"""
Esquemas e Mapeamentos do Banco de Dados PostgreSQL (cnpj_extractor.database.schema)
===================================================================================
Define DDLs com chaves primárias naturais, tipos monetários NUMERIC(15,2),
whitelist estrita de tabelas autorizadas e comandos de UPSERT (INSERT ... ON CONFLICT DO UPDATE).
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
    "cnaes": "CREATE TABLE IF NOT EXISTS cnaes (codigo VARCHAR(10) PRIMARY KEY, descricao TEXT);",
    "motivos": "CREATE TABLE IF NOT EXISTS motivos (codigo VARCHAR(10) PRIMARY KEY, descricao TEXT);",
    "municipios": "CREATE TABLE IF NOT EXISTS municipios (codigo VARCHAR(10) PRIMARY KEY, descricao TEXT);",
    "naturezas_juridicas": "CREATE TABLE IF NOT EXISTS naturezas_juridicas (codigo VARCHAR(10) PRIMARY KEY, descricao TEXT);",
    "paises": "CREATE TABLE IF NOT EXISTS paises (codigo VARCHAR(10) PRIMARY KEY, descricao TEXT);",
    "qualificacoes_socios": "CREATE TABLE IF NOT EXISTS qualificacoes_socios (codigo VARCHAR(10) PRIMARY KEY, descricao TEXT);",
    "empresas": """
        CREATE TABLE IF NOT EXISTS empresas (
            cnpj_basico VARCHAR(8) PRIMARY KEY,
            razao_social TEXT,
            codigo_natureza_juridica VARCHAR(10),
            qualificacao_responsavel VARCHAR(10),
            capital_social NUMERIC(15, 2),
            porte_empresa VARCHAR(5),
            ente_federativo_responsavel TEXT
        );
    """,
    "estabelecimentos": """
        CREATE TABLE IF NOT EXISTS estabelecimentos (
            cnpj_basico VARCHAR(8) NOT NULL,
            cnpj_ordem VARCHAR(4) NOT NULL,
            cnpj_dv VARCHAR(2) NOT NULL,
            identificador_matriz_filial VARCHAR(2),
            nome_fantasia TEXT,
            situacao_cadastral VARCHAR(2),
            data_situacao_cadastral VARCHAR(8),
            motivo_situacao_cadastral VARCHAR(10),
            nome_cidade_exterior TEXT,
            pais VARCHAR(10),
            data_inicio_atividade VARCHAR(8),
            cnae_fiscal_principal VARCHAR(10),
            cnae_fiscal_secundaria TEXT,
            tipo_logradouro VARCHAR(30),
            logradouro TEXT,
            numero TEXT,
            complemento TEXT,
            bairro TEXT,
            cep VARCHAR(8),
            uf VARCHAR(2),
            municipio VARCHAR(10),
            ddd_1 VARCHAR(5),
            telefone_1 VARCHAR(15),
            ddd_2 VARCHAR(5),
            telefone_2 VARCHAR(15),
            ddd_fax VARCHAR(5),
            fax VARCHAR(15),
            correio_eletronico TEXT,
            situacao_especial TEXT,
            data_situacao_especial VARCHAR(8),
            PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv)
        );
    """,
    "simples": """
        CREATE TABLE IF NOT EXISTS simples (
            cnpj_basico VARCHAR(8) PRIMARY KEY,
            opcao_simples VARCHAR(2),
            data_opcao_simples VARCHAR(8),
            data_exclusao_simples VARCHAR(8),
            opcao_mei VARCHAR(2),
            data_opcao_mei VARCHAR(8),
            data_exclusao_mei VARCHAR(8)
        );
    """,
    "socios": """
        CREATE TABLE IF NOT EXISTS socios (
            cnpj_basico VARCHAR(8) NOT NULL,
            identificador_socio VARCHAR(2) NOT NULL,
            nome_socio_razao_social TEXT NOT NULL,
            cnpj_cpf_socio TEXT,
            qualificacao_socio VARCHAR(10) NOT NULL,
            data_entrada_sociedade VARCHAR(8) NOT NULL DEFAULT '',
            pais VARCHAR(10),
            representante_legal VARCHAR(15),
            nome_do_representante TEXT,
            qualificacao_representante_legal VARCHAR(10),
            faixa_etaria VARCHAR(2),
            PRIMARY KEY (cnpj_basico, identificador_socio, nome_socio_razao_social, qualificacao_socio, data_entrada_sociedade)
        );
    """,
    "_ingestion_control": """
        CREATE TABLE IF NOT EXISTS _ingestion_control (
            nome_arquivo VARCHAR(100) PRIMARY KEY,
            mes VARCHAR(10) NOT NULL,
            tabela VARCHAR(50) NOT NULL,
            linhas_processadas BIGINT NOT NULL,
            data_conclusao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
}

