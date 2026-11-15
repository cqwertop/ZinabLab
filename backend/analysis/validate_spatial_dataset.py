
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "outputs"
    / "statistics"
    / "chirps_spatial_monthly.csv"
)

df = pd.read_csv(INPUT_FILE)

print("\n========== DATASET VALIDATION ==========")

print("\nShape:")
print(df.shape)

print("\nDate range:")
print(df["month"].min(), "to", df["month"].max())

print("\nUnique grid cells:")
print(df["cell_id"].nunique())

print("\nUnique months:")
print(df["month"].nunique())

print("\nMissing values:")
print(df.isnull().sum())

print("\nRainfall statistics (mm/month):")
print(df["rainfall_mm"].describe())

print("\nNegative rainfall values:")
print((df["rainfall_mm"] < 0).sum())

print("\nDuplicate cell-month records:")
print(df.duplicated(["cell_id", "month"]).sum())

print("\nMonths per grid cell:")
print(df.groupby("cell_id")["month"].nunique().describe())

print("\n========================================")
