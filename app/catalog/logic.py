import requests
from app.database import get_connection
from app.config import CELESTRAK_URL


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
        conn.execute(
            "INSERT OR IGNORE INTO satellites (norad_id, name) VALUES (?, ?)",
            (norad_id, name),
        )
        conn.execute(
            """
            INSERT INTO tle_cache (norad_id, line1, line2) VALUES (?, ?, ?)
            ON CONFLICT(norad_id) DO UPDATE SET
                line1 = excluded.line1,
                line2 = excluded.line2,
                fetched_at = datetime('now')
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
        rows = conn.execute(
            "SELECT norad_id, name, added_at FROM satellites ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def remove_satellite(norad_id):
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM satellites WHERE norad_id = ?", (norad_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()