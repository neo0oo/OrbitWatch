from datetime import datetime, timezone
import pytest
import requests
from app import database
from app.catalog import logic

SAMPLE_RESPONSE = """ISS (ZARYA)
1 25544U 98067A   26279.01444283  .00005131  00000+0  10208-3 0  9995
2 25544  51.6314 111.6262 0006858 227.8987 132.1419 15.48747543588933
"""


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()


def fake_fetch(line1="1 FAKE", line2="2 FAKE"):
    return lambda norad_id: ("ISS (ZARYA)", line1, line2)


def make_stale(norad_id):
    conn = database.get_connection()
    conn.execute(
        "UPDATE tle_cache SET fetched_at = '2020-01-01 00:00:00' WHERE norad_id = ?",
        (norad_id,),
    )
    conn.commit()
    conn.close()


def test_parse_tle_returns_name_and_both_lines():
    name, line1, line2 = logic.parse_tle(SAMPLE_RESPONSE)
    assert name == "ISS (ZARYA)"
    assert line1.startswith("1 25544")
    assert line2.startswith("2 25544")


def test_parse_tle_rejects_error_text():
    with pytest.raises(ValueError):
        logic.parse_tle("No GP data found")


def test_is_stale_compares_age_to_refresh_hours():
    now = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert not logic.is_stale("2026-10-07 10:00:00", now)
    assert logic.is_stale("2026-10-07 04:00:00", now)


def test_adding_same_satellite_twice_keeps_one_row(db, monkeypatch):
    monkeypatch.setattr(logic, "fetch_tle", fake_fetch())
    logic.add_satellite(25544)
    logic.add_satellite(25544)
    assert len(logic.list_satellites()) == 1


def test_remove_satellite_also_removes_cached_tle(db, monkeypatch):
    monkeypatch.setattr(logic, "fetch_tle", fake_fetch())
    logic.add_satellite(25544)
    assert logic.remove_satellite(25544) is True
    assert logic.remove_satellite(25544) is False
    with pytest.raises(LookupError):
        logic.get_tle(25544)


def test_get_tle_unknown_satellite_raises(db):
    with pytest.raises(LookupError):
        logic.get_tle(99999)


def test_get_tle_refreshes_a_stale_tle(db, monkeypatch):
    monkeypatch.setattr(logic, "fetch_tle", fake_fetch("1 OLD", "2 OLD"))
    logic.add_satellite(25544)
    make_stale(25544)
    monkeypatch.setattr(logic, "fetch_tle", fake_fetch("1 NEW", "2 NEW"))
    assert logic.get_tle(25544) == ("1 NEW", "2 NEW")


def test_get_tle_keeps_old_tle_when_celestrak_is_down(db, monkeypatch):
    monkeypatch.setattr(logic, "fetch_tle", fake_fetch("1 OLD", "2 OLD"))
    logic.add_satellite(25544)
    make_stale(25544)

    def celestrak_down(norad_id):
        raise requests.ConnectionError()

    monkeypatch.setattr(logic, "fetch_tle", celestrak_down)
    assert logic.get_tle(25544) == ("1 OLD", "2 OLD")