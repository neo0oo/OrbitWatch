from datetime import datetime, timedelta, timezone

from app import catalog_client
from app.config import TLE_CACHE_HOURS
from app.database import get_connection


def _read(norad_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT line1, line2, cached_at FROM tle_cache WHERE norad_id = %s", (norad_id,))
        return cur.fetchone()
    finally:
        conn.close()


def _save(norad_id, line1, line2):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            MERGE tle_cache AS target
            USING (SELECT %s AS norad_id, %s AS line1, %s AS line2) AS source
            ON target.norad_id = source.norad_id
            WHEN MATCHED THEN
                UPDATE SET line1 = source.line1, line2 = source.line2, cached_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (norad_id, line1, line2) VALUES (source.norad_id, source.line1, source.line2);
            """,
            (norad_id, line1, line2),
        )
        conn.commit()
    finally:
        conn.close()


def _delete(norad_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tle_cache WHERE norad_id = %s", (norad_id,))
        conn.commit()
    finally:
        conn.close()


def _is_fresh(cached_at):
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - cached_at < timedelta(hours=TLE_CACHE_HOURS)


def get_tle(norad_id):
    """Returns (line1, line2, stale). stale=True means the catalog was down and we used our cached copy."""
    row = _read(norad_id)
    if row and _is_fresh(row["cached_at"]):
        return row["line1"], row["line2"], False
    try:
        line1, line2 = catalog_client.get_tle(norad_id)
    except LookupError:
        _delete(norad_id)  # removed from the catalog, so drop our copy too
        raise
    except catalog_client.CatalogUnavailable:
        if row:
            return row["line1"], row["line2"], True
        raise
    _save(norad_id, line1, line2)
    return line1, line2, False
