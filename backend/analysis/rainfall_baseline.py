
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]

STATS_DIR = BASE_DIR / "data" / "outputs" / "statistics"

INPUT_FILE = STATS_DIR / "chirps_ethiopia_monthly.csv"

BACKTEST_FILE = STATS_DIR / "rainfall_baseline_backtest.csv"
FORECAST_FILE = STATS_DIR / "rainfall_baseline_2025.csv"


def load_data():
    df = pd.read_csv(INPUT_FILE, dtype={"month": str})

    df["date"] = pd.to_datetime(
        df["month"], format="%Y.%m"
    )

    df["year"] = df["date"].dt.year
    df["month_number"] = df["date"].dt.month

    return df.sort_values("date").reset_index(drop=True)


def backtest(df):
    print("Testing historical predictions...")

    results = []

    for _, row in df[df["year"] >= 2020].iterrows():

        # Only use data available before the prediction year.
        training = df[
            (df["year"] < row["year"])
            & (df["month_number"] == row["month_number"])
        ]

        if len(training) < 3:
            continue

        prediction = training["mean_rainfall_mm"].mean()

        actual = row["mean_rainfall_mm"]

        results.append({
            "date": row["date"].strftime("%Y-%m"),
            "actual_mm": actual,
            "predicted_mm": prediction,
            "error_mm": actual - prediction
        })

    results_df = pd.DataFrame(results)

    if results_df.empty:
        raise ValueError("Not enough historical data for backtesting.")

    results_df.to_csv(BACKTEST_FILE, index=False)

    errors = results_df["error_mm"]

    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors ** 2))

    print("\nBACKTEST RESULTS")
    print("Observations:", len(results_df))
    print(f"MAE: {mae:.3f} mm")
    print(f"RMSE: {rmse:.3f} mm")

    return results_df


def forecast_2025(df):
    print("\nGenerating 2025 baseline...")

    results = []

    for month in range(1, 13):

        historical = df[
            df["month_number"] == month
        ]["mean_rainfall_mm"]

        results.append({
            "date": f"2025-{month:02d}",
            "predicted_rainfall_mm": round(
                float(historical.mean()), 3
            ),
            "historical_p10_mm": round(
                float(historical.quantile(0.10)), 3
            ),
            "historical_p90_mm": round(
                float(historical.quantile(0.90)), 3
            )
        })

    forecast_df = pd.DataFrame(results)
    forecast_df.to_csv(FORECAST_FILE, index=False)

    print("2025 baseline forecast saved.")
    print(forecast_df.to_string(index=False))


def main():
    df = load_data()

    backtest(df)
    forecast_2025(df)

    print("\nBASELINE MODEL COMPLETE!")
    print("Backtest:", BACKTEST_FILE)
    print("Forecast:", FORECAST_FILE)


if __name__ == "__main__":
    main()
