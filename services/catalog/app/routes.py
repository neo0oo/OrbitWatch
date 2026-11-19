from datetime import datetime

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import logic

router = APIRouter(prefix="/api/satellites", tags=["catalog"])


class SatelliteIn(BaseModel):
    norad_id: int = Field(gt=0)


class Satellite(BaseModel):
    norad_id: int
    name: str
    category: str
    operator: str
    added_at: datetime


class AddedSatellite(BaseModel):
    norad_id: int
    name: str


class Tle(BaseModel):
    norad_id: int
    line1: str
    line2: str


@router.get("", response_model=list[Satellite])
def get_satellites():
    return logic.list_satellites()


@router.post("", status_code=201, response_model=AddedSatellite, responses={404: {"description": "No TLE on Celestrak"}, 502: {"description": "Celestrak unreachable"}})
def post_satellite(body: SatelliteIn):
    try:
        return logic.add_satellite(body.norad_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Celestrak has no data for that NORAD ID")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach Celestrak")


@router.delete("/{norad_id}", status_code=204, responses={404: {"description": "Not in the catalog"}})
def delete_satellite(norad_id: int):
    if not logic.remove_satellite(norad_id):
        raise HTTPException(status_code=404, detail="Satellite is not in the catalog")


@router.get("/{norad_id}/tle", response_model=Tle, responses={404: {"description": "Not in the catalog"}})
def get_satellite_tle(norad_id: int):
    try:
        line1, line2 = logic.get_tle(norad_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"norad_id": norad_id, "line1": line1, "line2": line2}