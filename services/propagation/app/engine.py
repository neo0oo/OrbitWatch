import math
from datetime import timezone, timedelta
from sgp4.api import Satrec, jday

EARTH_RADIUS_KM = 6378.137
EARTH_FLATTENING = 1 / 298.257223563
ECC_SQUARED = EARTH_FLATTENING * (2 - EARTH_FLATTENING)

def _julian_date(when):
    when = when.astimezone(timezone.utc)
    return jday(
        when.year, when.month, when.day,
        when.hour, when.minute, when.second + when.microsecond / 1e6,
    )

def propagate_teme(line1, line2, when):
    sat = Satrec.twoline2rv(line1, line2)
    jd, fr = _julian_date(when)
    error, position, _velocity = sat.sgp4(jd, fr)
    if error != 0:
        raise ValueError(f"SGP4 failed with error code {error}")
    return position

def gmst_radians(when):
    jd, fr = _julian_date(when)
    t = ((jd - 2451545.0) + fr) / 36525.0
    seconds = 67310.54841 + (876600 * 3600 + 8640184.812866) * t + 0.093104 * t**2 - 6.2e-6 * t**3
    return math.radians((seconds % 86400) / 240.0)

def teme_to_geodetic(position, when):
    x, y, z = position
    theta = gmst_radians(when)
    x_e = x * math.cos(theta) + y * math.sin(theta)
    y_e = -x * math.sin(theta) + y * math.cos(theta)

    lon = math.atan2(y_e, x_e)
    r = math.hypot(x_e, y_e)
    lat = math.atan2(z, r)
    for _ in range(5):
        sin_lat = math.sin(lat)
        n = EARTH_RADIUS_KM / math.sqrt(1 - ECC_SQUARED * sin_lat**2)
        lat = math.atan2(z + n * ECC_SQUARED * sin_lat, r)

    sin_lat = math.sin(lat)
    n = EARTH_RADIUS_KM / math.sqrt(1 - ECC_SQUARED * sin_lat**2)
    if abs(math.degrees(lat)) < 80:
        alt = r / math.cos(lat) - n
    else:
        alt = z / sin_lat - n * (1 - ECC_SQUARED)
    return math.degrees(lat), math.degrees(lon), alt

def orbit_points(line1, line2, start, minutes=95, step_seconds=60):
    points = []
    for offset in range(0, minutes * 60 + 1, step_seconds):
        when = start + timedelta(seconds=offset)
        lat, lon, alt = teme_to_geodetic(propagate_teme(line1, line2, when), when)
        points.append({
            "timestamp": when.isoformat(),
            "latitude": lat,
            "longitude": lon,
            "altitude_km": alt,
        })
    return points