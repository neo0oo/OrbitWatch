import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.catalog import logic

router = APIRouter(prefix="/api/satellites", tags=["catalog"])


class SatelliteIn(BaseModel):
    norad_id: int = Field(gt=0)


@router.get("")
def get_satellites():
    return logic.list_satellites()


@router.post("", status_code=201)
def post_satellite(body: SatelliteIn):
    try:
        return logic.add_satellite(body.norad_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Celestrak has no data for that NORAD ID")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach Celestrak")


@router.delete("/{norad_id}", status_code=204)
def delete_satellite(norad_id: int):
    if not logic.remove_satellite(norad_id):
        raise HTTPException(status_code=404, detail="Satellite is not in the catalog")