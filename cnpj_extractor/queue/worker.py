"""
Consumidor de Tarefas / Worker (cnpj_extractor.queue.worker)
===========================================================
Consome mensagens da fila RabbitMQ, baixa o arquivo ZIP em blocos para disco
temporário, descompacta com zipfile (CRC32 verificado) e insere no SQLite.
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


class TaskWorker:
    def __init__(
        self,
        config: Optional[Config] = None,
        db: Optional[DatabaseManager] = None,
        client: Optional[ReceitaFederalClient] = None,
    ):
        self.config = config or Config.carregar()
        self.db = db or DatabaseManager(self.config.db_path)
        self.client = client or ReceitaFederalClient(self.config)
        self._canal = None
        self._conexao = None

    def iniciar_consumo(self, max_tarefas: Optional[int] = None) -> None:
        self._conexao = obter_conexao_rabbitmq(self.config)
        self._canal = self._conexao.channel()
        declarar_fila(self._canal, self.config.rabbitmq_queue)
        self._canal.basic_qos(prefetch_count=1)

        tarefas_processadas = 0

        def callback(ch, method, properties, body):
            nonlocal tarefas_processadas
            try:
                payload = json.loads(body.decode("utf-8"))
                sucesso = self._executar_tarefa(payload)
                if sucesso:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    tarefas_processadas += 1
                else:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except Exception as e:
                logger.error(f"Erro ao processar mensagem do worker: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            if max_tarefas and tarefas_processadas >= max_tarefas:
                ch.stop_consuming()

        self._canal.basic_consume(
            queue=self.config.rabbitmq_queue,
            on_message_callback=callback,
            auto_ack=False,
        )

        try:
            self._canal.start_consuming()
        except KeyboardInterrupt:
            if self._canal and self._canal.is_open:
                self._canal.stop_consuming()
        finally:
            if self._conexao and self._conexao.is_open:
                self._conexao.close()
            self.db.fechar()

    def _executar_tarefa(self, payload: dict) -> bool:
        nome_arquivo = payload["nome_arquivo"]
        tabela = payload["tabela"]
        mes = payload["mes"]
        url = payload["url"]
        tamanho_bytes = payload.get("tamanho_bytes", 0)
        filtro_uf = payload.get("filtro_uf")
        limite_linhas = payload.get("limite_linhas")
        batch_size = payload.get("batch_size", self.config.batch_size)

        arquivo = ArquivoRemoto(nome=nome_arquivo, tamanho_bytes=tamanho_bytes, url=url, mes=mes)

        if self.db.arquivo_ja_processado(arquivo.nome):
            logger.info(f"Arquivo '{arquivo.nome}' já processado anteriormente. Ignorando.")
            return True

        linhas_inseridas = 0
        try:
            with self.client.abrir_stream_arquivo(arquivo) as raw_http_stream:
                with abrir_csv_do_zip_remoto(raw_http_stream, encoding="latin1") as text_stream:
                    gerador_linhas = iterar_linhas_csv(
                        text_stream=text_stream,
                        tabela=tabela,
                        filtro_uf=filtro_uf,
                        limite=limite_linhas,
                    )
                    gerador_lotes = gerar_lotes_dados(gerador_linhas, batch_size=batch_size)

                    for lote in gerador_lotes:
                        qtd = self.db.inserir_lote(tabela, lote)
                        linhas_inseridas += qtd

            self.db.registrar_conclusao_arquivo(
                nome_arquivo=arquivo.nome,
                mes=mes,
                tabela=tabela,
                linhas_processadas=linhas_inseridas,
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao executar tarefa do arquivo '{arquivo.nome}': {e}")
            return False
