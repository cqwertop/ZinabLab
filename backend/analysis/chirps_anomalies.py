
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parents[1]

STATS_DIR = BASE_DIR / "data" / "outputs" / "statistics"

MONTHLY_FILE = STATS_DIR / "chirps_ethiopia_monthly.csv"
SEASONAL_FILE = STATS_DIR / "chirps_seasonal_rainfall.csv"

MONTHLY_OUTPUT = STATS_DIR / "chirps_monthly_anomalies.csv"
SEASONAL_OUTPUT = STATS_DIR / "chirps_seasonal_anomalies.csv"

CHART_DIR = BASE_DIR / "data" / "outputs" / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)


def calculate_monthly_anomalies():
    print("Calculating monthly rainfall anomalies...")

    df = pd.read_csv(MONTHLY_FILE, dtype={"month": str})

    # Convert YYYY.MM into a proper date.
    df["date"] = pd.to_datetime(
        df["month"], format="%Y.%m"
    )

    df["year"] = df["date"].dt.year
    df["month_number"] = df["date"].dt.month

    # Calculate normal rainfall for each calendar month.
    climatology = (
        df.groupby("month_number")["mean_rainfall_mm"]
        .agg(["mean", "std"])
        .rename(columns={
            "mean": "normal_rainfall_mm",
            "std": "rainfall_std_mm"
        })
    )

    df = df.join(climatology, on="month_number")

    # Actual rainfall minus normal rainfall.
    df["anomaly_mm"] = (
        df["mean_rainfall_mm"] - df["normal_rainfall_mm"]
    )

    # Standardized anomaly.
    df["anomaly_z_score"] = (
        df["anomaly_mm"] / df["rainfall_std_mm"]
    )

    df.to_csv(MONTHLY_OUTPUT, index=False)

    print("Monthly anomalies saved.")

    # Plot monthly anomalies.
    plt.figure(figsize=(14, 6))

    plt.plot(
        df["date"],
        df["anomaly_mm"],
        linewidth=1.5
    )

    plt.axhline(0, linestyle="--", linewidth=1)

    plt.title("Ethiopia Monthly Rainfall Anomalies (2015–2024)")
    plt.xlabel("Date")
    plt.ylabel("Rainfall anomaly (mm)")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    plt.savefig(
        CHART_DIR / "monthly_rainfall_anomalies.png",
        dpi=200
    )

    plt.close()


def calculate_seasonal_anomalies():
    print("Calculating seasonal rainfall anomalies...")

    df = pd.read_csv(SEASONAL_FILE)

    # Compare each season against the historical average
    # for that same season.
    grouped = df.groupby("season")["rainfall_mm"]

    df["normal_rainfall_mm"] = grouped.transform("mean")
    df["rainfall_std_mm"] = grouped.transform(
        lambda values: values.std(ddof=0)
    )

    df["anomaly_mm"] = (
        df["rainfall_mm"] - df["normal_rainfall_mm"]
    )

    df["anomaly_z_score"] = (
        df["anomaly_mm"] / df["rainfall_std_mm"]
    )

    df.to_csv(SEASONAL_OUTPUT, index=False)

    print("Seasonal anomalies saved.")

    # Plot seasonal standardized anomalies.
    plt.figure(figsize=(12, 6))

    for season in ["Belg", "Kiremt", "Bega"]:
        season_data = df[df["season"] == season]

        plt.plot(
            season_data["season_year"],
            season_data["anomaly_z_score"],
            marker="o",
            label=season
        )

    plt.axhline(0, linestyle="--", linewidth=1)

    plt.title("Ethiopia Seasonal Rainfall Anomalies")
    plt.xlabel("Season year")
    plt.ylabel("Standardized rainfall anomaly")
    plt.legend(title="Season")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    plt.savefig(
        CHART_DIR / "seasonal_rainfall_anomalies.png",
        dpi=200
    )

    plt.close()


def main():
    calculate_monthly_anomalies()
    calculate_seasonal_anomalies()

    print("\nANALYSIS COMPLETE!")
    print("Monthly anomaly CSV:", MONTHLY_OUTPUT)
    print("Seasonal anomaly CSV:", SEASONAL_OUTPUT)
    print("Charts saved in:", CHART_DIR)


if __name__ == "__main__":
    main()
