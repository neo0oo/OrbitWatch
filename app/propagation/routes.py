from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.catalog.logic import get_tle
from app.propagation import engine

router = APIRouter(prefix="/api/satellites", tags=["propagation"])


def _tle_or_404(norad_id):
    try:
        return get_tle(norad_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/{norad_id}/position")
def get_position(norad_id: int):
    line1, line2 = _tle_or_404(norad_id)
    when = datetime.now(timezone.utc)
    try:
        position = engine.propagate_teme(line1, line2, when)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    lat, lon, alt = engine.teme_to_geodetic(position, when)
    return {
        "norad_id": norad_id,
        "timestamp": when.isoformat(),
        "latitude": lat,
        "longitude": lon,
        "altitude_km": alt,
    }


@router.get("/{norad_id}/track")
def get_track(
    norad_id: int,
    minutes: int = Query(95, ge=1, le=300),
    step_seconds: int = Query(60, ge=10, le=600),
):
    line1, line2 = _tle_or_404(norad_id)
    start = datetime.now(timezone.utc)
    try:
        points = engine.orbit_points(line1, line2, start, minutes, step_seconds)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"norad_id": norad_id, "points": points}