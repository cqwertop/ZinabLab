
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR / "data" / "outputs" / "statistics"
    / "chirps_ethiopia_monthly.csv"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "outputs" / "statistics"
    / "baseline_comparison.csv"
)


def main():
    df = pd.read_csv(INPUT_FILE, dtype={"month": str})

    df["date"] = pd.to_datetime(
        df["month"], format="%Y.%m"
    )

    df["year"] = df["date"].dt.year
    df["month_number"] = df["date"].dt.month

    results = []

    for _, row in df[df["year"] >= 2020].iterrows():

        previous = df[
            (df["year"] < row["year"])
            & (df["month_number"] == row["month_number"])
        ]

        if previous.empty:
            continue

        actual = row["mean_rainfall_mm"]

        climatology_prediction = (
            previous["mean_rainfall_mm"].mean()
        )

        previous_year = df[
            (df["year"] == row["year"] - 1)
            & (df["month_number"] == row["month_number"])
        ]

        if previous_year.empty:
            continue

        persistence_prediction = (
            previous_year["mean_rainfall_mm"].iloc[0]
        )

        results.append({
            "date": row["date"].strftime("%Y-%m"),
            "actual_mm": actual,
            "climatology_prediction_mm": climatology_prediction,
            "persistence_prediction_mm": persistence_prediction,
            "climatology_error_mm": (
                actual - climatology_prediction
            ),
            "persistence_error_mm": (
                actual - persistence_prediction
            )
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_FILE, index=False)

    print("\nBASELINE COMPARISON")

    for model, column in [
        ("Climatology", "climatology_error_mm"),
        ("Persistence", "persistence_error_mm")
    ]:
        errors = results_df[column]

        mae = np.mean(np.abs(errors))
        rmse = np.sqrt(np.mean(errors ** 2))

        print(f"\n{model}")
        print(f"MAE:  {mae:.3f} mm")
        print(f"RMSE: {rmse:.3f} mm")

    print("\nSaved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
