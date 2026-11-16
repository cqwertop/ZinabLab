from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
STATS_DIR = DATA_DIR / "outputs" / "statistics"
BOUNDARIES_DIR = DATA_DIR / "raw" / "boundaries"
ADM1_FILE = BOUNDARIES_DIR / "eth_adm1.geojson"
CHIRPS_CELLS_FILE = STATS_DIR / "chirps_spatial_monthly.csv"
CHIRPS_NATIONAL_FILE = STATS_DIR / "chirps_monthly_anomalies.csv"
CHIRPS_SEASONAL_FILE = STATS_DIR / "chirps_seasonal_anomalies.csv"
