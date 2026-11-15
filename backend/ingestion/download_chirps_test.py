
from pathlib import Path
import requests
import rasterio
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_DIR = BASE_DIR / "data" / "raw" / "chirps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

YEAR = 2015
MONTH = 1

FILENAME = f"chirps-v3.0.{YEAR}.{MONTH:02d}.tif"

URL = (
    "https://data.chc.ucsb.edu/products/CHIRPS/"
    "v3.0/monthly/africa/tifs/"
    + FILENAME
)

OUTPUT_FILE = OUTPUT_DIR / FILENAME


def download():
    if OUTPUT_FILE.exists():
        print("File already exists. Skipping download.")
        return

    print("Downloading:", FILENAME)

    response = requests.get(URL, stream=True, timeout=120)
    response.raise_for_status()

    with open(OUTPUT_FILE, "wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)

    print("Download complete!")


def inspect():
    print("\nInspecting GeoTIFF...")

    with rasterio.open(OUTPUT_FILE) as dataset:
        rainfall = dataset.read(1, masked=True)

        print("CRS:", dataset.crs)
        print("Dimensions:", dataset.width, "x", dataset.height)
        print("Bounds:", dataset.bounds)
        print("NoData:", dataset.nodata)

        valid = rainfall.compressed()

        print("Valid pixels:", len(valid))

        if len(valid) > 0:
            print("Minimum rainfall:", float(np.min(valid)), "mm")
            print("Maximum rainfall:", float(np.max(valid)), "mm")
            print("Mean pixel rainfall:", float(np.mean(valid)), "mm")


if __name__ == "__main__":
    download()
    inspect()
