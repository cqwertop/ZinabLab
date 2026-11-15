
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR / "data" / "outputs" / "statistics"
    / "chirps_ethiopia_monthly.csv"
)

OUTPUT_DIR = BASE_DIR / "data" / "outputs" / "statistics"

def main():
    df = pd.read_csv(INPUT_FILE, dtype={"month": str})

    # Extract year and month from YYYY.MM
    df["year"] = df["month"].str[:4].astype(int)
    df["month_number"] = df["month"].str[-2:].astype(int)

    # Average rainfall for each calendar month across all years
    monthly_climatology = (
        df.groupby("month_number")["mean_rainfall_mm"]
        .mean()
        .reset_index()
    )

    monthly_climatology.columns = [
        "month_number",
        "average_rainfall_mm"
    ]

    monthly_climatology.to_csv(
        OUTPUT_DIR / "chirps_monthly_climatology.csv",
        index=False
    )

    # Define Ethiopian seasonal groupings
    seasons = {
        "Belg": [2, 3, 4, 5],
        "Kiremt": [6, 7, 8, 9],
        "Bega": [10, 11, 12, 1]
    }

    seasonal_results = []

    for year in sorted(df["year"].unique()):

        for season, months in seasons.items():

            if season == "Bega":
                # Bega runs October through January.
                # January belongs to the following calendar year.
                season_data = df[
                    (
                        (df["year"] == year)
                        & (df["month_number"].isin([10, 11, 12]))
                    )
                    |
                    (
                        (df["year"] == year + 1)
                        & (df["month_number"] == 1)
                    )
                ]

            else:
                season_data = df[
                    (df["year"] == year)
                    & (df["month_number"].isin(months))
                ]

            if len(season_data) != 4:
                continue

            seasonal_results.append({
                "season_year": year,
                "season": season,
                "rainfall_mm": round(
                    season_data["mean_rainfall_mm"].sum(), 3
                )
            })

    seasonal_df = pd.DataFrame(seasonal_results)

    seasonal_df.to_csv(
        OUTPUT_DIR / "chirps_seasonal_rainfall.csv",
        index=False
    )

    print("\nSEASONAL ANALYSIS COMPLETE!")

    print("\nMonthly climatology:")
    print(monthly_climatology.to_string(index=False))

    print("\nSeasonal rainfall:")
    print(seasonal_df.to_string(index=False))

    print("\nSaved:")
    print("chirps_monthly_climatology.csv")
    print("chirps_seasonal_rainfall.csv")


if __name__ == "__main__":
    main()
