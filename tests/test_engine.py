from datetime import datetime, timezone

from app.propagation.engine import propagate_teme

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


def test_iss_distance_from_earth_centre_is_realistic():
    when = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    x, y, z = propagate_teme(LINE1, LINE2, when)
    distance = (x**2 + y**2 + z**2) ** 0.5
    assert 6600 < distance < 6900