import pytest
import requests
from fastapi.testclient import TestClient

from app import catalog_client, database
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_cache():
    if not database.DATABASE_URL:
        pytest.skip("DATABASE_URL not set; start SQL Server with docker compose")
    database.run_migrations()
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tle_cache")
    conn.commit()
    conn.close()

ISS_LINE1 = "1 25544U 98067A   26316.43260916  .00008191  00000+0  15481-3 0  9999"
ISS_LINE2 = "2 25544  51.6324 286.4897 0007327  17.4271 342.6968 15.49332729594739"


class FakeResponse:
    """Stands in for the catalog's HTTP response."""

    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


def test_position_uses_tle_from_catalog(monkeypatch):
    called = {}

    def fake_get(url, timeout):
        called["url"] = url
        called["timeout"] = timeout
        return FakeResponse(200, {"norad_id": 25544, "line1": ISS_LINE1, "line2": ISS_LINE2})

    monkeypatch.setattr(catalog_client.requests, "get", fake_get)
    response = client.get("/api/satellites/25544/position")

    assert response.status_code == 200
    body = response.json()
    assert -90 <= body["latitude"] <= 90
    assert 300 < body["altitude_km"] < 500
    assert called["url"].endswith("/api/satellites/25544/tle")
    assert called["timeout"] is not None


def test_unknown_satellite_in_catalog_gives_404(monkeypatch):
    monkeypatch.setattr(catalog_client.requests, "get", lambda url, timeout: FakeResponse(404))
    response = client.get("/api/satellites/99999/position")
    assert response.status_code == 404


def test_catalog_timeout_gives_503(monkeypatch):
    def fake_get(url, timeout):
        raise requests.Timeout()

    monkeypatch.setattr(catalog_client.requests, "get", fake_get)
    response = client.get("/api/satellites/25544/position")
    assert response.status_code == 503
    assert response.json()["detail"] == "Catalog service is unavailable"


def test_catalog_error_status_gives_503(monkeypatch):
    monkeypatch.setattr(catalog_client.requests, "get", lambda url, timeout: FakeResponse(500))
    response = client.get("/api/satellites/25544/track")
    assert response.status_code == 503


def test_catalog_down_serves_cached_tle_marked_stale(monkeypatch):
    def ok(url, timeout):
        return FakeResponse(200, {"norad_id": 25544, "line1": ISS_LINE1, "line2": ISS_LINE2})

    monkeypatch.setattr(catalog_client.requests, "get", ok)
    assert client.get("/api/satellites/25544/position").status_code == 200

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tle_cache SET cached_at = '2020-01-01T00:00:00'")
    conn.commit()
    conn.close()

    def catalog_down(url, timeout):
        raise requests.ConnectionError()

    monkeypatch.setattr(catalog_client.requests, "get", catalog_down)
    response = client.get("/api/satellites/25544/position")
    assert response.status_code == 200
    assert response.json()["stale_tle"] is True
