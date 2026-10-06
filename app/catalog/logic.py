import requests

from app.config import CELESTRAK_URL


def parse_tle(text):
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) != 3 or not lines[1].startswith("1 ") or not lines[2].startswith("2 "):
        raise ValueError("Celestrak did not return a valid TLE")
    return lines[0], lines[1], lines[2]


def fetch_tle(norad_id):
    response = requests.get(
        CELESTRAK_URL,
        params={"CATNR": norad_id, "FORMAT": "TLE"},
        timeout=10,
    )
    response.raise_for_status()
    return parse_tle(response.text)