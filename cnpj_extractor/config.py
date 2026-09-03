"""
Módulo de Configuração (cnpj_extractor.config)
=============================================
Centraliza as configurações do coletor de CNPJ de forma simples e intuitiva,
incluindo parâmetros de rede, banco de dados SQLite e mensageria com RabbitMQ.

Pode ser configurado através de:
1. Valores padrão oficiais da Receita Federal e RabbitMQ (zero configuração necessária).
2. Arquivo `.env` na raiz do projeto.
3. Variáveis de ambiente do sistema operacional / Docker.
4. Parâmetros passados diretamente na CLI ou no código Python.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Optional
from urllib.parse import urlparse

# URL pública oficial padrão da Receita Federal
DEFAULT_RECEITA_URL = "https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9"
DEFAULT_TOKEN = "YggdBLfdninEJX9"
DEFAULT_WEBDAV_BASE = "https://arquivos.receitafederal.gov.br/public.php/webdav"
DEFAULT_DB_PATH = "data/cnpj.db"
DEFAULT_BATCH_SIZE = 20000

# Configurações padrão do RabbitMQ
DEFAULT_RABBITMQ_HOST = "localhost"
DEFAULT_RABBITMQ_PORT = 5672
DEFAULT_RABBITMQ_USER = "guest"
DEFAULT_RABBITMQ_PASSWORD = "guest"
DEFAULT_RABBITMQ_QUEUE = "cnpj_tasks_queue"


def _carregar_arquivo_env(caminho_env: Optional[Path] = None) -> None:
    """
    Carrega variáveis de um arquivo .env de forma segura sem dependência externa obrigatória.
    Se a biblioteca 'dotenv' estiver instalada, usa ela; caso contrário, usa parser embutido.
    """
    if caminho_env is None:
        caminho_env = Path.cwd() / ".env"
        if not caminho_env.exists():
            caminho_env = Path(__file__).resolve().parent.parent / ".env"

    if not caminho_env.exists() or not caminho_env.is_file():
        return

    try:
        import dotenv
        dotenv.load_dotenv(caminho_env)
        return
    except ImportError:
        pass

    try:
        with open(caminho_env, "r", encoding="utf-8") as f:
            for line in f:
                linha = line.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave = chave.strip()
                valor = valor.strip().strip("'\"")
                if chave and chave not in os.environ:
                    os.environ[chave] = valor
    except Exception:
        pass


def extrair_token_e_base_url(url_ou_token: str) -> tuple[str, str, str]:
    """
    Extrai o token e constrói as URLs WebDAV e base a partir de uma URL completa ou token simples.
    """
    valor = url_ou_token.strip()

    if not valor.startswith("http://") and not valor.startswith("https://"):
        token = valor
        base_url = "https://arquivos.receitafederal.gov.br"
        webdav_url = f"{base_url}/public.php/webdav"
        return token, webdav_url, base_url

    parsed = urlparse(valor)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    webdav_url = f"{base_url}/public.php/webdav"

    match = re.search(r"/s/([a-zA-Z0-9_-]+)", parsed.path)
    if match:
        token = match.group(1)
    else:
        token = DEFAULT_TOKEN

    return token, webdav_url, base_url


@dataclass
class Config:
    """Classe de configuração centralizada para o pipeline de extração."""
    share_url: str = DEFAULT_RECEITA_URL
    share_token: str = DEFAULT_TOKEN
    webdav_base_url: str = DEFAULT_WEBDAV_BASE
    base_url: str = "https://arquivos.receitafederal.gov.br"
    db_path: str = DEFAULT_DB_PATH
    batch_size: int = DEFAULT_BATCH_SIZE
    default_month: str = "latest"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CNPJ-Streamer/1.0"
    timeout_seconds: int = 45

    # RabbitMQ
    rabbitmq_host: str = DEFAULT_RABBITMQ_HOST
    rabbitmq_port: int = DEFAULT_RABBITMQ_PORT
    rabbitmq_user: str = DEFAULT_RABBITMQ_USER
    rabbitmq_password: str = DEFAULT_RABBITMQ_PASSWORD
    rabbitmq_queue: str = DEFAULT_RABBITMQ_QUEUE

    @classmethod
    def carregar(
        cls,
        url_ou_token: Optional[str] = None,
        db_path: Optional[str] = None,
        batch_size: Optional[int] = None,
        month: Optional[str] = None,
        rabbitmq_host: Optional[str] = None,
        rabbitmq_port: Optional[int] = None,
        rabbitmq_user: Optional[str] = None,
        rabbitmq_password: Optional[str] = None,
        rabbitmq_queue: Optional[str] = None,
    ) -> "Config":
        """
        Carrega as configurações combinando arquivo .env, variáveis de ambiente e argumentos.
        """
        _carregar_arquivo_env()

        # 1. Obter URL / Token
        raw_url = (
            url_ou_token
            or os.getenv("RECEITA_SHARE_URL")
            or os.getenv("RECEITA_SHARE_TOKEN")
            or DEFAULT_RECEITA_URL
        )

        token, webdav_url, base_url = extrair_token_e_base_url(raw_url)

        # 2. Obter DB Path
        caminho_banco = (
            db_path
            or os.getenv("DB_PATH")
            or DEFAULT_DB_PATH
        )

        # 3. Obter Batch Size
        lote_str = os.getenv("BATCH_SIZE")
        if batch_size is not None:
            lote = batch_size
        elif lote_str and lote_str.isdigit():
            lote = int(lote_str)
        else:
            lote = DEFAULT_BATCH_SIZE

        # 4. Obter mês padrão
        mes = (
            month
            or os.getenv("DEFAULT_MONTH")
            or "latest"
        )

        # 5. RabbitMQ Configs
        rb_host = rabbitmq_host or os.getenv("RABBITMQ_HOST") or DEFAULT_RABBITMQ_HOST
        rb_port_str = os.getenv("RABBITMQ_PORT")
        if rabbitmq_port is not None:
            rb_port = rabbitmq_port
        elif rb_port_str and rb_port_str.isdigit():
            rb_port = int(rb_port_str)
        else:
            rb_port = DEFAULT_RABBITMQ_PORT

        rb_user = rabbitmq_user or os.getenv("RABBITMQ_USER") or DEFAULT_RABBITMQ_USER
        rb_pass = rabbitmq_password or os.getenv("RABBITMQ_PASSWORD") or DEFAULT_RABBITMQ_PASSWORD
        rb_queue = rabbitmq_queue or os.getenv("RABBITMQ_QUEUE") or DEFAULT_RABBITMQ_QUEUE

        return cls(
            share_url=raw_url,
            share_token=token,
            webdav_base_url=webdav_url,
            base_url=base_url,
            db_path=caminho_banco,
            batch_size=lote,
            default_month=mes,
            rabbitmq_host=rb_host,
            rabbitmq_port=rb_port,
            rabbitmq_user=rb_user,
            rabbitmq_password=rb_pass,
            rabbitmq_queue=rb_queue,
        )
