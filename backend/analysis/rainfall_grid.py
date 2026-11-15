
from pathlib import Path
import json

import numpy as np
import xarray as xr

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "data" / "raw" / "gpm"
OUTPUT_DIR = BASE_DIR / "data" / "outputs" / "maps"

WEST, SOUTH, EAST, NORTH = 33.0, 3.0, 48.0, 15.0

GRID_SIZE = 0.5  # degrees


def process_file(file):
    features = []

    with xr.open_dataset(file) as ds:

        # Rearrange dimensions into latitude, longitude
        rainfall = ds["precipitation"].squeeze("time").transpose(
            "lat", "lon"
        )

        lats = ds["lat"].values
        lons = ds["lon"].values
        values = rainfall.values

        # Restrict processing to our study-area bounding box
        lat_mask = (lats >= SOUTH) & (lats <= NORTH)
        lon_mask = (lons >= WEST) & (lons <= EAST)

        lats = lats[lat_mask]
        lons = lons[lon_mask]
        values = values[np.ix_(lat_mask, lon_mask)]

        date = str(ds["time"].values[0])[:10]

        lat_edges = np.arange(SOUTH, NORTH + GRID_SIZE, GRID_SIZE)
        lon_edges = np.arange(WEST, EAST + GRID_SIZE, GRID_SIZE)

        for i in range(len(lat_edges) - 1):
            for j in range(len(lon_edges) - 1):

                south = lat_edges[i]
                north = lat_edges[i + 1]
                west = lon_edges[j]
                east = lon_edges[j + 1]

                cell_mask = (
                    (lats[:, None] >= south) &
                    (lats[:, None] < north) &
                    (lons[None, :] >= west) &
                    (lons[None, :] < east)
                )

                cell_values = values[cell_mask]

                valid = np.isfinite(cell_values)

                if not np.any(valid):
                    continue

                # Weight pixels by their latitude
                cell_lats = np.broadcast_to(
                    lats[:, None], values.shape
                )[cell_mask][valid]

                weights = np.cos(np.deg2rad(cell_lats))

                mean_rainfall = float(
                    np.average(cell_values[valid], weights=weights)
                )

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [west, south],
                            [east, south],
                            [east, north],
                            [west, north],
                            [west, south]
                        ]]
                    },
                    "properties": {
                        "date": date,
                        "rainfall_mm_per_day": mean_rainfall,
                        "unit": "mm/day"
                    }
                })

    return features


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(INPUT_DIR.glob("*.nc4"))

    if not files:
        print("No GPM files found.")
        return

    all_features = []

    for file in files:
        print("Processing:", file.name)

        try:
            features = process_file(file)
            all_features.extend(features)
            print(f"Generated {len(features)} grid cells.")

        except Exception as error:
            print(f"Error processing {file.name}: {error}")

    geojson = {
        "type": "FeatureCollection",
        "features": all_features
    }

    output_file = OUTPUT_DIR / "ethiopia_rainfall.geojson"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, allow_nan=False)

    print("\nMAP DATA GENERATED!")
    print("Total features:", len(all_features))
    print("Saved to:", output_file)


if __name__ == "__main__":
    main()
