"""
Parser e Sanitização de CSV em Streaming (cnpj_extractor.extraction.parser)
==========================================================================
Fornece tratamento explícito coluna a coluna para todas as tabelas oficiais,
sanitização de valores monetários (float) e captura resiliente de erros em CSV.
"""

import csv
import io
import logging
from typing import Dict, Generator, List, Optional, Tuple

logger = logging.getLogger("cnpj_extractor.parser")

SCHEMA_COLUNAS: Dict[str, int] = {
    "empresas": 7,
    "estabelecimentos": 30,
    "socios": 11,
    "simples": 7,
    "cnaes": 2,
    "motivos": 2,
    "municipios": 2,
    "naturezas_juridicas": 2,
    "paises": 2,
    "qualificacoes_socios": 2,
}


# Remove bytes nulos e espaços nas extremidades
def _sanitizar_texto(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    limpo = str(valor).replace("\x00", "").strip()
    return limpo if limpo else None


# Converte o formato do real pro formato python (retorna None se inválido ou vazio)
def _sanitizar_float(valor: Optional[str]) -> Optional[float]:
    if not valor:
        return None
    limpo = str(valor).replace("\x00", "").strip().replace(".", "").replace(",", ".")
    if not limpo:
        return None
    try:
        return float(limpo)
    except ValueError:
        return None


# Normaliza tipos e estrutura coluna a coluna para cada tabela
def normalizar_linha(
    tabela: str,
    row: List[str],
    expected_cols: Optional[int] = None,
) -> Optional[Tuple]:
    if not row:
        return None

    tabela_lower = tabela.lower().strip()
    if tabela_lower not in SCHEMA_COLUNAS:
        raise ValueError(
            f"Tabela desconhecida: '{tabela}'. Tabelas válidas: {sorted(list(SCHEMA_COLUNAS.keys()))}"
        )

    n_cols = expected_cols if expected_cols is not None else SCHEMA_COLUNAS[tabela_lower]

    if len(row) < n_cols:
        row = row + [""] * (n_cols - len(row))
    elif len(row) > n_cols:
        row = row[:n_cols]

    if tabela_lower == "empresas":
        return (
            _sanitizar_texto(row[0]),  # cnpj_basico
            _sanitizar_texto(row[1]),  # razao_social
            _sanitizar_texto(row[2]),  # codigo_natureza_juridica
            _sanitizar_texto(row[3]),  # qualificacao_responsavel
            _sanitizar_float(row[4]),  # capital_social
            _sanitizar_texto(row[5]),  # porte_empresa
            _sanitizar_texto(row[6]),  # ente_federativo_responsavel
        )

    elif tabela_lower == "estabelecimentos":
        uf = _sanitizar_texto(row[19])
        email = _sanitizar_texto(row[27])
        return (
            _sanitizar_texto(row[0]),   # cnpj_basico
            _sanitizar_texto(row[1]),   # cnpj_ordem
            _sanitizar_texto(row[2]),   # cnpj_dv
            _sanitizar_texto(row[3]),   # identificador_matriz_filial
            _sanitizar_texto(row[4]),   # nome_fantasia
            _sanitizar_texto(row[5]),   # situacao_cadastral
            _sanitizar_texto(row[6]),   # data_situacao_cadastral
            _sanitizar_texto(row[7]),   # motivo_situacao_cadastral
            _sanitizar_texto(row[8]),   # nome_cidade_exterior
            _sanitizar_texto(row[9]),   # pais
            _sanitizar_texto(row[10]),  # data_inicio_atividade
            _sanitizar_texto(row[11]),  # cnae_fiscal_principal
            _sanitizar_texto(row[12]),  # cnae_fiscal_secundaria
            _sanitizar_texto(row[13]),  # tipo_logradouro
            _sanitizar_texto(row[14]),  # logradouro
            _sanitizar_texto(row[15]),  # numero
            _sanitizar_texto(row[16]),  # complemento
            _sanitizar_texto(row[17]),  # bairro
            _sanitizar_texto(row[18]),  # cep
            uf.upper() if uf else None, # uf
            _sanitizar_texto(row[20]),  # municipio
            _sanitizar_texto(row[21]),  # ddd_1
            _sanitizar_texto(row[22]),  # telefone_1
            _sanitizar_texto(row[23]),  # ddd_2
            _sanitizar_texto(row[24]),  # telefone_2
            _sanitizar_texto(row[25]),  # ddd_fax
            _sanitizar_texto(row[26]),  # fax
            email.lower() if email else None,  # correio_eletronico
            _sanitizar_texto(row[28]),  # situacao_especial
            _sanitizar_texto(row[29]),  # data_situacao_especial
        )

    elif tabela_lower == "socios":
        return (
            _sanitizar_texto(row[0]),   # cnpj_basico
            _sanitizar_texto(row[1]),   # identificador_socio
            _sanitizar_texto(row[2]),   # nome_socio_razao_social
            _sanitizar_texto(row[3]),   # cnpj_cpf_socio
            _sanitizar_texto(row[4]),   # qualificacao_socio
            _sanitizar_texto(row[5]),   # data_entrada_sociedade
            _sanitizar_texto(row[6]),   # pais
            _sanitizar_texto(row[7]),   # representante_legal
            _sanitizar_texto(row[8]),   # nome_do_representante
            _sanitizar_texto(row[9]),   # qualificacao_representante_legal
            _sanitizar_texto(row[10]),  # faixa_etaria
        )

    elif tabela_lower == "simples":
        return (
            _sanitizar_texto(row[0]),  # cnpj_basico
            _sanitizar_texto(row[1]),  # opcao_simples
            _sanitizar_texto(row[2]),  # data_opcao_simples
            _sanitizar_texto(row[3]),  # data_exclusao_simples
            _sanitizar_texto(row[4]),  # opcao_mei
            _sanitizar_texto(row[5]),  # data_opcao_mei
            _sanitizar_texto(row[6]),  # data_exclusao_mei
        )

    elif tabela_lower in {"cnaes", "motivos", "municipios", "naturezas_juridicas", "paises", "qualificacoes_socios"}:
        return (
            _sanitizar_texto(row[0]),  # codigo
            _sanitizar_texto(row[1]),  # descricao
        )

    raise ValueError(f"Tabela desconhecida: '{tabela}'")


# Filtra por UF e produz uma tupla por streaming com resiliência a falhas de linha
def iterar_linhas_csv(
    text_stream: io.TextIOBase,
    tabela: str,
    filtro_uf: Optional[str] = None,
    limite: Optional[int] = None,
) -> Generator[Tuple, None, None]:
    tabela_lower = tabela.lower().strip()
    if tabela_lower not in SCHEMA_COLUNAS:
        raise ValueError(f"Tabela desconhecida para iteração: '{tabela}'")

    expected_cols = SCHEMA_COLUNAS[tabela_lower]

    reader = csv.reader(
        text_stream,
        delimiter=";",
        quotechar='"',
        doublequote=True,
        skipinitialspace=True,
    )

    uf_filtro_normalizada = filtro_uf.upper().strip() if filtro_uf else None
    linhas_geradas = 0
    num_linha = 0

    while True:
        try:
            raw_row = next(reader)
            num_linha += 1
        except StopIteration:
            break
        except csv.Error as err:
            logger.warning(
                f"Erro de formato CSV na linha {num_linha + 1} da tabela {tabela}: {err}. Pulando linha."
            )
            continue
        except UnicodeDecodeError as err:
            logger.warning(
                f"Erro de codificação na linha {num_linha + 1} da tabela {tabela}: {err}. Pulando linha."
            )
            continue
        except Exception as err:
            logger.warning(
                f"Erro inesperado ao ler linha {num_linha + 1} da tabela {tabela}: {err}. Pulando linha."
            )
            continue

        if not raw_row or (len(raw_row) == 1 and not (raw_row[0] or "").strip()):
            continue

        if tabela_lower == "estabelecimentos" and uf_filtro_normalizada:
            if len(raw_row) <= 19:
                continue
            uf_linha = (raw_row[19] or "").strip().upper()
            if uf_linha != uf_filtro_normalizada:
                continue

        try:
            tupla_normalizada = normalizar_linha(tabela_lower, raw_row, expected_cols)
            if tupla_normalizada is not None:
                yield tupla_normalizada
                linhas_geradas += 1

                if limite is not None and linhas_geradas >= limite:
                    break
        except Exception as err:
            logger.warning(
                f"Falha ao normalizar registro na linha {num_linha} da tabela {tabela}: {err}. Pulando registro."
            )
            continue


def gerar_lotes_dados(
    gerador_linhas: Generator[Tuple, None, None],
    batch_size: int = 20000,
) -> Generator[List[Tuple], None, None]:
    lote = []
    for linha in gerador_linhas:
        lote.append(linha)
        if len(lote) >= batch_size:
            yield lote
            lote = []
    if lote:
        yield lote
