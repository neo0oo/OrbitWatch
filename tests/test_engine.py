from datetime import datetime, timedelta, timezone
import pytest
from app.propagation.engine import propagate_teme, teme_to_geodetic, orbit_points

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


def test_iss_distance_from_earth_centre_is_realistic():
    when = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    x, y, z = propagate_teme(LINE1, LINE2, when)
    distance = (x**2 + y**2 + z**2) ** 0.5
    assert 6600 < distance < 6900

def test_geodetic_matches_reference_values():
    when = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    position = propagate_teme(LINE1, LINE2, when)
    lat, lon, alt = teme_to_geodetic(position, when)
    assert lat == pytest.approx(49.85, abs=0.05)
    assert lon == pytest.approx(65.33, abs=0.05)
    assert alt == pytest.approx(421.7, abs=1)


def test_iss_latitude_never_exceeds_its_inclination():
    start = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    for minutes in range(0, 93, 3):
        when = start + timedelta(minutes=minutes)
        lat, _lon, _alt = teme_to_geodetic(propagate_teme(LINE1, LINE2, when), when)
        assert abs(lat) <= 52.0

def test_orbit_points_covers_requested_window():
    start = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    points = orbit_points(LINE1, LINE2, start, minutes=10, step_seconds=60)
    assert len(points) == 11
    assert points[0]["timestamp"] == start.isoformat()