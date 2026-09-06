"""
Produtor / Orquestrador de Mensagens RabbitMQ (cnpj_extractor.queue.producer)
===========================================================================
Descobre os arquivos remotos da Receita Federal e publica UMA mensagem por arquivo
na fila RabbitMQ para distribuição balanceada entre múltiplos workers concorrentes.
"""

import json
import logging
from typing import Dict, List, Optional, Set, Tuple

try:
    import pika
except ImportError:
    pika = None

from ..config import Config
from ..database import DatabaseManager, identificar_tabela_por_arquivo
from ..extraction import ArquivoRemoto, ReceitaFederalClient, resolver_tabelas_solicitadas
from .connection import declarar_fila, obter_conexao_rabbitmq

logger = logging.getLogger("cnpj_extractor.producer")


class TaskProducer:
    """
    Publica tarefas individuais de processamento de arquivos na fila RabbitMQ.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        client: Optional[ReceitaFederalClient] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.config = config or Config.carregar()
        self.client = client or ReceitaFederalClient(self.config)
        self.db = db or DatabaseManager(self.config)

    def publicar_tarefas(
        self,
        mes: Optional[str] = None,
        tabelas: Optional[List[str]] = None,
        filtro_uf: Optional[str] = None,
        limite_linhas: Optional[int] = None,
        pular_ja_processados: bool = True,
    ) -> Tuple[int, List[str]]:
        """
        Descobre arquivos remotos e publica na fila RabbitMQ.
        Retorna (quantidade_de_tarefas_publicadas, lista_total_arquivos_esperados).
        """
        mes_alvo = mes or self.config.default_month
        if mes_alvo == "latest":
            logger.info("Identificando o mês mais recente disponível na Receita Federal...")
            mes_alvo = self.client.obter_mes_mais_recente()

        logger.info(f"Mês de extração: {mes_alvo}")
        tabelas_alvo = resolver_tabelas_solicitadas(tabelas)
        logger.info(f"Tabelas alvo: {', '.join(sorted(tabelas_alvo))}")

        # 1. Garante a criação do esquema no PostgreSQL antes do consumo dos workers
        self.db.inicializar_tabelas(list(tabelas_alvo))

        # 2. Descobre os arquivos remotos
        todos_arquivos = self.client.listar_arquivos(mes_alvo)
        arquivos_para_processar: List[ArquivoRemoto] = []
        arquivos_esperados: List[str] = []

        for arq in todos_arquivos:
            tabela_correspondente = identificar_tabela_por_arquivo(arq.nome)
            if tabela_correspondente and tabela_correspondente in tabelas_alvo:
                arquivos_esperados.append(arq.nome)
                if pular_ja_processados and self.db.arquivo_ja_processado(arq.nome):
                    logger.info(f"⏭️  Arquivo '{arq.nome}' já registrado no banco. Pulando publicação.")
                    continue
                arquivos_para_processar.append(arq)

        if not arquivos_para_processar:
            logger.info("Nenhuma nova tarefa a ser publicada no RabbitMQ.")
            return 0, arquivos_esperados

        # 3. Conecta ao RabbitMQ e publica uma mensagem por arquivo
        conexao = obter_conexao_rabbitmq(self.config)
        canal = conexao.channel()
        declarar_fila(canal, self.config.rabbitmq_queue)

        tarefas_publicadas = 0
        try:
            for arq in arquivos_para_processar:
                tabela = identificar_tabela_por_arquivo(arq.nome)
                # Lookups (CNAEs, Motivos, Municípios) recebem prioridade alta para popular primeiro
                prioridade = 9 if tabela in {
                    "cnaes", "motivos", "municipios", "naturezas_juridicas", "paises", "qualificacoes_socios"
                } else 1

                payload = {
                    "nome_arquivo": arq.nome,
                    "tabela": tabela,
                    "mes": mes_alvo,
                    "url": arq.url,
                    "tamanho_bytes": arq.tamanho_bytes,
                    "filtro_uf": filtro_uf,
                    "limite_linhas": limite_linhas,
                    "batch_size": self.config.batch_size,
                }

                corpo_json = json.dumps(payload, ensure_ascii=False)
                canal.basic_publish(
                    exchange="",
                    routing_key=self.config.rabbitmq_queue,
                    body=corpo_json.encode("utf-8"),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Mensagem persistente em disco
                        priority=prioridade,
                        content_type="application/json",
                        headers={"x-attempts": 0},
                    ) if pika else None,
                )
                tarefas_publicadas += 1
                logger.info(f"📦 Publicada tarefa: {arq.nome} (Prioridade: {prioridade})")

        finally:
            canal.close()
            conexao.close()

        logger.info(f"🚀 Total de {tarefas_publicadas} tarefas publicadas com sucesso na fila '{self.config.rabbitmq_queue}'.")
        return tarefas_publicadas, arquivos_esperados
