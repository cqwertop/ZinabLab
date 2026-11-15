
from pathlib import Path
import csv
import re

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape, mapping
import geopandas as gpd

BASE_DIR = Path(__file__).resolve().parents[1]

RASTER_DIR = BASE_DIR / "data" / "raw" / "chirps"
BOUNDARY_FILE = BASE_DIR / "data" / "raw" / "boundaries" / "countries.zip"

OUTPUT_DIR = BASE_DIR / "data" / "outputs" / "statistics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "chirps_ethiopia_monthly.csv"


def load_boundary():
    countries = gpd.read_file(BOUNDARY_FILE)
    ethiopia = countries[countries["ADMIN"] == "Ethiopia"]

    if ethiopia.empty:
        raise ValueError("Ethiopia boundary not found.")

    return ethiopia.geometry.union_all()


def calculate_statistics(file, boundary):
    with rasterio.open(file) as dataset:

        # Ensure the country geometry uses the raster's CRS.
        geometry = gpd.GeoSeries(
            [boundary], crs="EPSG:4326"
        ).to_crs(dataset.crs).iloc[0]

        clipped, transform = mask(
            dataset,
            [mapping(geometry)],
            crop=True,
            filled=False
        )

        rainfall = clipped[0]
        values = rainfall.filled(np.nan)

        rows = np.arange(values.shape[0])
        latitudes = (
            transform.f
            + (rows + 0.5) * transform.e
        )

        weights = np.cos(np.deg2rad(latitudes))[:, None]
        weights = np.broadcast_to(weights, values.shape)

        valid = (
            ~np.ma.getmaskarray(rainfall)
            & np.isfinite(values)
        )

        if not np.any(valid):
            return None

        valid_values = values[valid]
        valid_weights = weights[valid]

        mean = np.average(
            valid_values,
            weights=valid_weights
        )

        return {
            "month": file.stem.replace("chirps-v3.0.", ""),
            "mean_rainfall_mm": round(float(mean), 3),
            "median_rainfall_mm": round(
                float(np.median(valid_values)), 3
            ),
            "p90_rainfall_mm": round(
                float(np.percentile(valid_values, 90)), 3
            ),
            "max_rainfall_mm": round(
                float(np.max(valid_values)), 3
            ),
            "valid_pixels": int(len(valid_values))
        }


def main():
    boundary = load_boundary()

    files = sorted(RASTER_DIR.glob("chirps-v3.0.*.tif"))

    if not files:
        print("No CHIRPS files found.")
        return

    results = []

    for index, file in enumerate(files, start=1):
        print(f"Processing {index}/{len(files)}: {file.name}")

        try:
            result = calculate_statistics(file, boundary)

            if result:
                results.append(result)

        except Exception as error:
            print("Error:", error)

    results.sort(key=lambda row: row["month"])

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "month",
                "mean_rainfall_mm",
                "median_rainfall_mm",
                "p90_rainfall_mm",
                "max_rainfall_mm",
                "valid_pixels"
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    print("\nCHIRPS PROCESSING COMPLETE!")
    print("Months processed:", len(results))
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
