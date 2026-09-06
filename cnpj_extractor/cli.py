"""
Interface de Linha de Comando (cnpj_extractor.cli)
=================================================
Permite executar a aplicação em modo standalone, produtor (RabbitMQ),
worker concorrente ou efetuar consultas e verificação de índices no PostgreSQL.
"""

import argparse
import sys
from typing import List, Optional

from .config import Config
from .database import DatabaseManager
from .extraction import IngestionPipeline, ReceitaFederalClient
from .queue.producer import TaskProducer
from .queue.worker import TaskWorker


def criar_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cnpj-streamer",
        description="🚀 Ingestão e Processamento Concorrente de CNPJ (PostgreSQL & RabbitMQ)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["standalone", "producer", "worker"],
        default="standalone",
        help="Modo de operação: standalone (direto), producer (publica no RabbitMQ) ou worker (consome e grava no Postgres)",
    )
    parser.add_argument("--list-months", action="store_true", help="Lista os meses disponíveis na Receita Federal")
    parser.add_argument("--list-files", action="store_true", help="Lista os arquivos remotos do mês selecionado")
    parser.add_argument("--status", action="store_true", help="Exibe a contagem de registros por tabela no PostgreSQL")
    parser.add_argument("--search-cnpj", type=str, help="Busca uma empresa completa pelo CNPJ no PostgreSQL")
    parser.add_argument("--create-indexes", action="store_true", help="Garante a criação de índices no PostgreSQL")

    # Parâmetros de extração
    parser.add_argument("--month", type=str, default=None, help="Mês de referência (ex: 2026-08 ou latest)")
    parser.add_argument("--tables", type=str, default="all", help="Tabelas ou grupos separados por vírgula (ex: empresas,estabelecimentos ou all)")
    parser.add_argument("--uf", type=str, default=None, help="Filtro por UF para estabelecimentos (ex: SP, RJ)")
    parser.add_argument("--limit", type=int, default=None, help="Limite de linhas por arquivo para testes rápidos")
    parser.add_argument("--batch-size", type=int, default=None, help="Tamanho do lote para inserções no PostgreSQL")
    parser.add_argument("--url", "--token", dest="url_ou_token", type=str, default=None, help="URL pública ou token da Receita")
    parser.add_argument("--force", action="store_true", help="Força reprocessamento de arquivos já concluídos")
    parser.add_argument("--no-index", action="store_true", help="Pula a etapa de verificação/criação de índices")

    # Parâmetros do PostgreSQL
    parser.add_argument("--pg-host", type=str, default=None, help="Host do PostgreSQL")
    parser.add_argument("--pg-port", type=int, default=None, help="Porta do PostgreSQL")
    parser.add_argument("--pg-db", type=str, default=None, help="Nome do banco de dados PostgreSQL")
    parser.add_argument("--pg-user", type=str, default=None, help="Usuário do PostgreSQL")
    parser.add_argument("--pg-password", type=str, default=None, help="Senha do PostgreSQL")
    parser.add_argument("--database-url", type=str, default=None, help="URL de conexão PostgreSQL (ex: postgresql://user:pass@host:5432/db)")

    # Parâmetros do RabbitMQ
    parser.add_argument("--rabbitmq-host", type=str, default=None, help="Host do RabbitMQ")
    parser.add_argument("--rabbitmq-port", type=int, default=None, help="Porta do RabbitMQ")
    parser.add_argument("--rabbitmq-user", type=str, default=None, help="Usuário do RabbitMQ")
    parser.add_argument("--rabbitmq-password", type=str, default=None, help="Senha do RabbitMQ")
    parser.add_argument("--rabbitmq-queue", type=str, default=None, help="Nome da fila no RabbitMQ")
    parser.add_argument("--max-tasks", type=int, default=None, help="Máximo de tarefas para o worker processar antes de encerrar")

    return parser


def executar_cli(args_lista: Optional[List[str]] = None) -> int:
    parser = criar_argument_parser()
    args = parser.parse_args(args_lista)

    config = Config.carregar(
        url_ou_token=args.url_ou_token,
        batch_size=args.batch_size,
        month=args.month,
        postgres_host=args.pg_host,
        postgres_port=args.pg_port,
        postgres_db=args.pg_db,
        postgres_user=args.pg_user,
        postgres_password=args.pg_password,
        database_url=args.database_url,
        rabbitmq_host=args.rabbitmq_host,
        rabbitmq_port=args.rabbitmq_port,
        rabbitmq_user=args.rabbitmq_user,
        rabbitmq_password=args.rabbitmq_password,
        rabbitmq_queue=args.rabbitmq_queue,
    )

    if args.list_months:
        client = ReceitaFederalClient(config)
        for m in client.listar_meses_disponiveis():
            print(f"  • {m}")
        return 0

    if args.list_files:
        client = ReceitaFederalClient(config)
        mes_alvo = args.month or config.default_month
        if mes_alvo == "latest":
            mes_alvo = client.obter_mes_mais_recente()
        for a in client.listar_arquivos(mes_alvo):
            print(f"  • {a.nome.ljust(30)} {a.tamanho_formatado.rjust(12)}")
        return 0

    if args.status:
        db = DatabaseManager(config)
        for tab in [
            "cnaes", "motivos", "municipios", "naturezas_juridicas", "paises",
            "qualificacoes_socios", "empresas", "estabelecimentos", "socios", "simples",
        ]:
            try:
                print(f"  • {tab.ljust(25)}: {db.contar_linhas(tab):,} registros")
            except Exception:
                print(f"  • {tab.ljust(25)}: (não criada ou inacessível)")
        return 0

    if args.search_cnpj:
        db = DatabaseManager(config)
        empresa = db.buscar_empresa_detalhada(args.search_cnpj)
        if not empresa:
            print(f"❌ Nenhuma empresa encontrada com CNPJ '{args.search_cnpj}'.")
            return 1
        for k in ["cnpj_basico", "razao_social", "porte_descricao", "capital_social"]:
            print(f"  {k}: {empresa.get(k)}")
        return 0

    tabelas_lista = [t.strip() for t in args.tables.split(",") if t.strip()]

    if args.create_indexes:
        pipeline = IngestionPipeline(config=config)
        pipeline.verificar_e_criar_indices(mes=args.month, tabelas=tabelas_lista)
        return 0

    if args.mode == "producer":
        producer = TaskProducer(config=config)
        producer.publicar_tarefas(
            mes=args.month,
            tabelas=tabelas_lista,
            filtro_uf=args.uf,
            limite_linhas=args.limit,
            pular_ja_processados=not args.force,
        )
        return 0

    if args.mode == "worker":
        worker = TaskWorker(config=config)
        worker.iniciar_consumo(max_tarefas=args.max_tasks)
        return 0

    # Modo standalone (execução direta)
    pipeline = IngestionPipeline(config=config)
    pipeline.executar(
        mes=args.month,
        tabelas=tabelas_lista,
        filtro_uf=args.uf,
        limite_linhas_por_arquivo=args.limit,
        pular_ja_processados=not args.force,
        criar_indices_ao_final=not args.no_index,
    )
    return 0
