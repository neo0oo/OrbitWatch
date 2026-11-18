from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app import catalog_client, engine, tle_service

router = APIRouter(prefix="/api/satellites", tags=["propagation"])


class Position(BaseModel):
    norad_id: int
    timestamp: str
    latitude: float
    longitude: float
    altitude_km: float
    stale_tle: bool


class TrackPoint(BaseModel):
    timestamp: str
    latitude: float
    longitude: float
    altitude_km: float


class Track(BaseModel):
    norad_id: int
    points: list[TrackPoint]
    stale_tle: bool


def _tle_or_404(norad_id):
    try:
        return tle_service.get_tle(norad_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except catalog_client.CatalogUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))


errors = {404: {"description": "Not in the catalog"}, 422: {"description": "Propagation failed"}, 503: {"description": "Catalog unavailable and no cached TLE"}}


@router.get("/{norad_id}/position", response_model=Position, responses=errors)
def get_position(norad_id: int):
    line1, line2, stale = _tle_or_404(norad_id)
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
        "stale_tle": stale,
    }


@router.get("/{norad_id}/track", response_model=Track, responses=errors)
def get_track(
    norad_id: int,
    minutes: int = Query(95, ge=1, le=300),
    step_seconds: int = Query(60, ge=10, le=600),
):
    line1, line2, stale = _tle_or_404(norad_id)
    start = datetime.now(timezone.utc)
    try:
        points = engine.orbit_points(line1, line2, start, minutes, step_seconds)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"norad_id": norad_id, "points": points, "stale_tle": stale}