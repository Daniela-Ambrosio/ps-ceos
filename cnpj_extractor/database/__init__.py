"""
Módulo de Banco de Dados PostgreSQL (cnpj_extractor.database)
==============================================================
Centraliza esquemas DDL, pool de conexões thread-safe e repositório PostgreSQL.
"""

from .connection import PostgresConnectionPool
from .manager import DatabaseManager
from .repository import CNPJRepository
from .schema import (
    ARQUIVO_PARA_TABELA,
    GRUPOS_TABELAS,
    INDICES_DDL,
    INDICES_POR_TABELA,
    MAPA_MATRIZ_FILIAL,
    MAPA_PORTE_EMPRESA,
    MAPA_SITUACAO_CADASTRAL,
    MAPA_TIPO_SOCIO,
    TABELAS_DDL,
    TABELAS_PERMITIDAS,
    identificar_tabela_por_arquivo,
    obter_comando_upsert,
    validar_tabela,
)

# Alias retrocompatível
obter_comando_insert = obter_comando_upsert

__all__ = [
    "DatabaseManager",
    "CNPJRepository",
    "PostgresConnectionPool",
    "TABELAS_PERMITIDAS",
    "GRUPOS_TABELAS",
    "ARQUIVO_PARA_TABELA",
    "TABELAS_DDL",
    "INDICES_POR_TABELA",
    "INDICES_DDL",
    "identificar_tabela_por_arquivo",
    "validar_tabela",
    "obter_comando_upsert",
    "obter_comando_insert",
    "MAPA_SITUACAO_CADASTRAL",
    "MAPA_PORTE_EMPRESA",
    "MAPA_MATRIZ_FILIAL",
    "MAPA_TIPO_SOCIO",
]
