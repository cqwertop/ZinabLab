
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

from shapely.geometry import box
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


# ============================================================
# PATHS AND SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "outputs"
    / "statistics"
    / "chirps_spatial_monthly.csv"
)

BOUNDARY_FILE = (
    BASE_DIR
    / "data"
    / "raw"
    / "boundaries"
    / "countries.zip"
)

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
    / "statistics"
)

MAP_DIR = (
    BASE_DIR
    / "data"
    / "outputs"
    / "maps"
)

WEST = 33.0
SOUTH = 3.0
GRID_SIZE = 0.5


# ============================================================
# SEASON DEFINITIONS
# ============================================================

SEASONS = {
    "Belg": [2, 3, 4, 5],
    "Kiremt": [6, 7, 8, 9],
    "Bega": [10, 11, 12, 1]
}

SEASON_DESCRIPTIONS = {
    "Belg": "February-May",
    "Kiremt": "June-September",
    "Bega": "October-January"
}


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("Loading CHIRPS spatial dataset...")

    df = pd.read_csv(INPUT_FILE)

    df["date"] = pd.to_datetime(
        df["month"] + "-01"
    )

    df["year"] = df["date"].dt.year
    df["calendar_month"] = df["date"].dt.month

    print(f"Loaded {len(df)} monthly records.")
    print(f"Grid cells: {df['cell_id'].nunique()}")

    return df


# ============================================================
# ASSIGN SEASONS
# ============================================================

def assign_seasons(df):

    print("\nAssigning rainfall seasons...")

    df = df.copy()

    df["season"] = None

    df.loc[
        df["calendar_month"].isin([2, 3, 4, 5]),
        "season"
    ] = "Belg"

    df.loc[
        df["calendar_month"].isin([6, 7, 8, 9]),
        "season"
    ] = "Kiremt"

    df.loc[
        df["calendar_month"].isin([10, 11, 12, 1]),
        "season"
    ] = "Bega"

    # Bega starts in October.
    # January belongs to the Bega season that started
    # in the previous calendar year.

    df["season_year"] = df["year"]

    january = (
        (df["season"] == "Bega")
        & (df["calendar_month"] == 1)
    )

    df.loc[january, "season_year"] -= 1

    return df


# ============================================================
# CALCULATE SEASONAL TOTALS
# ============================================================

def calculate_seasonal_totals(df):

    print("\nCalculating seasonal rainfall totals...")

    seasonal = (
        df.groupby(
            ["cell_id", "season", "season_year"]
        )
        .agg(
            grid_row=("grid_row", "first"),
            grid_col=("grid_col", "first"),
            center_lon=("center_lon", "first"),
            center_lat=("center_lat", "first"),
            rainfall_mm=("rainfall_mm", "sum"),
            valid_months=("rainfall_mm", "count")
        )
        .reset_index()
    )

    # Keep only complete four-month seasons.
    seasonal = seasonal[
        seasonal["valid_months"] == 4
    ].copy()

    print("\nComplete seasons available:")

    print(
        seasonal.groupby("season")[
            "season_year"
        ].nunique().to_string()
    )

    return seasonal


# ============================================================
# CALCULATE SEASONAL ANOMALIES
# ============================================================

def calculate_anomalies(seasonal):

    print("\nCalculating seasonal climatologies...")

    groups = seasonal.groupby(
        ["cell_id", "season"]
    )["rainfall_mm"]

    seasonal["baseline_mean_mm"] = (
        groups.transform("mean")
    )

    seasonal["baseline_std_mm"] = (
        groups.transform("std")
    )

    seasonal["anomaly_mm"] = (
        seasonal["rainfall_mm"]
        - seasonal["baseline_mean_mm"]
    )

    seasonal["anomaly_percent"] = np.where(
        seasonal["baseline_mean_mm"] != 0,
        (
            seasonal["anomaly_mm"]
            / seasonal["baseline_mean_mm"]
        ) * 100,
        np.nan
    )

    seasonal["z_score"] = np.where(
        seasonal["baseline_std_mm"] > 0,
        (
            seasonal["anomaly_mm"]
            / seasonal["baseline_std_mm"]
        ),
        np.nan
    )

    conditions = [
        seasonal["z_score"] <= -1,
        seasonal["z_score"] >= 1
    ]

    labels = [
        "Below normal",
        "Above normal"
    ]

    seasonal["anomaly_category"] = np.select(
        conditions,
        labels,
        default="Near normal"
    )

    return seasonal


# ============================================================
# LOAD ETHIOPIA BOUNDARY
# ============================================================

def load_boundary():

    print("\nLoading Ethiopia boundary...")

    countries = gpd.read_file(
        "zip://" + BOUNDARY_FILE.as_posix()
    )

    countries = countries.to_crs(
        "EPSG:4326"
    )

    ethiopia = countries[
        countries["ADMIN"] == "Ethiopia"
    ]

    if ethiopia.empty:
        raise ValueError(
            "Ethiopia boundary not found."
        )

    return ethiopia.geometry.union_all()


