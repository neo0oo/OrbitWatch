import os

PORT = int(os.environ.get("PORT", 8000))
DATA_DIR = os.environ.get("DATA_DIR", "./data")
CELESTRAK_URL = os.environ.get("CELESTRAK_URL", "https://celestrak.org/NORAD/elements/gp.php")
TLE_REFRESH_HOURS = int(os.environ.get("TLE_REFRESH_HOURS", 6))