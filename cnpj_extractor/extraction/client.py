"""
Cliente WebDAV / HTTP da Receita Federal (cnpj_extractor.extraction.client)
==========================================================================
Gerencia a comunicação segura com o Nextcloud público da Receita Federal,
tratando erros HTTP (401, 404, 500), falhas de rede, timeouts e parsing XML.
"""

import base64
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import re
import ssl
from typing import Generator, List, Optional
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ..config import Config

logger = logging.getLogger("cnpj_extractor.client")


@dataclass
class ArquivoRemoto:
    """Representa um arquivo ZIP remoto no repositório da Receita Federal."""
    nome: str
    tamanho_bytes: int
    url: str
    mes: str

    @property
    def tamanho_mb(self) -> float:
        return self.tamanho_bytes / (1024 * 1024)

    @property
    def tamanho_formatado(self) -> str:
        if self.tamanho_bytes < 1024 * 1024:
            return f"{self.tamanho_bytes / 1024:.1f} KB"
        elif self.tamanho_bytes < 1024 * 1024 * 1024:
            return f"{self.tamanho_mb:.1f} MB"
        else:
            return f"{self.tamanho_bytes / (1024 * 1024 * 1024):.2f} GB"


class ReceitaFederalClient:
    """
    Cliente para integração WebDAV/HTTP com a base de dados abertos da Receita Federal.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.carregar()
        self._auth_header = self._gerar_auth_header()
        self._ssl_ctx = self._criar_ssl_context()

    def _gerar_auth_header(self) -> str:
        """Autenticação WebDAV: o token do link público vira o usuário, sem senha."""
        token_limpo = (self.config.share_token or "").strip()
        if not token_limpo:
            raise ValueError("Token de compartilhamento da Receita Federal não configurado.")
        auth_bytes = f"{token_limpo}:".encode("utf-8")
        b64 = base64.b64encode(auth_bytes).decode("ascii")
        return f"Basic {b64}"

    def _criar_ssl_context(self) -> ssl.SSLContext:
        """Cria contexto SSL padrão com validação de certificados do sistema."""
        return ssl.create_default_context()

    def _executar_propfind(self, path_relativo: str = "") -> ET.Element:
        """
        Executa requisição WebDAV PROPFIND e devolve o XML parseado.
        Trata erros HTTP (401, 404, 503), falhas de conexão de rede e XML corrompido.
        """
        path_limpo = path_relativo.strip("/")
        if path_limpo:
            url = f"{self.config.webdav_base_url}/{urllib.parse.quote(path_limpo)}/"
        else:
            url = f"{self.config.webdav_base_url}/"

        req = urllib.request.Request(url, method="PROPFIND")
        req.add_header("User-Agent", self.config.user_agent)
        req.add_header("Authorization", self._auth_header)
        req.add_header("Depth", "1")

        try:
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=self.config.timeout_seconds) as resp:
                data = resp.read()
                if not data:
                    raise RuntimeError(f"Resposta vazia recebida do servidor WebDAV para: {url}")
                try:
                    return ET.fromstring(data)
                except ET.ParseError as pe:
                    logger.error(f"Erro ao interpretar resposta XML do WebDAV ({url}): {pe}")
                    raise RuntimeError(f"Formato XML inválido retornado pelo servidor da Receita: {pe}") from pe

        except urllib.error.HTTPError as http_err:
            if http_err.code == 401:
                logger.error("Erro 401: Token da Receita Federal inválido ou expirado.")
                raise PermissionError(
                    f"Falha na verificação de autenticação "
                ) from http_err
            elif http_err.code == 404:
                logger.error(f"Erro 404: Recurso não encontrado ({url}).")
                raise FileNotFoundError(
                    f"O caminho '{path_relativo}' não foi encontrado no servidor da Receita (HTTP 404)."
                ) from http_err
            else:
                logger.error(f"Erro HTTP {http_err.code} ao consultar WebDAV ({url}): {http_err.reason}")
                raise ConnectionError(
                    f"Erro no servidor da Receita Federal (HTTP {http_err.code}: {http_err.reason}) ao acessar {url}"
                ) from http_err

        except urllib.error.URLError as url_err:
            logger.error(f"Falha de conexão com a Receita Federal ({url}): {url_err.reason}")
            raise ConnectionError(
                f"Não foi possível conectar ao servidor da Receita Federal ({url}): {url_err.reason}. "
                f"Verifique sua conexão com a internet e resolução DNS."
            ) from url_err

        except TimeoutError as timeout_err:
            logger.error(f"Timeout ao consultar WebDAV ({url}) após {self.config.timeout_seconds}s.")
            raise TimeoutError(
                f"Tempo limite de resposta excedido ({self.config.timeout_seconds}s) ao consultar a Receita Federal."
            ) from timeout_err

    def listar_meses_disponiveis(self) -> List[str]:
        """
        Descobre e lista todos os meses (YYYY-MM) disponíveis no repositório da Receita.
        Retorna ordenado cronologicamente de forma decrescente (mais recente primeiro).
        """
        root = self._executar_propfind("")
        meses = []
        for response_elem in root.findall("{DAV:}response"):
            href = response_elem.findtext("{DAV:}href") or ""
            match = re.search(r"/(\d{4}-\d{2})/?$", href)
            if match:
                meses.append(match.group(1))

        meses_unicos = sorted(list(set(meses)), reverse=True)
        if not meses_unicos:
            logger.warning("Nenhum mês no formato AAAA-MM foi encontrado na resposta do WebDAV.")
        return meses_unicos

    def obter_mes_mais_recente(self) -> str:
        """Obtém o mês mais recente disponível ou lança erro explicativo."""
        meses = self.listar_meses_disponiveis()
        if not meses:
            raise RuntimeError(
                "Nenhum mês de dados de CNPJ foi encontrado no repositório da Receita Federal. "
                "Verifique se o token de compartilhamento está correto e ativo."
            )
        return meses[0]

    def listar_arquivos(self, mes: str) -> List[ArquivoRemoto]:
        """
        Lista todos os arquivos ZIP disponíveis para o mês informado.
        """
        if not mes or not mes.strip():
            raise ValueError("O parâmetro 'mes' não pode ser vazio.")

        mes_limpo = mes.strip()
        if mes_limpo == "latest":
            mes_limpo = self.obter_mes_mais_recente()

        # Validação do formato AAAA-MM
        if not re.match(r"^\d{4}-\d{2}$", mes_limpo):
            raise ValueError(
                f"Mês inválido: '{mes_limpo}'. O formato esperado é 'AAAA-MM' (ex: '2026-08') ou 'latest'."
            )

        root = self._executar_propfind(mes_limpo)
        arquivos = []

        for response_elem in root.findall("{DAV:}response"):
            href = response_elem.findtext("{DAV:}href") or ""
            propstat = response_elem.find("{DAV:}propstat")
            if propstat is None:
                continue
            prop = propstat.find("{DAV:}prop")
            if prop is None:
                continue

            displayname = prop.findtext("{DAV:}displayname")
            if not displayname:
                displayname = href.rstrip("/").split("/")[-1]

            if not displayname.lower().endswith(".zip"):
                continue

            content_length = prop.findtext("{DAV:}getcontentlength")
            tamanho = int(content_length) if content_length and content_length.isdigit() else 0

            url_completa = f"{self.config.webdav_base_url}/{urllib.parse.quote(mes_limpo)}/{urllib.parse.quote(displayname)}"
            arquivos.append(
                ArquivoRemoto(
                    nome=displayname,
                    tamanho_bytes=tamanho,
                    url=url_completa,
                    mes=mes_limpo,
                )
            )

        arquivos_ordenados = sorted(arquivos, key=lambda a: a.nome.lower())
        if not arquivos_ordenados:
            logger.warning(f"Nenhum arquivo ZIP encontrado para o mês {mes_limpo}.")
        return arquivos_ordenados

    @contextmanager
    def abrir_stream_arquivo(self, arquivo: ArquivoRemoto) -> Generator:
        """
        Abre o fluxo de leitura HTTP contínuo de um arquivo remoto.
        Garante tratamento de exceções de rede e fechamento seguro do socket.
        """
        req = urllib.request.Request(arquivo.url, method="GET")
        req.add_header("User-Agent", self.config.user_agent)
        req.add_header("Authorization", self._auth_header)
        req.add_header("Accept-Encoding", "identity")

        try:
            resp = urllib.request.urlopen(req, context=self._ssl_ctx, timeout=self.config.timeout_seconds)
        except urllib.error.HTTPError as http_err:
            logger.error(f"Erro HTTP {http_err.code} ao abrir stream do arquivo {arquivo.nome}: {http_err.reason}")
            raise ConnectionError(
                f"Falha ao baixar '{arquivo.nome}' da Receita Federal (HTTP {http_err.code}: {http_err.reason})."
            ) from http_err
        except urllib.error.URLError as url_err:
            logger.error(f"Falha de rede ao abrir stream do arquivo {arquivo.nome}: {url_err.reason}")
            raise ConnectionError(
                f"Não foi possível conectar para baixar '{arquivo.nome}': {url_err.reason}."
            ) from url_err
        except Exception as err:
            logger.error(f"Erro inesperado ao abrir stream do arquivo {arquivo.nome}: {err}")
            raise ConnectionError(f"Erro ao abrir stream de '{arquivo.nome}': {err}") from err

        try:
            yield resp
        finally:
            try:
                resp.close()
            except Exception:
                pass