# ============================================================
# BUILD GRID GEOMETRIES
# ============================================================

def build_grid(seasonal, boundary):

    cells = seasonal[
        [
            "cell_id",
            "grid_row",
            "grid_col"
        ]
    ].drop_duplicates("cell_id").copy()

    geometries = []

    for _, row in cells.iterrows():

        west = (
            WEST
            + row["grid_col"] * GRID_SIZE
        )

        south = (
            SOUTH
            + row["grid_row"] * GRID_SIZE
        )

        cell = box(
            west,
            south,
            west + GRID_SIZE,
            south + GRID_SIZE
        )

        geometries.append(
            cell.intersection(boundary)
        )

    return gpd.GeoDataFrame(
        cells,
        geometry=geometries,
        crs="EPSG:4326"
    )


# ============================================================
# GENERATE SEASONAL MAPS
# ============================================================

def create_maps(seasonal, grid):

    print("\nGenerating seasonal maps...")

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(17, 8)
    )

    norm = Normalize(
        vmin=-2,
        vmax=2
    )

    cmap = "RdBu_r"

    for ax, season_name in zip(
        axes,
        ["Belg", "Kiremt", "Bega"]
    ):

        season_data = seasonal[
            seasonal["season"] == season_name
        ].copy()

        if season_data.empty:
            ax.set_title(
                f"{season_name}: No complete data"
            )
            ax.set_axis_off()
            continue

        # Use the latest complete season
        latest_year = int(
            season_data["season_year"].max()
        )

        latest = season_data[
            season_data["season_year"] == latest_year
        ]

        map_data = grid.merge(
            latest[
                ["cell_id", "z_score"]
            ],
            on="cell_id",
            how="left"
        )

        map_data.plot(
            column="z_score",
            ax=ax,
            cmap=cmap,
            norm=norm,
            edgecolor="none",
            legend=False,
            missing_kwds={
                "color": "lightgrey"
            }
        )

        grid.boundary.plot(
            ax=ax,
            color="black",
            linewidth=0.25
        )

        if season_name == "Bega":
            year_label = (
                f"{latest_year}-{latest_year + 1}"
            )
        else:
            year_label = str(latest_year)

        ax.set_title(
            f"{season_name} ({year_label})",
            fontsize=13,
            fontweight="bold"
        )

        ax.set_xlim(32.5, 48.5)
        ax.set_ylim(2.5, 15.5)
        ax.set_aspect("equal")
        ax.set_axis_off()

        print(
            f"Mapped {season_name}: {year_label}"
        )

    sm = ScalarMappable(
        norm=norm,
        cmap=cmap
    )

    sm.set_array([])

    fig.colorbar(
        sm,
        ax=axes.tolist(),
        orientation="horizontal",
        fraction=0.045,
        pad=0.08,
        label="Seasonal rainfall anomaly (standard deviations)"
    )

    fig.suptitle(
        "Ethiopia Seasonal Rainfall Anomalies",
        fontsize=17,
        fontweight="bold"
    )

    fig.text(
        0.5,
        0.015,
        "Blue = below normal | White = near normal | "
        "Red = above normal. "
        "Reference: 2015-2024 seasonal climatology.",
        ha="center",
        fontsize=9
    )

    MAP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        MAP_DIR
        / "ethiopia_seasonal_anomalies.png"
    )

    plt.savefig(
        output_file,
        dpi=250,
        bbox_inches="tight"
    )

    plt.close(fig)

    print(f"\nMap saved to: {output_file}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("ETHIOPIA SEASONAL RAINFALL ANALYSIS")
    print("=" * 60)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    df = load_data()

    df = assign_seasons(df)

    seasonal = calculate_seasonal_totals(df)

    seasonal = calculate_anomalies(seasonal)

    # Save seasonal results
    output_csv = (
        OUTPUT_DIR
        / "chirps_spatial_seasonal_anomalies.csv"
    )

    seasonal.to_csv(
        output_csv,
        index=False
    )

    boundary = load_boundary()

    grid = build_grid(
        seasonal,
        boundary
    )

    create_maps(
        seasonal,
        grid
    )

    print("\n" + "=" * 60)
    print("SEASONAL ANALYSIS COMPLETE!")
    print("=" * 60)

    print("\nSeasonal records:")
    print(len(seasonal))

    print("\nUnique grid cells:")
    print(seasonal["cell_id"].nunique())

    print("\nSeasons available:")
    print(
        seasonal.groupby("season")[
            "season_year"
        ].nunique().to_string()
    )

    print("\nAverage seasonal rainfall (mm):")

    print(
        seasonal.groupby("season")[
            "rainfall_mm"
        ].mean().round(2).to_string()
    )

    print("\nSeasonal anomaly categories:")

    print(
        seasonal.groupby(
            ["season", "anomaly_category"]
        ).size().to_string()
    )

    print(f"\nCSV saved to: {output_csv}")


if __name__ == "__main__":
    main()
