
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "outputs"
    / "statistics"
    / "chirps_spatial_monthly.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
    / "statistics"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "chirps_spatial_anomalies.csv"
)


# ============================================================
# LOAD DATA
# ============================================================

def main():

    print("=" * 55)
    print("CHIRPS SPATIAL ANOMALY ANALYSIS")
    print("=" * 55)

    print("\nLoading spatial rainfall dataset...")

    df = pd.read_csv(INPUT_FILE)

    # Convert YYYY-MM into a date
    df["date"] = pd.to_datetime(
        df["month"] + "-01"
    )

    # Extract calendar month
    df["calendar_month"] = df["date"].dt.month

    print(f"Loaded {len(df)} records.")
    print(f"Grid cells: {df['cell_id'].nunique()}")

    # ========================================================
    # CALCULATE HISTORICAL CLIMATOLOGY
    # ========================================================

    print("\nCalculating historical climatology...")

    # Each grid cell gets its own normal for each calendar month
    groups = df.groupby(
        ["cell_id", "calendar_month"]
    )["rainfall_mm"]

    df["baseline_mean_mm"] = groups.transform("mean")

    df["baseline_std_mm"] = groups.transform("std")

    # ========================================================
    # CALCULATE ANOMALIES
    # ========================================================

    print("Calculating rainfall anomalies...")

    # Difference from historical normal
    df["anomaly_mm"] = (
        df["rainfall_mm"]
        - df["baseline_mean_mm"]
    )

    # Percentage difference from historical normal
    df["anomaly_percent"] = np.where(
        df["baseline_mean_mm"] != 0,
        (
            df["anomaly_mm"]
            / df["baseline_mean_mm"]
        ) * 100,
        np.nan
    )

    # Standardized anomaly
    df["z_score"] = np.where(
        df["baseline_std_mm"] > 0,
        (
            df["anomaly_mm"]
            / df["baseline_std_mm"]
        ),
        np.nan
    )

    # ========================================================
    # CLASSIFY ANOMALIES
    # ========================================================

    print("Classifying rainfall patterns...")

    conditions = [
        df["z_score"] <= -1,
        df["z_score"] >= 1
    ]

    labels = [
        "Below normal",
        "Above normal"
    ]

    df["anomaly_category"] = np.select(
        conditions,
        labels,
        default="Near normal"
    )

    # These are statistical categories, not official drought
    # classifications.

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    df = df.sort_values(
        ["date", "cell_id"]
    )

    columns = [
        "cell_id",
        "grid_row",
        "grid_col",
        "center_lon",
        "center_lat",
        "month",
        "rainfall_mm",
        "baseline_mean_mm",
        "baseline_std_mm",
        "anomaly_mm",
        "anomaly_percent",
        "z_score",
        "anomaly_category",
        "valid_pixels"
    ]

    df[columns].to_csv(
        OUTPUT_FILE,
        index=False
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 55)
    print("SPATIAL ANOMALY ANALYSIS COMPLETE")
    print("=" * 55)

    print("\nAnomaly categories:")

    print(
        df["anomaly_category"]
        .value_counts()
        .to_string()
    )

    print("\nAverage anomaly (mm):")

    print(
        round(df["anomaly_mm"].mean(), 3)
    )

    print("\nMost unusually dry grid-cell months:")

    print(
        df.nsmallest(10, "z_score")[
            [
                "cell_id",
                "month",
                "rainfall_mm",
                "anomaly_mm",
                "z_score"
            ]
        ].to_string(index=False)
    )

    print("\nMost unusually wet grid-cell months:")

    print(
        df.nlargest(10, "z_score")[
            [
                "cell_id",
                "month",
                "rainfall_mm",
                "anomaly_mm",
                "z_score"
            ]
        ].to_string(index=False)
    )

    print(f"\nSaved results to:\n{OUTPUT_FILE}")

    print("\nDone!")


if __name__ == "__main__":
    main()
