"""
Gerenciamento de Conexão SQLite (cnpj_extractor.database.connection)
====================================================================
"""

from pathlib import Path
import sqlite3


def criar_conexao_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        timeout=60.0,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA busy_timeout = 60000;")
    cursor.execute("PRAGMA cache_size = -524288;")  # ~512MB
    cursor.execute("PRAGMA temp_store = MEMORY;")
    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.close()

    return conn
