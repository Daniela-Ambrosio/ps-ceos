"""
Consumidor de Tarefas / Worker Concorrente (cnpj_extractor.queue.worker)
========================================================================
Consome tarefas da fila RabbitMQ em paralelo com proteção contra poison pills,
limite de tentativas com Dead-Letter Queue (DLQ) e UPSERT em lote no PostgreSQL.
Garante envio de ACK estritamente após conclusão total e registro no banco.
"""

import json
import logging
import sys
import time
from typing import Optional

try:
    import pika
except ImportError:
    pika = None

from ..config import Config
from ..database import DatabaseManager
from ..extraction import (
    ArquivoRemoto,
    ReceitaFederalClient,
    abrir_csv_do_zip_remoto,
    gerar_lotes_dados,
    iterar_linhas_csv,
)
from .connection import declarar_fila, obter_conexao_rabbitmq

logger = logging.getLogger("cnpj_extractor.worker")

# Limite máximo de tentativas antes de descartar para a Dead-Letter Queue
MAX_TENTATIVAS_REQUEUE = 3


class TaskWorker:
    def __init__(
        self,
        config: Optional[Config] = None,
        db: Optional[DatabaseManager] = None,
        client: Optional[ReceitaFederalClient] = None,
    ):
        self.config = config or Config.carregar()
        self.db = db or DatabaseManager(self.config)
        self.client = client or ReceitaFederalClient(self.config)
        self._canal = None
        self._conexao = None

    def iniciar_consumo(self, max_tarefas: Optional[int] = None) -> None:
        """Inicia o consumo concorrente com prefetch_count=1 (Fair Dispatch) e proteção DLQ."""
        self._conexao = obter_conexao_rabbitmq(self.config)
        self._canal = self._conexao.channel()
        # Enable publisher confirms to safely republish with acknowledgment
        self._canal.confirm_delivery()
        declarar_fila(self._canal, self.config.rabbitmq_queue)
        self._canal.basic_qos(prefetch_count=1)

        tarefas_processadas = 0

        def callback(ch, method, properties, body):
            nonlocal tarefas_processadas
            nome_arquivo = "desconhecido"

            # 1. Parsing e validação de JSON seguro (proteção contra mensagens malformadas / poison pills)
            try:
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"Payload deve ser um dicionário JSON, recebido: {type(payload)}")
            except Exception as parse_err:
                logger.critical(
                    f"🚨 Mensagem corrompida / JSON inválido recebido: {body!r} ({parse_err}). "
                    f"Descartando para Dead-Letter Queue (requeue=False)."
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            nome_arquivo = payload.get("nome_arquivo", "desconhecido")

            logger.info(f"Worker recebeu tarefa: {nome_arquivo} ({payload.get('tabela')})")

            # 3. Execução da tarefa
            try:
                sucesso = self._executar_tarefa(payload)
                if sucesso:
                    # Confirmação (ACK) apenas após conclusão total e registro no PostgreSQL
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    tarefas_processadas += 1
                    logger.info(f"✅ Conclusão confirmada (ACK): {nome_arquivo}")
                    if max_tarefas and tarefas_processadas >= max_tarefas:
                        ch.stop_consuming()
                    return
                
            except (KeyError, ValueError) as deterministico_err:
                # Erro determinístico de dados/configuração (não vai resolver tentando de novo)
                logger.critical(
                    f"🚨 Erro permanente/determinístico no payload de '{nome_arquivo}': {deterministico_err}. "
                    f"Enviando para Dead-Letter Queue sem requeue."
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            except Exception as e:
                logger.error(f"❌ Exceção inesperada no processamento de {nome_arquivo}: {e}. Aplicando política de retry.")
                # Incrementar tentativas
                attempts = 0
                if properties and properties.headers:
                    attempts = properties.headers.get('x-attempts', 0)
                new_attempts = attempts + 1
                if new_attempts >= MAX_TENTATIVAS_REQUEUE:
                    logger.critical(
                        f"🚨 Limite de {MAX_TENTATIVAS_REQUEUE} tentativas excedido para a tarefa '{nome_arquivo}'. "
                        f"Enviando mensagem para Dead-Letter Queue (requeue=False)."
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return
                # Backoff antes de republicar (exponential with cap at 30s)
                backoff = min(2 ** attempts, 30)
                time.sleep(backoff)
                # Republishing com x-attempts incrementado, preservando propriedades originais
                new_headers = dict(properties.headers or {})
                new_headers['x-attempts'] = new_attempts
                new_props = pika.BasicProperties(
                    delivery_mode=properties.delivery_mode,
                    priority=properties.priority,
                    content_type=properties.content_type,
                    headers=new_headers,
                )
                try:
                    ch.basic_publish(
                        exchange="",
                        routing_key=self.config.rabbitmq_queue,
                        body=body,
                        properties=new_props,
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"✅ Republicado '{nome_arquivo}' com tentativa {new_attempts}/{MAX_TENTATIVAS_REQUEUE}")
                except (pika.exceptions.UnroutableError, pika.exceptions.NackError) as pub_err:
                    logger.error(f"❌ Falha ao republicar mensagem para '{nome_arquivo}': {pub_err}. Mensagem original será reenviada pela fila.")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

            if max_tarefas and tarefas_processadas >= max_tarefas:
                ch.stop_consuming()

        self._canal.basic_consume(
            queue=self.config.rabbitmq_queue,
            on_message_callback=callback,
            auto_ack=False,
        )

        logger.info(f"Worker pronto e aguardando tarefas na fila '{self.config.rabbitmq_queue}'...")
        try:
            self._canal.start_consuming()
        except KeyboardInterrupt:
            logger.info("Encerrando worker após solicitação do usuário...")
            if self._canal and self._canal.is_open:
                self._canal.stop_consuming()
        finally:
            if self._conexao and self._conexao.is_open:
                self._conexao.close()
            self.db.fechar()

    def _executar_tarefa(self, payload: dict) -> bool:
        """
        Executa a tarefa validando todos os campos com .get() de forma resiliente.
        """
        nome_arquivo = payload.get("nome_arquivo")
        tabela = payload.get("tabela")
        mes = payload.get("mes")
        url = payload.get("url")

        if not nome_arquivo or not tabela or not mes or not url:
            raise KeyError(
                f"Payload incompleto. Campos obrigatórios ausentes: "
                f"nome_arquivo={nome_arquivo}, tabela={tabela}, mes={mes}, url={url}"
            )

        tamanho_bytes = payload.get("tamanho_bytes", 0)
        filtro_uf = payload.get("filtro_uf")
        limite_linhas = payload.get("limite_linhas")
        batch_size = payload.get("batch_size", self.config.batch_size)

        arquivo = ArquivoRemoto(nome=nome_arquivo, tamanho_bytes=tamanho_bytes, url=url, mes=mes)

        # Checagem de segurança concorrente no PostgreSQL
        if self.db.arquivo_ja_processado(arquivo.nome):
            logger.info(f"Arquivo '{arquivo.nome}' já registrado anteriormente no banco. Pulando processamento.")
            return True

        linhas_inseridas = 0
        tempo_inicio = time.time()

        with self.client.abrir_stream_arquivo(arquivo) as raw_http_stream:
            with abrir_csv_do_zip_remoto(raw_http_stream, encoding="latin1") as text_stream:
                gerador_linhas = iterar_linhas_csv(
                    text_stream=text_stream,
                    tabela=tabela,
                    filtro_uf=filtro_uf,
                    limite=limite_linhas,
                )
                gerador_lotes = gerar_lotes_dados(
                    gerador_linhas,
                    batch_size=batch_size,
                )

                for lote in gerador_lotes:
                    qtd = self.db.inserir_lote(tabela, lote)
                    linhas_inseridas += qtd

        # Registra conclusão atômica no PostgreSQL com chave única
        self.db.registrar_conclusao_arquivo(
            nome_arquivo=arquivo.nome,
            mes=mes,
            tabela=tabela,
            linhas_processadas=linhas_inseridas,
        )

        delta_t = max(time.time() - tempo_inicio, 0.001)
        velocidade = linhas_inseridas / delta_t
        logger.info(
            f"Arquivo '{arquivo.nome}' gravado no PostgreSQL: {linhas_inseridas:,} linhas em {delta_t:.1f}s ({velocidade:,.0f} lin/s)."
        )
        return True
