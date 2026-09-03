"""
Produtor de Tarefas de Ingestão (cnpj_extractor.queue.producer)
==============================================================
"""

import json
from typing import Dict, List, Optional, Set

try:
    import pika
except ImportError:
    pika = None

from ..config import Config
from ..database import DatabaseManager, identificar_tabela_por_arquivo
from ..extraction import ReceitaFederalClient, resolver_tabelas_solicitadas
from .connection import declarar_fila, obter_conexao_rabbitmq


class TaskProducer:
    def __init__(
        self,
        config: Optional[Config] = None,
        client: Optional[ReceitaFederalClient] = None,
        db: Optional[DatabaseManager] = None,
    ):
        self.config = config or Config.carregar()
        self.client = client or ReceitaFederalClient(self.config)
        self.db = db or DatabaseManager(self.config.db_path)

    def publicar_tarefas(
        self,
        mes: Optional[str] = None,
        tabelas: Optional[List[str]] = None,
        filtro_uf: Optional[str] = None,
        limite_linhas: Optional[int] = None,
        pular_ja_processados: bool = True,
    ) -> int:
        mes_alvo = mes or self.config.default_month
        if mes_alvo == "latest":
            mes_alvo = self.client.obter_mes_mais_recente()

        tabelas_alvo = resolver_tabelas_solicitadas(tabelas)
        self.db.inicializar_tabelas(list(tabelas_alvo))
        todos_arquivos = self.client.listar_arquivos(mes_alvo)

        conexao = obter_conexao_rabbitmq(self.config)
        canal = conexao.channel()
        declarar_fila(canal, self.config.rabbitmq_queue)

        tarefas_publicadas = 0
        try:
            for arq in todos_arquivos:
                tabela = identificar_tabela_por_arquivo(arq.nome)
                if not tabela or tabela not in tabelas_alvo:
                    continue

                if pular_ja_processados and self.db.arquivo_ja_processado(arq.nome):
                    continue

                prioridade = 9 if tabela in {"cnaes", "motivos", "municipios", "naturezas_juridicas", "paises", "qualificacoes_socios"} else 1
                payload = {
                    "nome_arquivo": arq.nome,
                    "tabela": tabela,
                    "mes": mes_alvo,
                    "url": arq.url,
                    "tamanho_bytes": arq.tamanho_bytes,
                    "filtro_uf": filtro_uf,
                    "limite_linhas": limite_linhas,
                    "batch_size": self.config.batch_size,
                    "db_path": str(self.db.db_path),
                }

                corpo_json = json.dumps(payload, ensure_ascii=False)
                canal.basic_publish(
                    exchange="",
                    routing_key=self.config.rabbitmq_queue,
                    body=corpo_json.encode("utf-8"),
                    properties=pika.BasicProperties(delivery_mode=2, priority=prioridade, content_type="application/json") if pika else None,
                )
                tarefas_publicadas += 1
        finally:
            canal.close()
            conexao.close()
        return tarefas_publicadas
