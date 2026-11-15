
from pathlib import Path
import xarray as xr

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw" / "gpm"

files = list(DATA_DIR.glob("*.nc4"))

if not files:
    print("No NetCDF files found!")
else:
    file = files[0]

    print("Inspecting:", file.name)

    with xr.open_dataset(file) as ds:
        print("\nVARIABLES:")
        print(list(ds.variables))

        print("\nDIMENSIONS:")
        print(ds.sizes)

        print("\nPRECIPITATION DETAILS:")
        if "precipitation" in ds:
            print(ds["precipitation"])
        else:
            print("Precipitation variable not found.")
