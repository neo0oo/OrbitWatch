from pathlib import Path
import os

DATA_DIR = Path(__file__).resolve().parent.parent

CELESTRAK_URL = os.environ.get("CELESTRAK_URL", "https://celestrak.org/NORAD/elements/gp.php")
TLE_REFRESH_HOURS = int(os.environ.get("TLE_REFRESH_HOURS", 6))
