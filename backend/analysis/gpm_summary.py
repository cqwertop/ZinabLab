
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# Find the backend directory regardless of where the script is run
BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "data" / "raw" / "gpm"
OUTPUT_DIR = BASE_DIR / "data" / "outputs" / "statistics"

# Approximate Ethiopia bounding box
WEST, SOUTH, EAST, NORTH = 33.0, 3.0, 48.0, 15.0


def summarize_gpm():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        list(INPUT_DIR.glob("*.nc4")) +
        list(INPUT_DIR.glob("*.nc"))
    )

    if not files:
        print("No NetCDF files found in:", INPUT_DIR)
        return

    results = []

    print(f"Found {len(files)} GPM files.")

    for file in files:
        print(f"\nProcessing: {file.name}")

        try:
            with xr.open_dataset(file, engine="netcdf4") as ds:

                # Check that the expected variables exist
                required = ["precipitation", "lat", "lon"]
                missing = [v for v in required if v not in ds.variables]

                if missing:
                    print("Missing variables:", missing)
                    print("Available variables:", list(ds.variables))
                    continue

                # Handle either ascending or descending coordinates
                lat = ds["lat"]
                lon = ds["lon"]

                lat_slice = (
                    slice(SOUTH, NORTH)
                    if lat.values[0] < lat.values[-1]
                    else slice(NORTH, SOUTH)
                )

                lon_slice = (
                    slice(WEST, EAST)
                    if lon.values[0] < lon.values[-1]
                    else slice(EAST, WEST)
                )

                # Extract Ethiopia's approximate bounding box
                region = ds["precipitation"].sel(
                    lat=lat_slice,
                    lon=lon_slice
                )

                # Ignore invalid values
                region = region.where(np.isfinite(region))

                # Weight grid cells by latitude
                weights = np.cos(np.deg2rad(region["lat"]))

                # Calculate area-weighted regional mean
                average = region.weighted(weights).mean(
                    dim=("lat", "lon"),
                    skipna=True
                )

                value = float(average.mean().values)

                # Daily IMERG precipitation is measured in mm/day
                results.append({
                    "file": file.name,
                    "rainfall_mm_per_day": value,
                    "units": "mm/day"
                })

                print(f"Average precipitation: {value:.3f} mm/day")

        except Exception as error:
            print(f"Could not process {file.name}: {error}")

    if not results:
        print("\nNo files could be processed.")
        return

    # Save results
    dataframe = pd.DataFrame(results)

    output_file = OUTPUT_DIR / "gpm_ethiopia_daily.csv"
    dataframe.to_csv(output_file, index=False)

    print("\n------------------------------")
    print("GPM ANALYSIS COMPLETE")
    print("------------------------------")
    print(dataframe.to_string(index=False))
    print(f"\nSaved results to: {output_file}")


if __name__ == "__main__":
    summarize_gpm()
