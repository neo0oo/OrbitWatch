from datetime import timezone
from sgp4.api import Satrec, jday

def propagate_teme(line1, line2, when):
    when = when.astimezone(timezone.utc)
    sat = Satrec.twoline2rv(line1, line2)
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, when.second + when.microsecond * 1e-6)
    error, position, _velocity = sat.sgp4(jd, fr)
    if error != 0:
        raise ValueError(f"SGP4 propagation error: {error}")
    return position