from datetime import datetime, timedelta, timezone

import requests

from app.config import CELESTRAK_URL, TLE_REFRESH_HOURS
from app.database import get_connection


def parse_tle(text):
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) != 3 or not lines[1].startswith("1 ") or not lines[2].startswith("2 "):
        raise ValueError("Celestrak did not return a valid TLE")
    return lines[0], lines[1], lines[2]


def fetch_tle(norad_id):
    response = requests.get(
        CELESTRAK_URL,
        params={"CATNR": norad_id, "FORMAT": "TLE"},
        timeout=10,
    )
    response.raise_for_status()
    return parse_tle(response.text)


def add_satellite(norad_id):
    name, line1, line2 = fetch_tle(norad_id)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM satellites WHERE norad_id = %s)
                INSERT INTO satellites (norad_id, name) VALUES (%s, %s)
            """,
            (norad_id, norad_id, name),
        )
        cur.execute(
            """
            MERGE tle_cache AS target
            USING (SELECT %s AS norad_id, %s AS line1, %s AS line2) AS source
            ON target.norad_id = source.norad_id
            WHEN MATCHED THEN
                UPDATE SET line1 = source.line1, line2 = source.line2, fetched_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (norad_id, line1, line2) VALUES (source.norad_id, source.line1, source.line2);
            """,
            (norad_id, line1, line2),
        )
        conn.commit()
    finally:
        conn.close()
    return {"norad_id": norad_id, "name": name}


def list_satellites():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT norad_id, name, category, operator, added_at FROM satellites ORDER BY name")
        return cur.fetchall()
    finally:
        conn.close()


def remove_satellite(norad_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM satellites WHERE norad_id = %s", (norad_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def is_stale(fetched_at, now=None):
    now = now or datetime.now(timezone.utc)
    if isinstance(fetched_at, str):
        fetched_at = datetime.fromisoformat(fetched_at[:19])
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return now - fetched_at > timedelta(hours=TLE_REFRESH_HOURS)


def _read_tle_row(norad_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT line1, line2, fetched_at FROM tle_cache WHERE norad_id = %s",
            (norad_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_tle(norad_id):
    row = _read_tle_row(norad_id)
    if row is None:
        raise LookupError(f"Satellite {norad_id} is not in the catalog")
    if is_stale(row["fetched_at"]):
        try:
            add_satellite(norad_id)
            row = _read_tle_row(norad_id)
        except (requests.RequestException, ValueError):
            pass
    return row["line1"], row["line2"]
