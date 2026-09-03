"""
Fachada DatabaseManager (cnpj_extractor.database.manager)
=========================================================
Mantém interface limpa e unificada para controle do banco SQLite.
"""

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .connection import criar_conexao_sqlite
from .repository import CNPJRepository


class DatabaseManager:
    def __init__(self, db_path: str = "data/cnpj.db"):
        self.db_path = Path(db_path).resolve()
        self._conn: Optional[sqlite3.Connection] = None
        self._repo: Optional[CNPJRepository] = None

    def conectar(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = criar_conexao_sqlite(self.db_path)
            self._repo = CNPJRepository(self._conn)
        return self._conn

    @property
    def repository(self) -> CNPJRepository:
        if self._repo is None:
            self.conectar()
        return self._repo

    def inicializar_tabelas(self, tabelas: Optional[List[str]] = None) -> None:
        self.repository.inicializar_tabelas(tabelas)

    def arquivo_ja_processado(self, nome_arquivo: str) -> bool:
        return self.repository.arquivo_ja_processado(nome_arquivo)

    def registrar_conclusao_arquivo(self, nome_arquivo: str, mes: str, tabela: str, linhas_processadas: int) -> None:
        self.repository.registrar_conclusao_arquivo(nome_arquivo, mes, tabela, linhas_processadas)

    def inserir_lote(self, tabela: str, lote: List[Tuple]) -> int:
        return self.repository.inserir_lote(tabela, lote)

    def verificar_e_garantir_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        return self.repository.verificar_e_garantir_indices(tabelas)

    def criar_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        return self.repository.criar_indices(tabelas)

    def contar_linhas(self, tabela: str) -> int:
        return self.repository.contar_linhas(tabela)

    def buscar_empresa_detalhada(self, cnpj_input: str) -> Optional[Dict[str, Any]]:
        return self.repository.buscar_empresa_detalhada(cnpj_input)

    def buscar_empresas_por_filtros(self, termo_busca: Optional[str] = None, uf: Optional[str] = None, situacao: Optional[str] = None, limite: int = 50) -> List[Dict[str, Any]]:
        return self.repository.buscar_empresas_por_filtros(termo_busca, uf, situacao, limite)

    def fechar(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._repo = None
