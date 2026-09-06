"""
Módulo de Configuração (cnpj_extractor.config)
=============================================
Centraliza as configurações do coletor de CNPJ de forma simples e intuitiva,
incluindo parâmetros de rede, banco de dados PostgreSQL e mensageria RabbitMQ.

Pode ser configurado através de:
1. Valores padrão oficiais da Receita Federal, PostgreSQL e RabbitMQ.
2. Arquivo `.env` na raiz do projeto.
3. Variáveis de ambiente do sistema operacional / Docker Compose.
4. Parâmetros passados diretamente na CLI ou no código Python.
"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("cnpj_extractor.config")

# URL pública oficial padrão da Receita Federal
DEFAULT_RECEITA_URL = "https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9"
DEFAULT_TOKEN = "YggdBLfdninEJX9"
DEFAULT_WEBDAV_BASE = "https://arquivos.receitafederal.gov.br/public.php/webdav"
DEFAULT_BATCH_SIZE = 20000

# Configurações padrão do PostgreSQL
DEFAULT_PG_HOST = "localhost"
DEFAULT_PG_PORT = 5432
DEFAULT_PG_DB = "cnpj_db"
DEFAULT_PG_USER = "postgres"
DEFAULT_PG_PASSWORD = "postgres"
DEFAULT_PG_POOL_MIN = 1
DEFAULT_PG_POOL_MAX = 10

# Configurações padrão do RabbitMQ
DEFAULT_RABBITMQ_HOST = "localhost"
DEFAULT_RABBITMQ_PORT = 5672
DEFAULT_RABBITMQ_USER = "guest"
DEFAULT_RABBITMQ_PASSWORD = "guest"
DEFAULT_RABBITMQ_QUEUE = "cnpj_tasks_queue"


def _carregar_arquivo_env(caminho_env: Optional[Path] = None) -> None:
    """
    Carrega variáveis de um arquivo .env de forma segura, com log de advertências.
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
    except Exception as err:
        logger.warning(f"Erro ao processar arquivo .env ({caminho_env}): {err}")


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
        logger.warning(
            f"Não foi possível identificar o token na URL '{valor}'. "
            f"Utilizando token padrão de contingência '{DEFAULT_TOKEN}'."
        )
        token = DEFAULT_TOKEN

    return token, webdav_url, base_url


