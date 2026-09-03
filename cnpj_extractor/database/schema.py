"""
Esquemas e Mapeamentos do Banco de Dados (cnpj_extractor.database.schema)
========================================================================
Define DDLs com chaves primárias para inserções idempotentes (INSERT OR REPLACE),
whitelist estrita de tabelas autorizadas e mapeamento de índices otimizados.
"""

from typing import Dict, List, Optional, Set

# Mapeamentos oficiais de códigos da Receita Federal para legendas legíveis
MAPA_SITUACAO_CADASTRAL = {
    "01": "Nula",
    "02": "Ativa",
    "03": "Suspensa",
    "04": "Inapta",
    "08": "Baixada",
}

MAPA_PORTE_EMPRESA = {
    "00": "Não Informado",
    "01": "Microempresa (ME)",
    "03": "Empresa de Pequeno Porte (EPP)",
    "05": "Demais",
}

MAPA_MATRIZ_FILIAL = {
    "1": "Matriz",
    "2": "Filial",
}

MAPA_TIPO_SOCIO = {
    "1": "Pessoa Jurídica",
    "2": "Pessoa Física",
    "3": "Estrangeiro",
}

# Whitelist estrita de tabelas autorizadas contra SQL Injection
TABELAS_PERMITIDAS: Set[str] = {
    "cnaes",
    "motivos",
    "municipios",
    "naturezas_juridicas",
    "paises",
    "qualificacoes_socios",
    "empresas",
    "estabelecimentos",
    "simples",
    "socios",
    "_ingestion_control",
}

GRUPOS_TABELAS: Dict[str, List[str]] = {
    "lookup": ["cnaes", "motivos", "municipios", "naturezas_juridicas", "paises", "qualificacoes_socios"],
    "empresas": ["empresas"],
    "estabelecimentos": ["estabelecimentos"],
    "socios": ["socios"],
    "simples": ["simples"],
    "all": [
        "cnaes",
        "motivos",
        "municipios",
        "naturezas_juridicas",
        "paises",
        "qualificacoes_socios",
        "empresas",
        "estabelecimentos",
        "socios",
        "simples",
    ],
}

ARQUIVO_PARA_TABELA: Dict[str, str] = {
    "cnaes": "cnaes",
    "motivos": "motivos",
    "municipios": "municipios",
    "naturezas": "naturezas_juridicas",
    "paises": "paises",
    "qualificacoes": "qualificacoes_socios",
    "empresas": "empresas",
    "estabelecimentos": "estabelecimentos",
    "simples": "simples",
    "socios": "socios",
}

