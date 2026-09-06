"""
Módulo de Extração de Arquivos ZIP via Arquivo Temporário (cnpj_extractor.extraction.zip_extractor)
================================================================================================
Baixa o arquivo remoto em blocos para disco temporário e abre o CSV interno usando zipfile.ZipFile,
garantindo validação automática de integridade (CRC32), suporte nativo a ZIP64 e limpeza garantida.
"""

from contextlib import contextmanager
import io
import logging
import os
import shutil
import tempfile
from typing import BinaryIO, Generator
import zipfile

logger = logging.getLogger("cnpj_extractor.zip_extractor")


@contextmanager
def abrir_csv_do_zip_remoto(
    raw_http_stream: BinaryIO,
    encoding: str = "latin1",
    chunk_size: int = 64 * 1024,
) -> Generator[io.TextIOWrapper, None, None]:
    """
    Baixa o stream HTTP em blocos para um arquivo temporário em disco e fornece
    um TextIOWrapper do arquivo CSV interno para iteração de linhas.

    Garantias:
    - O arquivo temporário é sempre removido no bloco finally, mesmo em caso de erro.
    - Validação de integridade CRC32 nativa executada pelo zipfile (estoura exceção se truncado/corrompido).
    - Suporte nativo e transparente a arquivos ZIP64 (>4GB) e Data Descriptors.
    - Validação explícita de entradas internas no ZIP.
    """
    temp_path = None

    try:
        # 1. Copia o stream HTTP em blocos para o arquivo temporário em disco
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            temp_path = tmp.name
            shutil.copyfileobj(raw_http_stream, tmp, length=chunk_size)

        # 2. Abre o arquivo ZIP com a biblioteca padrão do Python
        with zipfile.ZipFile(temp_path, "r", allowZip64=True) as zf:
            namelist = zf.namelist()
            if not namelist:
                raise zipfile.BadZipFile(f"O arquivo ZIP '{temp_path}' está vazio e não contém entradas internas.")

            # Filtra diretórios e metadados de sistema (ex: __MACOSX)
            arquivos_internos = [
                nome for nome in namelist
                if not nome.endswith("/") and not nome.startswith("__MACOSX")
            ]

            if not arquivos_internos:
                raise zipfile.BadZipFile(f"Nenhum arquivo encontrado no ZIP '{temp_path}'. Entradas: {namelist}")

            # Identifica o arquivo de dados esperado
            if len(arquivos_internos) == 1:
                entrada_alvo = arquivos_internos[0]
            else:
                # Prioridade 1: Arquivos explicitamente com extensão .csv
                csvs = [n for n in arquivos_internos if n.lower().endswith(".csv")]
                if len(csvs) == 1:
                    entrada_alvo = csvs[0]
                elif len(csvs) > 1:
                    # Se houver múltiplos CSVs, seleciona o de maior tamanho
                    entrada_alvo = max(csvs, key=lambda n: zf.getinfo(n).file_size)
                    logger.warning(
                        f"Múltiplos arquivos .csv encontrados no ZIP ({csvs}). "
                        f"Selecionado o de maior tamanho: '{entrada_alvo}'."
                    )
                else:
                    # Prioridade 2: Arquivos de dados sem extensão ou extensões da Receita, ignorando documentações
                    candidatos = [
                        n for n in arquivos_internos
                        if not n.lower().endswith((".txt", ".pdf", ".md", ".json"))
                    ]
                    if candidatos:
                        entrada_alvo = max(candidatos, key=lambda n: zf.getinfo(n).file_size)
                    else:
                        entrada_alvo = max(arquivos_internos, key=lambda n: zf.getinfo(n).file_size)

            # 3. Abre a entrada em modo binário e envolve em TextIOWrapper
            with zf.open(entrada_alvo, "r") as binary_csv_stream:
                text_stream = io.TextIOWrapper(
                    binary_csv_stream,
                    encoding=encoding,
                    errors="replace",
                    newline="",
                )
                yield text_stream

    finally:
        # 4. Garante que o arquivo temporário seja SEMPRE apagado do disco
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Não foi possível remover o arquivo temporário '{temp_path}': {e}")

