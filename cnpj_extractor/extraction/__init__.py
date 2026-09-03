"""
Módulo de Extração e Parsing (cnpj_extractor.extraction)
========================================================
Responsável por conexão WebDAV/HTTP com a Receita, download temporário,
descompactação segura com zipfile e parsing de CSV.
"""

from .client import ArquivoRemoto, ReceitaFederalClient
from .parser import (
    _sanitizar_float,
    _sanitizar_texto,
    gerar_lotes_dados,
    iterar_linhas_csv,
    normalizar_linha,
)
from .pipeline import (
    EstatisticasProcessamento,
    IngestionPipeline,
    resolver_tabelas_solicitadas,
)
from .zip_extractor import abrir_csv_do_zip_remoto

__all__ = [
    "ReceitaFederalClient",
    "ArquivoRemoto",
    "abrir_csv_do_zip_remoto",
    "normalizar_linha",
    "iterar_linhas_csv",
    "gerar_lotes_dados",
    "_sanitizar_texto",
    "_sanitizar_float",
    "IngestionPipeline",
    "EstatisticasProcessamento",
    "resolver_tabelas_solicitadas",
]
