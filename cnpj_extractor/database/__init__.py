"""
Módulo de Banco de Dados (cnpj_extractor.database)
==================================================
Centraliza esquemas, conexões otimizadas e consultas estruturadas SQLite.
"""

from .schema import (
    TABELAS_PERMITIDAS,
    GRUPOS_TABELAS,
    ARQUIVO_PARA_TABELA,
    TABELAS_DDL,
    INDICES_POR_TABELA,
    INDICES_DDL,
    identificar_tabela_por_arquivo,
    validar_tabela,
    obter_comando_insert,
    MAPA_SITUACAO_CADASTRAL,
    MAPA_PORTE_EMPRESA,
    MAPA_MATRIZ_FILIAL,
    MAPA_TIPO_SOCIO,
)
from .connection import criar_conexao_sqlite
from .repository import CNPJRepository
from .manager import DatabaseManager

__all__ = [
    "DatabaseManager",
    "CNPJRepository",
    "criar_conexao_sqlite",
    "TABELAS_PERMITIDAS",
    "GRUPOS_TABELAS",
    "ARQUIVO_PARA_TABELA",
    "TABELAS_DDL",
    "INDICES_POR_TABELA",
    "INDICES_DDL",
    "identificar_tabela_por_arquivo",
    "validar_tabela",
    "obter_comando_insert",
    "MAPA_SITUACAO_CADASTRAL",
    "MAPA_PORTE_EMPRESA",
    "MAPA_MATRIZ_FILIAL",
    "MAPA_TIPO_SOCIO",
]
