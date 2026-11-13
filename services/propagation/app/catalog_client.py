import requests

from app.config import CATALOG_URL, CATALOG_TIMEOUT_S


class CatalogUnavailable(Exception):
    """The catalog service could not be reached or gave an unusable answer."""


def get_tle(norad_id):
    try:
        response = requests.get(
            f"{CATALOG_URL}/api/satellites/{norad_id}/tle",
            timeout=CATALOG_TIMEOUT_S,
        )
    except requests.RequestException as error:
        raise CatalogUnavailable("Catalog service is unavailable") from error

    if response.status_code == 404:
        raise LookupError(f"Satellite {norad_id} is not in the catalog")
    if response.status_code != 200:
        raise CatalogUnavailable(f"Catalog returned status {response.status_code}")

    data = response.json()
    return data["line1"], data["line2"]