TABELAS_DDL: Dict[str, str] = {
    "cnaes": "CREATE TABLE IF NOT EXISTS cnaes (codigo TEXT PRIMARY KEY, descricao TEXT);",
    "motivos": "CREATE TABLE IF NOT EXISTS motivos (codigo TEXT PRIMARY KEY, descricao TEXT);",
    "municipios": "CREATE TABLE IF NOT EXISTS municipios (codigo TEXT PRIMARY KEY, descricao TEXT);",
    "naturezas_juridicas": "CREATE TABLE IF NOT EXISTS naturezas_juridicas (codigo TEXT PRIMARY KEY, descricao TEXT);",
    "paises": "CREATE TABLE IF NOT EXISTS paises (codigo TEXT PRIMARY KEY, descricao TEXT);",
    "qualificacoes_socios": "CREATE TABLE IF NOT EXISTS qualificacoes_socios (codigo TEXT PRIMARY KEY, descricao TEXT);",
    "empresas": """
        CREATE TABLE IF NOT EXISTS empresas (
            cnpj_basico TEXT PRIMARY KEY,
            razao_social TEXT,
            codigo_natureza_juridica TEXT,
            qualificacao_responsavel TEXT,
            capital_social REAL,
            porte_empresa TEXT,
            ente_federativo_responsavel TEXT
        );
    """,
    "estabelecimentos": """
        CREATE TABLE IF NOT EXISTS estabelecimentos (
            cnpj_basico TEXT,
            cnpj_ordem TEXT,
            cnpj_dv TEXT,
            identificador_matriz_filial TEXT,
            nome_fantasia TEXT,
            situacao_cadastral TEXT,
            data_situacao_cadastral TEXT,
            motivo_situacao_cadastral TEXT,
            nome_cidade_exterior TEXT,
            pais TEXT,
            data_inicio_atividade TEXT,
            cnae_fiscal_principal TEXT,
            cnae_fiscal_secundaria TEXT,
            tipo_logradouro TEXT,
            logradouro TEXT,
            numero TEXT,
            complemento TEXT,
            bairro TEXT,
            cep TEXT,
            uf TEXT,
            municipio TEXT,
            ddd_1 TEXT,
            telefone_1 TEXT,
            ddd_2 TEXT,
            telefone_2 TEXT,
            ddd_fax TEXT,
            fax TEXT,
            correio_eletronico TEXT,
            situacao_especial TEXT,
            data_situacao_especial TEXT,
            PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv)
        );
    """,
    "simples": """
        CREATE TABLE IF NOT EXISTS simples (
            cnpj_basico TEXT PRIMARY KEY,
            opcao_simples TEXT,
            data_opcao_simples TEXT,
            data_exclusao_simples TEXT,
            opcao_mei TEXT,
            data_opcao_mei TEXT,
            data_exclusao_mei TEXT
        );
    """,
    "socios": """
        CREATE TABLE IF NOT EXISTS socios (
            cnpj_basico TEXT,
            identificador_socio TEXT,
            nome_socio_razao_social TEXT,
            cnpj_cpf_socio TEXT,
            qualificacao_socio TEXT,
            data_entrada_sociedade TEXT,
            pais TEXT,
            representante_legal TEXT,
            nome_do_representante TEXT,
            qualificacao_representante_legal TEXT,
            faixa_etaria TEXT,
            PRIMARY KEY (cnpj_basico, identificador_socio, nome_socio_razao_social, qualificacao_socio)
        );
    """,
    "_ingestion_control": """
        CREATE TABLE IF NOT EXISTS _ingestion_control (
            nome_arquivo TEXT PRIMARY KEY,
            mes TEXT,
            tabela TEXT,
            linhas_processadas INTEGER,
            data_conclusao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
}

INDICES_POR_TABELA: Dict[str, List[str]] = {
    "empresas": [
        "CREATE INDEX IF NOT EXISTS idx_empresas_cnpj ON empresas (cnpj_basico);",
    ],
    "estabelecimentos": [
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnpj ON estabelecimentos (cnpj_basico);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnpj_completo ON estabelecimentos (cnpj_basico, cnpj_ordem, cnpj_dv);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_uf ON estabelecimentos (uf);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnae ON estabelecimentos (cnae_fiscal_principal);",
    ],
    "socios": [
        "CREATE INDEX IF NOT EXISTS idx_socios_cnpj ON socios (cnpj_basico);",
    ],
    "simples": [
        "CREATE INDEX IF NOT EXISTS idx_simples_cnpj ON simples (cnpj_basico);",
    ],
}

INDICES_DDL: List[str] = [idx for indices in INDICES_POR_TABELA.values() for idx in indices]


def identificar_tabela_por_arquivo(nome_arquivo: str) -> Optional[str]:
    nome_limpo = nome_arquivo.lower().replace(".zip", "")
    for prefixo, tabela in ARQUIVO_PARA_TABELA.items():
        if nome_limpo.startswith(prefixo):
            return tabela
    return None


def validar_tabela(nome_tabela: str) -> str:
    nome_normalizado = nome_tabela.lower().strip()
    if nome_normalizado not in TABELAS_PERMITIDAS:
        raise ValueError(f"Tabela não permitida: {nome_tabela}")
    return nome_normalizado


def obter_comando_insert(nome_tabela: str) -> str:
    """
    Retorna o comando parametrizado INSERT OR REPLACE para garantir idempotência,
    evitando duplicação de dados caso um arquivo seja reprocessado após falha parcial.
    """
    tabela = validar_tabela(nome_tabela)
    contagem_colunas = {
        "cnaes": 2, "motivos": 2, "municipios": 2, "naturezas_juridicas": 2, "paises": 2,
        "qualificacoes_socios": 2, "empresas": 7, "estabelecimentos": 30, "simples": 7,
        "socios": 11, "_ingestion_control": 4,
    }
    n_cols = contagem_colunas[tabela]
    placeholders = ", ".join(["?"] * n_cols)
    return f"INSERT OR REPLACE INTO {tabela} VALUES ({placeholders});"
