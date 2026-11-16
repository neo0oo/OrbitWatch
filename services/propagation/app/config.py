import os

PORT = int(os.environ.get("PORT", 8000))
DATA_DIR = os.environ.get("DATA_DIR", "./data")
CELESTRAK_URL = os.environ.get("CELESTRAK_URL", "https://celestrak.org/NORAD/elements/gp.php")
TLE_REFRESH_HOURS = int(os.environ.get("TLE_REFRESH_HOURS", 6))

CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:8001")
CATALOG_TIMEOUT_S = float(os.environ.get("CATALOG_TIMEOUT_S", 5))
GIT_SHA = os.environ.get("GIT_SHA", "dev")
ALLOWED_ORIGINS = [o for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o]
DATABASE_URL = os.environ.get("DATABASE_URL")
TLE_CACHE_HOURS = int(os.environ.get("TLE_CACHE_HOURS", 1))
