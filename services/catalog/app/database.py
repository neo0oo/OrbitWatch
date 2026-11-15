import logging
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymssql

from app.config import DATABASE_URL

logger = logging.getLogger("orbitwatch")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _connect_args():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    url = urlparse(DATABASE_URL)
    return {
        "server": url.hostname,
        "port": url.port or 1433,
        "user": unquote(url.username),
        "password": unquote(url.password),
        "database": url.path.lstrip("/"),
    }


def get_connection(retries=5, delay=2):
    """Connect, retrying with backoff (Azure SQL may be paused and take up to a minute to resume)."""
    for attempt in range(1, retries + 1):
        try:
            return pymssql.connect(**_connect_args(), as_dict=True, login_timeout=10, tds_version="7.4")
        except pymssql.OperationalError:
            if attempt == retries:
                raise
            logger.info("Database not ready, retry %s/%s", attempt, retries)
            time.sleep(delay * attempt)


def run_migrations():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            IF OBJECT_ID('schema_migrations') IS NULL
            CREATE TABLE schema_migrations (
                version NVARCHAR(255) NOT NULL PRIMARY KEY,
                applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """)
        conn.commit()
        cur.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in cur.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            logger.info("Applying migration %s", path.name)
            cur.execute(path.read_text())
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            conn.commit()
    finally:
        conn.close()


def check_db():
    try:
        conn = get_connection(retries=1)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS n FROM satellites")      # can read
            cur.execute("UPDATE satellites SET name = name WHERE 1 = 0")  # has write permission
            conn.rollback()
        finally:
            conn.close()
        return True
    except Exception:
        return False