@dataclass
class Config:
    """Classe de configuração centralizada para o pipeline de extração e persistência PostgreSQL."""
    share_url: str = DEFAULT_RECEITA_URL
    share_token: str = DEFAULT_TOKEN
    webdav_base_url: str = DEFAULT_WEBDAV_BASE
    base_url: str = "https://arquivos.receitafederal.gov.br"
    batch_size: int = DEFAULT_BATCH_SIZE
    default_month: str = "latest"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CNPJ-Streamer/2.0"
    timeout_seconds: int = 45

    # PostgreSQL
    postgres_host: str = DEFAULT_PG_HOST
    postgres_port: int = DEFAULT_PG_PORT
    postgres_db: str = DEFAULT_PG_DB
    postgres_user: str = DEFAULT_PG_USER
    postgres_password: str = DEFAULT_PG_PASSWORD
    postgres_pool_min: int = DEFAULT_PG_POOL_MIN
    postgres_pool_max: int = DEFAULT_PG_POOL_MAX
    database_url: Optional[str] = None

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
        batch_size: Optional[int] = None,
        month: Optional[str] = None,
        postgres_host: Optional[str] = None,
        postgres_port: Optional[int] = None,
        postgres_db: Optional[str] = None,
        postgres_user: Optional[str] = None,
        postgres_password: Optional[str] = None,
        database_url: Optional[str] = None,
        rabbitmq_host: Optional[str] = None,
        rabbitmq_port: Optional[int] = None,
        rabbitmq_user: Optional[str] = None,
        rabbitmq_password: Optional[str] = None,
        rabbitmq_queue: Optional[str] = None,
    ) -> "Config":
        """
        Carrega as configurações combinando arquivo .env, variáveis de ambiente e argumentos,
        alertando via logger.warning sobre fallbacks para credenciais ou tokens padrão.
        """
        _carregar_arquivo_env()

        # 1. Obter URL / Token com alerta em fallback
        has_custom_url = bool(url_ou_token or os.getenv("RECEITA_SHARE_URL") or os.getenv("RECEITA_SHARE_TOKEN"))
        raw_url = (
            url_ou_token
            or os.getenv("RECEITA_SHARE_URL")
            or os.getenv("RECEITA_SHARE_TOKEN")
            or DEFAULT_RECEITA_URL
        )

        if not has_custom_url:
            logger.warning(
                f"Nenhuma URL ou Token customizado da Receita Federal informado no .env. "
                f"Utilizando token público padrão ('{DEFAULT_TOKEN}')."
            )

        token, webdav_url, base_url = extrair_token_e_base_url(raw_url)

        # 2. Obter Batch Size
        lote_str = os.getenv("BATCH_SIZE")
        if batch_size is not None:
            lote = batch_size
        elif lote_str and lote_str.isdigit():
            lote = int(lote_str)
        else:
            lote = DEFAULT_BATCH_SIZE

        # 3. Obter mês padrão
        mes = (
            month
            or os.getenv("DEFAULT_MONTH")
            or "latest"
        )

        # 4. PostgreSQL Configs com alerta em fallback de senha
        pg_url = database_url or os.getenv("DATABASE_URL")

        pg_host = postgres_host or os.getenv("POSTGRES_HOST") or os.getenv("PGHOST") or DEFAULT_PG_HOST
        pg_port_str = os.getenv("POSTGRES_PORT") or os.getenv("PGPORT")
        if postgres_port is not None:
            pg_port = postgres_port
        elif pg_port_str and pg_port_str.isdigit():
            pg_port = int(pg_port_str)
        else:
            pg_port = DEFAULT_PG_PORT

        pg_db = postgres_db or os.getenv("POSTGRES_DB") or os.getenv("POSTGRES_DATABASE") or os.getenv("PGDATABASE") or DEFAULT_PG_DB
        pg_user = postgres_user or os.getenv("POSTGRES_USER") or os.getenv("PGUSER") or DEFAULT_PG_USER
        
        has_custom_pg_pass = bool(postgres_password or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or pg_url)
        pg_pass = postgres_password or os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD") or DEFAULT_PG_PASSWORD

        if not has_custom_pg_pass:
            logger.warning(
                "Variável POSTGRES_PASSWORD não informada no .env. "
                "Utilizando senha padrão de desenvolvimento ('postgres'). Para ambientes de produção, defina POSTGRES_PASSWORD no .env."
            )

        pg_pool_min = int(os.getenv("POSTGRES_POOL_MIN", str(DEFAULT_PG_POOL_MIN)))
        pg_pool_max = int(os.getenv("POSTGRES_POOL_MAX", str(DEFAULT_PG_POOL_MAX)))

        # 5. RabbitMQ Configs com alerta em fallback de senha
        rb_host = rabbitmq_host or os.getenv("RABBITMQ_HOST") or DEFAULT_RABBITMQ_HOST
        rb_port_str = os.getenv("RABBITMQ_PORT")
        if rabbitmq_port is not None:
            rb_port = rabbitmq_port
        elif rb_port_str and rb_port_str.isdigit():
            rb_port = int(rb_port_str)
        else:
            rb_port = DEFAULT_RABBITMQ_PORT

        rb_user = rabbitmq_user or os.getenv("RABBITMQ_USER") or DEFAULT_RABBITMQ_USER

        has_custom_rb_pass = bool(rabbitmq_password or os.getenv("RABBITMQ_PASSWORD"))
        rb_pass = rabbitmq_password or os.getenv("RABBITMQ_PASSWORD") or DEFAULT_RABBITMQ_PASSWORD

        if not has_custom_rb_pass:
            logger.warning(
                "Variável RABBITMQ_PASSWORD não informada no .env. "
                "Utilizando credenciais padrão de desenvolvimento ('guest'). Para ambientes de produção, defina RABBITMQ_PASSWORD no .env."
            )

        rb_queue = rabbitmq_queue or os.getenv("RABBITMQ_QUEUE") or DEFAULT_RABBITMQ_QUEUE

        return cls(
            share_url=raw_url,
            share_token=token,
            webdav_base_url=webdav_url,
            base_url=base_url,
            batch_size=lote,
            default_month=mes,
            postgres_host=pg_host,
            postgres_port=pg_port,
            postgres_db=pg_db,
            postgres_user=pg_user,
            postgres_password=pg_pass,
            postgres_pool_min=pg_pool_min,
            postgres_pool_max=pg_pool_max,
            database_url=pg_url,
            rabbitmq_host=rb_host,
            rabbitmq_port=rb_port,
            rabbitmq_user=rb_user,
            rabbitmq_password=rb_pass,
            rabbitmq_queue=rb_queue,
        )
