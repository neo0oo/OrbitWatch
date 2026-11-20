import os

PORT = int(os.environ.get("PORT", 8000))

CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:8001")
CATALOG_TIMEOUT_S = float(os.environ.get("CATALOG_TIMEOUT_S", 5))
GIT_SHA = os.environ.get("GIT_SHA", "dev")
ALLOWED_ORIGINS = [o for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o]
DATABASE_URL = os.environ.get("DATABASE_URL")
TLE_CACHE_HOURS = int(os.environ.get("TLE_CACHE_HOURS", 1))
