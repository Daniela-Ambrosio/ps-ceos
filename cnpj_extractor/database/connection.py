"""
Gerenciamento de Conexões e Pooling do PostgreSQL (cnpj_extractor.database.connection)
===================================================================================
Gerencia o pool de conexões thread-safe com PostgreSQL (psycopg2.pool.ThreadedConnectionPool),
oferecendo contexto seguro com auto-commit/rollback e liberação de conexões.
"""

from contextlib import contextmanager
import logging
from typing import Any, Generator, Optional

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except ImportError:
    psycopg2 = None

from ..config import Config

logger = logging.getLogger("cnpj_extractor.database.connection")


class PostgresConnectionPool:
    """Pool de conexões thread-safe para PostgreSQL."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.carregar()
        self._pool: Optional[Any] = None
        self._inicializar_pool()

    def _inicializar_pool(self) -> None:
        if psycopg2 is None:
            logger.warning(
                "Biblioteca 'psycopg2' não está instalada no ambiente. "
                "Operações de banco de dados PostgreSQL exigem psycopg2 ou psycopg2-binary."
            )
            return

        try:
            if self.config.database_url:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=self.config.postgres_pool_min,
                    maxconn=self.config.postgres_pool_max,
                    dsn=self.config.database_url,
                )
            else:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=self.config.postgres_pool_min,
                    maxconn=self.config.postgres_pool_max,
                    host=self.config.postgres_host,
                    port=self.config.postgres_port,
                    dbname=self.config.postgres_db,
                    user=self.config.postgres_user,
                    password=self.config.postgres_password,
                    connect_timeout=15,
                )
            logger.info(
                f"Connection pool PostgreSQL inicializado ({self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_db})."
            )
        except Exception as err:
            logger.error(f"Erro ao inicializar o Connection Pool do PostgreSQL: {err}")
            self._pool = None

    @contextmanager
    def get_connection(self) -> Generator:
        """
        Adquire uma conexão do pool, gerencia transação e garante a devolução ao pool.
        """
        if self._pool is None:
            self._inicializar_pool()
            if self._pool is None:
                raise ConnectionError(
                    "Connection pool PostgreSQL não disponível. Verifique se o banco de dados está ativo e acessível."
                )

        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self._pool is not None:
                self._pool.putconn(conn)

    def fechar_todos(self) -> None:
        """Fecha todas as conexões do pool no encerramento da aplicação."""
        if self._pool is not None:
            try:
                self._pool.closeall()
                self._pool = None
                logger.info("Connection pool PostgreSQL encerrado.")
            except Exception as err:
                logger.warning(f"Erro ao fechar pool PostgreSQL: {err}")
