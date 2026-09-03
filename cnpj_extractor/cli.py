"""
Interface de Linha de Comando (cnpj_extractor.cli)
=================================================
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
    parser = argparse.ArgumentParser(prog="cnpj-streamer", description="🚀 Coletor e Parser em Streaming de Dados de CNPJ")
    parser.add_argument("--mode", type=str, choices=["standalone", "producer", "worker"], default="standalone")
    parser.add_argument("--list-months", action="store_true")
    parser.add_argument("--list-files", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--search-cnpj", type=str)
    parser.add_argument("--create-indexes", action="store_true")
    parser.add_argument("--month", type=str, default=None)
    parser.add_argument("--tables", type=str, default="all")
    parser.add_argument("--uf", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--db-path", type=str, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--url", "--token", dest="url_ou_token", type=str, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-index", action="store_true")
    parser.add_argument("--rabbitmq-host", type=str, default=None)
    parser.add_argument("--rabbitmq-port", type=int, default=None)
    parser.add_argument("--rabbitmq-user", type=str, default=None)
    parser.add_argument("--rabbitmq-password", type=str, default=None)
    parser.add_argument("--rabbitmq-queue", type=str, default=None)
    parser.add_argument("--max-tasks", type=int, default=None)
    return parser


def executar_cli(args_lista: Optional[List[str]] = None) -> int:
    parser = criar_argument_parser()
    args = parser.parse_args(args_lista)
    config = Config.carregar(
        url_ou_token=args.url_ou_token,
        db_path=args.db_path,
        batch_size=args.batch_size,
        month=args.month,
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
        db = DatabaseManager(config.db_path)
        for tab in ["cnaes", "motivos", "municipios", "naturezas_juridicas", "paises", "qualificacoes_socios", "empresas", "estabelecimentos", "socios", "simples"]:
            try:
                print(f"  • {tab.ljust(25)}: {db.contar_linhas(tab):,} registros")
            except Exception:
                print(f"  • {tab.ljust(25)}: (não criada)")
        return 0

    if args.search_cnpj:
        db = DatabaseManager(config.db_path)
        empresa = db.buscar_empresa_detalhada(args.search_cnpj)
        if not empresa:
            print(f"❌ Nenhuma empresa encontrada com CNPJ '{args.search_cnpj}'.")
            return 1
        for k in ["cnpj_basico", "razao_social", "porte_descricao", "capital_social"]:
            print(f"  {k}: {empresa.get(k)}")
        return 0

    if args.create_indexes:
        db = DatabaseManager(config.db_path)
        print("⚡ Criando índices no banco de dados...")
        db.criar_indices()
        print("✅ Índices criados com sucesso!")
        return 0

    if args.mode == "producer":
        tabelas_lista = [t.strip() for t in args.tables.split(",") if t.strip()]
        producer = TaskProducer(config=config)
        producer.publicar_tarefas(mes=args.month, tabelas=tabelas_lista, filtro_uf=args.uf, limite_linhas=args.limit, pular_ja_processados=not args.force)
        return 0

    if args.mode == "worker":
        worker = TaskWorker(config=config)
        worker.iniciar_consumo(max_tarefas=args.max_tasks)
        return 0

    tabelas_lista = [t.strip() for t in args.tables.split(",") if t.strip()]
    pipeline = IngestionPipeline(config=config)
    pipeline.executar(mes=args.month, tabelas=tabelas_lista, filtro_uf=args.uf, limite_linhas_por_arquivo=args.limit, pular_ja_processados=not args.force, criar_indices_ao_final=not args.no_index)
    return 0
