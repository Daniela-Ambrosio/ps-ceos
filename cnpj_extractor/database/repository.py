"""
Repositório de Dados e Consultas (cnpj_extractor.database.repository)
=====================================================================
Centraliza consultas com Prepared Statements, inserções idempotentes
e verificação inteligente de índices existentes no banco SQLite.
"""

import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .schema import (
    INDICES_POR_TABELA,
    TABELAS_DDL,
    MAPA_SITUACAO_CADASTRAL,
    MAPA_PORTE_EMPRESA,
    MAPA_MATRIZ_FILIAL,
    MAPA_TIPO_SOCIO,
    obter_comando_insert,
    validar_tabela,
)


class CNPJRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def inicializar_tabelas(self, tabelas: Optional[List[str]] = None) -> None:
        cursor = self.conn.cursor()
        cursor.execute(TABELAS_DDL["_ingestion_control"])

        tabelas_a_criar = tabelas or list(TABELAS_DDL.keys())
        for nome_tabela in tabelas_a_criar:
            if nome_tabela in TABELAS_DDL and nome_tabela != "_ingestion_control":
                validar_tabela(nome_tabela)
                cursor.execute(TABELAS_DDL[nome_tabela])
        cursor.close()

    def arquivo_ja_processado(self, nome_arquivo: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM _ingestion_control WHERE nome_arquivo = ? LIMIT 1;",
            (nome_arquivo,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row is not None

    def registrar_conclusao_arquivo(self, nome_arquivo: str, mes: str, tabela: str, linhas_processadas: int) -> None:
        validar_tabela(tabela)
        cursor = self.conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute(
            """
            INSERT OR REPLACE INTO _ingestion_control
            (nome_arquivo, mes, tabela, linhas_processadas, data_conclusao)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);
            """,
            (nome_arquivo, mes, tabela, linhas_processadas),
        )
        cursor.execute("COMMIT;")
        cursor.close()

    def inserir_lote(self, tabela: str, lote: List[Tuple]) -> int:
        if not lote:
            return 0
        validar_tabela(tabela)
        sql_insert = obter_comando_insert(tabela)
        cursor = self.conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        try:
            cursor.executemany(sql_insert, lote)
            cursor.execute("COMMIT;")
        except Exception:
            cursor.execute("ROLLBACK;")
            cursor.close()
            raise
        cursor.close()
        return len(lote)

    def verificar_e_garantir_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        """
        Verifica no sqlite_master quais índices já existem no banco e cria apenas
        os índices recomendados que estiverem faltando, independente de ter havido
        novas linhas inseridas nesta execução.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas_no_banco = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indices_existentes = {row[0] for row in cursor.fetchall()}

        indices_criados: List[str] = []
        for tab_nome, indices in INDICES_POR_TABELA.items():
            if tab_nome in tabelas_no_banco:
                if tabelas is None or tab_nome in tabelas:
                    for idx_sql in indices:
                        # Extrai o nome do índice (ex: idx_estabelecimentos_uf)
                        match = re.search(r"INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON", idx_sql, re.IGNORECASE)
                        idx_name = match.group(1) if match else None
                        if not idx_name or idx_name not in indices_existentes:
                            cursor.execute(idx_sql)
                            if idx_name:
                                indices_existentes.add(idx_name)
                                indices_criados.append(idx_name)
        cursor.close()
        return indices_criados

    def criar_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        """Atalho retrocompatível para verificar e garantir índices."""
        return self.verificar_e_garantir_indices(tabelas)

    def contar_linhas(self, tabela: str) -> int:
        validar_tabela(tabela)
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {tabela};")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def buscar_empresa_detalhada(self, cnpj_input: str) -> Optional[Dict[str, Any]]:
        digitos = "".join(filter(str.isdigit, cnpj_input.strip()))
        if not digitos:
            return None
        cnpj_basico = digitos[:8].zfill(8)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                e.cnpj_basico,
                e.razao_social,
                e.codigo_natureza_juridica,
                n.descricao AS natureza_juridica_descricao,
                e.qualificacao_responsavel,
                q.descricao AS qualificacao_responsavel_descricao,
                e.capital_social,
                e.porte_empresa,
                e.ente_federativo_responsavel,
                s.opcao_simples,
                s.data_opcao_simples,
                s.data_exclusao_simples,
                s.opcao_mei,
                s.data_opcao_mei,
                s.data_exclusao_mei
            FROM empresas e
            LEFT JOIN naturezas_juridicas n ON e.codigo_natureza_juridica = n.codigo
            LEFT JOIN qualificacoes_socios q ON e.qualificacao_responsavel = q.codigo
            LEFT JOIN simples s ON e.cnpj_basico = s.cnpj_basico
            WHERE e.cnpj_basico = ?
            LIMIT 1;
            """,
            (cnpj_basico,),
        )
        empresa_row = cursor.fetchone()
        if not empresa_row:
            cursor.close()
            return None

        empresa_dict = dict(empresa_row)
        empresa_dict["porte_descricao"] = MAPA_PORTE_EMPRESA.get(empresa_dict.get("porte_empresa"), "Outros")

        cursor.execute(
            """
            SELECT 
                est.cnpj_basico,
                est.cnpj_ordem,
                est.cnpj_dv,
                est.identificador_matriz_filial,
                est.nome_fantasia,
                est.situacao_cadastral,
                est.data_situacao_cadastral,
                m.descricao AS motivo_situacao_descricao,
                est.data_inicio_atividade,
                est.cnae_fiscal_principal,
                c.descricao AS cnae_principal_descricao,
                est.cnae_fiscal_secundaria,
                est.tipo_logradouro,
                est.logradouro,
                est.numero,
                est.complemento,
                est.bairro,
                est.cep,
                est.uf,
                est.municipio AS codigo_municipio,
                mun.descricao AS municipio_nome,
                est.ddd_1,
                est.telefone_1,
                est.ddd_2,
                est.telefone_2,
                est.correio_eletronico
            FROM estabelecimentos est
            LEFT JOIN motivos m ON est.motivo_situacao_cadastral = m.codigo
            LEFT JOIN cnaes c ON est.cnae_fiscal_principal = c.codigo
            LEFT JOIN municipios mun ON est.municipio = mun.codigo
            WHERE est.cnpj_basico = ?
            ORDER BY est.identificador_matriz_filial ASC, est.cnpj_ordem ASC;
            """,
            (cnpj_basico,),
        )
        estabelecimentos = []
        for row in cursor.fetchall():
            item = dict(row)
            item["situacao_descricao"] = MAPA_SITUACAO_CADASTRAL.get(item.get("situacao_cadastral"), "Desconhecida")
            item["tipo_unidade"] = MAPA_MATRIZ_FILIAL.get(item.get("identificador_matriz_filial"), "Estabelecimento")
            item["cnpj_completo"] = f"{item['cnpj_basico']}/{item['cnpj_ordem']}-{item['cnpj_dv']}"
            estabelecimentos.append(item)

        cursor.execute(
            """
            SELECT 
                soc.cnpj_basico,
                soc.identificador_socio,
                soc.nome_socio_razao_social,
                soc.cnpj_cpf_socio,
                soc.qualificacao_socio,
                q.descricao AS qualificacao_socio_descricao,
                soc.data_entrada_sociedade,
                soc.pais,
                p.descricao AS pais_nome,
                soc.representante_legal,
                soc.nome_do_representante,
                soc.faixa_etaria
            FROM socios soc
            LEFT JOIN qualificacoes_socios q ON soc.qualificacao_socio = q.codigo
            LEFT JOIN paises p ON soc.pais = p.codigo
            WHERE soc.cnpj_basico = ?;
            """,
            (cnpj_basico,),
        )
        socios = []
        for row in cursor.fetchall():
            item = dict(row)
            item["tipo_socio_descricao"] = MAPA_TIPO_SOCIO.get(item.get("identificador_socio"), "Outros")
            socios.append(item)

        cursor.close()
        empresa_dict["estabelecimentos"] = estabelecimentos
        empresa_dict["socios"] = socios
        return empresa_dict

    def buscar_empresas_por_filtros(
        self,
        termo_busca: Optional[str] = None,
        uf: Optional[str] = None,
        situacao: Optional[str] = None,
        limite: int = 50,
    ) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        condicoes = []
        parametros: List[Any] = []

        if termo_busca and termo_busca.strip():
            termo_limpo = f"%{termo_busca.strip().upper()}%"
            condicoes.append("(e.razao_social LIKE ? OR est.nome_fantasia LIKE ?)")
            parametros.extend([termo_limpo, termo_limpo])

        if uf and uf.strip() and uf.upper() != "TODOS":
            condicoes.append("est.uf = ?")
            parametros.append(uf.strip().upper())

        if situacao and situacao.strip() and situacao != "TODOS":
            condicoes.append("est.situacao_cadastral = ?")
            parametros.append(situacao.strip())

        where_clause = " WHERE " + " AND ".join(condicoes) if condicoes else ""

        sql = f"""
            SELECT DISTINCT
                est.cnpj_basico,
                est.cnpj_ordem,
                est.cnpj_dv,
                e.razao_social,
                est.nome_fantasia,
                est.uf,
                mun.descricao AS municipio,
                est.situacao_cadastral,
                est.cnae_fiscal_principal,
                c.descricao AS cnae_descricao,
                e.capital_social
            FROM estabelecimentos est
            JOIN empresas e ON est.cnpj_basico = e.cnpj_basico
            LEFT JOIN municipios mun ON est.municipio = mun.codigo
            LEFT JOIN cnaes c ON est.cnae_fiscal_principal = c.codigo
            {where_clause}
            ORDER BY e.capital_social DESC
            LIMIT ?;
        """
        parametros.append(limite)

        cursor.execute(sql, tuple(parametros))
        resultados = []
        for r in cursor.fetchall():
            item = dict(r)
            item["cnpj_formatado"] = f"{item['cnpj_basico']}/{item['cnpj_ordem']}-{item['cnpj_dv']}"
            item["situacao_texto"] = MAPA_SITUACAO_CADASTRAL.get(item.get("situacao_cadastral"), "Outros")
            resultados.append(item)

        cursor.close()
        return resultados
