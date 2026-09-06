"""
Repositório de Dados PostgreSQL (cnpj_extractor.database.repository)
====================================================================
Centraliza operações no PostgreSQL via Connection Pool, Prepared Statements (%s),
UPSERT em lote via execute_batch e verificação de integridade de ingestão.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

from .connection import PostgresConnectionPool
from .schema import (
    INDICES_POR_TABELA,
    MAPA_MATRIZ_FILIAL,
    MAPA_PORTE_EMPRESA,
    MAPA_SITUACAO_CADASTRAL,
    MAPA_TIPO_SOCIO,
    TABELAS_DDL,
    obter_comando_upsert,
    validar_tabela,
)

logger = logging.getLogger("cnpj_extractor.database.repository")


class CNPJRepository:
    def __init__(self, pool: PostgresConnectionPool):
        self.pool = pool

    def inicializar_tabelas(self, tabelas: Optional[List[str]] = None) -> None:
        """Cria as tabelas necessárias no PostgreSQL se ainda não existirem."""
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(TABELAS_DDL["_ingestion_control"])
                tabelas_a_criar = tabelas or list(TABELAS_DDL.keys())
                for nome_tabela in tabelas_a_criar:
                    if nome_tabela in TABELAS_DDL and nome_tabela != "_ingestion_control":
                        validar_tabela(nome_tabela)
                        cursor.execute(TABELAS_DDL[nome_tabela])

    def arquivo_ja_processado(self, nome_arquivo: str) -> bool:
        """Verifica se um arquivo já teve sua conclusão registrada no PostgreSQL."""
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM _ingestion_control WHERE nome_arquivo = %s LIMIT 1;",
                    (nome_arquivo,),
                )
                row = cursor.fetchone()
                return row is not None

    def registrar_conclusao_arquivo(
        self, nome_arquivo: str, mes: str, tabela: str, linhas_processadas: int
    ) -> None:
        """Registra a conclusão do processamento de um arquivo de forma atômica."""
        validar_tabela(tabela)
        sql_upsert = obter_comando_upsert("_ingestion_control")
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_upsert, (nome_arquivo, mes, tabela, linhas_processadas))

    def inserir_lote(self, tabela: str, lote: List[Tuple]) -> int:
        """
        Insere um lote de registros no PostgreSQL via UPSERT com execute_batch,
        garantindo idempotência e alta vazão sem riscos de duplicação em reentregas.
        """
        if not lote:
            return 0
        validar_tabela(tabela)
        sql_upsert = obter_comando_upsert(tabela)

        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                if psycopg2 and hasattr(psycopg2.extras, "execute_batch"):
                    psycopg2.extras.execute_batch(cursor, sql_upsert, lote, page_size=1000)
                else:
                    cursor.executemany(sql_upsert, lote)
        return len(lote)

    def verificar_arquivos_pendentes(self, mes: str, arquivos_esperados: List[str]) -> List[str]:
        """
        Retorna a lista de nomes de arquivos que ainda NÃO constam como concluídos
        na tabela de controle do PostgreSQL para o mês informado.
        """
        if not arquivos_esperados:
            return []

        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT nome_arquivo FROM _ingestion_control WHERE mes = %s AND nome_arquivo = ANY(%s);",
                    (mes, arquivos_esperados),
                )
                arquivos_processados = {row[0] for row in cursor.fetchall()}

        return [arq for arq in arquivos_esperados if arq not in arquivos_processados]

    def todos_arquivos_concluidos(self, mes: str, arquivos_esperados: List[str]) -> bool:
        """Verifica se 100% dos arquivos esperados já foram gravados no banco."""
        pendentes = self.verificar_arquivos_pendentes(mes, arquivos_esperados)
        return len(pendentes) == 0

    def garantir_indices(self, tabelas: Optional[List[str]] = None) -> List[str]:
        """
        Verifica no catálogo do PostgreSQL (pg_indexes) quais índices já existem
        e cria apenas os que estiverem ausentes.
        """
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
                )
                tabelas_no_banco = {row[0] for row in cursor.fetchall()}

                cursor.execute(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'public';"
                )
                indices_existentes = {row[0] for row in cursor.fetchall()}

                indices_criados: List[str] = []
                for tab_nome, indices in INDICES_POR_TABELA.items():
                    if tab_nome in tabelas_no_banco:
                        if tabelas is None or tab_nome in tabelas:
                            for idx_sql in indices:
                                match = re.search(
                                    r"INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON",
                                    idx_sql,
                                    re.IGNORECASE,
                                )
                                idx_name = match.group(1) if match else None
                                if not idx_name or idx_name not in indices_existentes:
                                    cursor.execute(idx_sql)
                                    if idx_name:
                                        indices_existentes.add(idx_name)
                                        indices_criados.append(idx_name)
        return indices_criados

    def contar_linhas(self, tabela: str) -> int:
        """Retorna o total de linhas em uma tabela validada."""
        tab_validada = validar_tabela(tabela)
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {tab_validada};")
                count = cursor.fetchone()[0]
                return count

    def listar_cnaes(self) -> List[Tuple[str, str]]:
        """Retorna todos os CNAEs (código, descrição) ordenados por código."""
        sql = "SELECT codigo, descricao FROM cnaes ORDER BY codigo;"
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()

    def listar_municipios(self, uf: Optional[str] = None) -> List[Tuple[str, str]]:
        """Retorna municípios distintos (código, descrição).
        Se uf for None ou "TODOS", devolve todos os municípios presentes em estabelecimentos.
        Caso contrário filtra por UF usando a coluna est.uf.
        """
        base_sql = (
            "SELECT DISTINCT mun.codigo, mun.descricao"
            " FROM estabelecimentos est"
            " JOIN municipios mun ON est.municipio = mun.codigo"
        )
        params: List[Any] = []
        if uf and uf.upper() != "TODOS":
            sql = base_sql + " WHERE est.uf = %s"
            params.append(uf.upper())
        else:
            sql = "SELECT codigo, descricao FROM municipios ORDER BY codigo;"
        with self.pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params) if params else None)
                return cursor.fetchall()

    def buscar_empresa_detalhada(self, cnpj_input: str) -> Optional[Dict[str, Any]]:
        """Busca os dados consolidados da empresa, estabelecimentos e sócios pelo CNPJ."""
        digitos = "".join(filter(str.isdigit, cnpj_input.strip()))
        if not digitos:
            return None
        cnpj_basico = digitos[:8].zfill(8)

        with self.pool.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor if psycopg2 else None) as cursor:
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
                    WHERE e.cnpj_basico = %s
                    LIMIT 1;
                    """,
                    (cnpj_basico,),
                )
                empresa_row = cursor.fetchone()
                if not empresa_row:
                    return None

                empresa_dict = dict(empresa_row)
                empresa_dict["porte_descricao"] = MAPA_PORTE_EMPRESA.get(
                    empresa_dict.get("porte_empresa"), "Outros"
                )

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
                    WHERE est.cnpj_basico = %s
                    ORDER BY est.identificador_matriz_filial ASC, est.cnpj_ordem ASC;
                    """,
                    (cnpj_basico,),
                )
                estabelecimentos = []
                for row in cursor.fetchall():
                    item = dict(row)
                    item["situacao_descricao"] = MAPA_SITUACAO_CADASTRAL.get(
                        item.get("situacao_cadastral"), "Desconhecida"
                    )
                    item["tipo_unidade"] = MAPA_MATRIZ_FILIAL.get(
                        item.get("identificador_matriz_filial"), "Estabelecimento"
                    )
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
                    WHERE soc.cnpj_basico = %s;
                    """,
                    (cnpj_basico,),
                )
                socios = []
                for row in cursor.fetchall():
                    item = dict(row)
                    item["tipo_socio_descricao"] = MAPA_TIPO_SOCIO.get(
                        item.get("identificador_socio"), "Outros"
                    )
                    socios.append(item)

                empresa_dict["estabelecimentos"] = estabelecimentos
                empresa_dict["socios"] = socios
                return empresa_dict

    def buscar_empresas_por_filtros(
        self,
        termo_busca: Optional[str] = None,
        uf: Optional[str] = None,
        situacao: Optional[str] = None,
        cnae_codigo: Optional[str] = None,
        municipio_codigo: Optional[str] = None,
        limite: int = 50,
    ) -> List[Dict[str, Any]]:
        """Consulta empresas por termo de busca, UF e situação cadastral no PostgreSQL."""
        condicoes = []
        parametros: List[Any] = []

        if termo_busca and termo_busca.strip():
            termo_limpo = f"%{termo_busca.strip().upper()}%"
            condicoes.append("(e.razao_social ILIKE %s OR est.nome_fantasia ILIKE %s)")
            parametros.extend([termo_limpo, termo_limpo])

        if uf and uf.strip() and uf.upper() != "TODOS":
            condicoes.append("est.uf = %s")
            parametros.append(uf.strip().upper())

        if situacao and situacao.strip() and situacao != "TODOS":
            condicoes.append("est.situacao_cadastral = %s")
            parametros.append(situacao.strip())

        if cnae_codigo and cnae_codigo.strip() and cnae_codigo.upper() != "TODOS":
            condicoes.append("est.cnae_fiscal_principal = %s")
            parametros.append(cnae_codigo.strip())

        if municipio_codigo and municipio_codigo.strip() and municipio_codigo.upper() != "TODOS":
            condicoes.append("est.municipio = %s")
            parametros.append(municipio_codigo.strip())

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
            ORDER BY e.capital_social DESC NULLS LAST
            LIMIT %s;
        """
        parametros.append(limite)

        with self.pool.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor if psycopg2 else None) as cursor:
                cursor.execute(sql, tuple(parametros))
                resultados = []
                for r in cursor.fetchall():
                    item = dict(r)
                    item["cnpj_formatado"] = f"{item['cnpj_basico']}/{item['cnpj_ordem']}-{item['cnpj_dv']}"
                    item["situacao_texto"] = MAPA_SITUACAO_CADASTRAL.get(
                        item.get("situacao_cadastral"), "Outros"
                    )
                    resultados.append(item)
                return resultados
