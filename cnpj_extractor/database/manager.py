"""
Fachada DatabaseManager (cnpj_extractor.database.manager)
=========================================================
Mantém interface limpa e unificada para controle do PostgreSQL com Connection Pool.
"""

from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from .connection import PostgresConnectionPool
from .repository import CNPJRepository


class DatabaseManager:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.carregar()
        self.pool = PostgresConnectionPool(self.config)
        self.repository = CNPJRepository(self.pool)

    def inicializar_tabelas(self, tabelas: Optional[List[str]] = None) -> None:
        self.repository.inicializar_tabelas(tabelas)

    def arquivo_ja_processado(self, nome_arquivo: str) -> bool:
        return self.repository.arquivo_ja_processado(nome_arquivo)

    def registrar_conclusao_arquivo(
        self, nome_arquivo: str, mes: str, tabela: str, linhas_processadas: int
    ) -> None:
        self.repository.registrar_conclusao_arquivo(nome_arquivo, mes, tabela, linhas_processadas)

    def inserir_lote(self, tabela: str, lote: List[Tuple]) -> int:
        return self.repository.inserir_lote(tabela, lote)

    def verificar_arquivos_pendentes(self, mes: str, arquivos_esperados: List[str]) -> List[str]:
        return self.repository.verificar_arquivos_pendentes(mes, arquivos_esperados)

    def todos_arquivos_concluidos(self, mes: str, arquivos_esperados: List[str]) -> bool:
        return self.repository.todos_arquivos_concluidos(mes, arquivos_esperados)

    def garantir_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        return self.repository.garantir_indices(tabelas)

    def criar_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        return self.repository.garantir_indices(tabelas)

    def contar_linhas(self, tabela: str) -> int:
        return self.repository.contar_linhas(tabela)

    def buscar_empresa_detalhada(self, cnpj_input: str) -> Optional[Dict[str, Any]]:
        return self.repository.buscar_empresa_detalhada(cnpj_input)

    def listar_cnaes(self) -> List[Tuple[str, str]]:
        """Delegate to repository.listar_cnaes."""
        return self.repository.listar_cnaes()

    def listar_municipios(self, uf: Optional[str] = None) -> List[Tuple[str, str]]:
        """Delegate to repository.listar_municipios, optionally filtered by UF."""
        return self.repository.listar_municipios(uf)

    def buscar_empresas_por_filtros(
        self,
        termo_busca: Optional[str] = None,
        uf: Optional[str] = None,
        situacao: Optional[str] = None,
        cnae_codigo: Optional[str] = None,
        municipio_codigo: Optional[str] = None,
        limite: int = 50,
    ) -> List[Dict[str, Any]]:
        """Delegate to repository.buscar_empresas_por_filtros with all filter parameters."""
        return self.repository.buscar_empresas_por_filtros(
            termo_busca=termo_busca,
            uf=uf,
            situacao=situacao,
            cnae_codigo=cnae_codigo,
            municipio_codigo=municipio_codigo,
            limite=limite,
        )

    def fechar(self) -> None:
        self.pool.fechar_todos()