INDICES_POR_TABELA: Dict[str, List[str]] = {
    "empresas": [
        "CREATE INDEX IF NOT EXISTS idx_empresas_razao ON empresas (razao_social);",
    ],
    "estabelecimentos": [
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnpj_basico ON estabelecimentos (cnpj_basico);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_uf ON estabelecimentos (uf);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnae ON estabelecimentos (cnae_fiscal_principal);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_situacao ON estabelecimentos (situacao_cadastral);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_nome_fantasia ON estabelecimentos (nome_fantasia);",
        "CREATE INDEX IF NOT EXISTS idx_estabelecimentos_municipio ON estabelecimentos (municipio);",
    ],
    "socios": [
        "CREATE INDEX IF NOT EXISTS idx_socios_cnpj_basico ON socios (cnpj_basico);",
    ],
    "simples": [
        "CREATE INDEX IF NOT EXISTS idx_simples_cnpj_basico ON simples (cnpj_basico);",
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


def obter_comando_upsert(nome_tabela: str) -> str:
    """
    Retorna o comando SQL de UPSERT parametrizado com placeholders %s para o driver psycopg2.
    Garante idempotência absoluta mesmo sob reentregas e reprocessamentos concorrentes.
    """
    tabela = validar_tabela(nome_tabela)

    if tabela in {"cnaes", "motivos", "municipios", "naturezas_juridicas", "paises", "qualificacoes_socios"}:
        return f"""
            INSERT INTO {tabela} (codigo, descricao)
            VALUES (%s, %s)
            ON CONFLICT (codigo) DO UPDATE SET
                descricao = EXCLUDED.descricao;
        """

    elif tabela == "empresas":
        return """
            INSERT INTO empresas (
                cnpj_basico, razao_social, codigo_natureza_juridica, qualificacao_responsavel,
                capital_social, porte_empresa, ente_federativo_responsavel
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cnpj_basico) DO UPDATE SET
                razao_social = EXCLUDED.razao_social,
                codigo_natureza_juridica = EXCLUDED.codigo_natureza_juridica,
                qualificacao_responsavel = EXCLUDED.qualificacao_responsavel,
                capital_social = EXCLUDED.capital_social,
                porte_empresa = EXCLUDED.porte_empresa,
                ente_federativo_responsavel = EXCLUDED.ente_federativo_responsavel;
        """

    elif tabela == "estabelecimentos":
        return """
            INSERT INTO estabelecimentos (
                cnpj_basico, cnpj_ordem, cnpj_dv, identificador_matriz_filial, nome_fantasia,
                situacao_cadastral, data_situacao_cadastral, motivo_situacao_cadastral,
                nome_cidade_exterior, pais, data_inicio_atividade, cnae_fiscal_principal,
                cnae_fiscal_secundaria, tipo_logradouro, logradouro, numero, complemento,
                bairro, cep, uf, municipio, ddd_1, telefone_1, ddd_2, telefone_2,
                ddd_fax, fax, correio_eletronico, situacao_especial, data_situacao_especial
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (cnpj_basico, cnpj_ordem, cnpj_dv) DO UPDATE SET
                identificador_matriz_filial = EXCLUDED.identificador_matriz_filial,
                nome_fantasia = EXCLUDED.nome_fantasia,
                situacao_cadastral = EXCLUDED.situacao_cadastral,
                data_situacao_cadastral = EXCLUDED.data_situacao_cadastral,
                motivo_situacao_cadastral = EXCLUDED.motivo_situacao_cadastral,
                nome_cidade_exterior = EXCLUDED.nome_cidade_exterior,
                pais = EXCLUDED.pais,
                data_inicio_atividade = EXCLUDED.data_inicio_atividade,
                cnae_fiscal_principal = EXCLUDED.cnae_fiscal_principal,
                cnae_fiscal_secundaria = EXCLUDED.cnae_fiscal_secundaria,
                tipo_logradouro = EXCLUDED.tipo_logradouro,
                logradouro = EXCLUDED.logradouro,
                numero = EXCLUDED.numero,
                complemento = EXCLUDED.complemento,
                bairro = EXCLUDED.bairro,
                cep = EXCLUDED.cep,
                uf = EXCLUDED.uf,
                municipio = EXCLUDED.municipio,
                ddd_1 = EXCLUDED.ddd_1,
                telefone_1 = EXCLUDED.telefone_1,
                ddd_2 = EXCLUDED.ddd_2,
                telefone_2 = EXCLUDED.telefone_2,
                ddd_fax = EXCLUDED.ddd_fax,
                fax = EXCLUDED.fax,
                correio_eletronico = EXCLUDED.correio_eletronico,
                situacao_especial = EXCLUDED.situacao_especial,
                data_situacao_especial = EXCLUDED.data_situacao_especial;
        """

    elif tabela == "simples":
        return """
            INSERT INTO simples (
                cnpj_basico, opcao_simples, data_opcao_simples, data_exclusao_simples,
                opcao_mei, data_opcao_mei, data_exclusao_mei
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cnpj_basico) DO UPDATE SET
                opcao_simples = EXCLUDED.opcao_simples,
                data_opcao_simples = EXCLUDED.data_opcao_simples,
                data_exclusao_simples = EXCLUDED.data_exclusao_simples,
                opcao_mei = EXCLUDED.opcao_mei,
                data_opcao_mei = EXCLUDED.data_opcao_mei,
                data_exclusao_mei = EXCLUDED.data_exclusao_mei;
        """

    elif tabela == "socios":
        return """
            INSERT INTO socios (
                cnpj_basico, identificador_socio, nome_socio_razao_social, cnpj_cpf_socio,
                qualificacao_socio, data_entrada_sociedade, pais, representante_legal,
                nome_do_representante, qualificacao_representante_legal, faixa_etaria
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cnpj_basico, identificador_socio, nome_socio_razao_social, qualificacao_socio, data_entrada_sociedade) DO UPDATE SET
                cnpj_cpf_socio = EXCLUDED.cnpj_cpf_socio,
                pais = EXCLUDED.pais,
                representante_legal = EXCLUDED.representante_legal,
                nome_do_representante = EXCLUDED.nome_do_representante,
                qualificacao_representante_legal = EXCLUDED.qualificacao_representante_legal,
                faixa_etaria = EXCLUDED.faixa_etaria;
        """

    elif tabela == "_ingestion_control":
        return """
            INSERT INTO _ingestion_control (
                nome_arquivo, mes, tabela, linhas_processadas, data_conclusao
            ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (nome_arquivo) DO UPDATE SET
                mes = EXCLUDED.mes,
                tabela = EXCLUDED.tabela,
                linhas_processadas = EXCLUDED.linhas_processadas,
                data_conclusao = CURRENT_TIMESTAMP;
        """

    raise ValueError(f"Tabela desconhecida para comando UPSERT: {nome_tabela}")
