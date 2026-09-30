import sqlite3
from pathlib import Path
from app.config import DATA_DIR

DB_PATH = Path(DATA_DIR) / "orbitwatch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS satellites (
    norad_id    INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    added_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tle_cache (
    norad_id    INTEGER PRIMARY KEY REFERENCES satellites(norad_id) ON DELETE CASCADE,
    line1       TEXT NOT NULL,
    line2       TEXT NOT NULL,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()