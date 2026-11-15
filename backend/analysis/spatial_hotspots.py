
from pathlib import Path

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
    / "chirps_spatial_anomalies.csv"
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

GRID_SIZE = 0.5
WEST = 33.0
SOUTH = 3.0


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("Loading spatial anomaly data...")

    df = pd.read_csv(INPUT_FILE)

    required = [
        "cell_id",
        "grid_row",
        "grid_col",
        "center_lon",
        "center_lat",
        "rainfall_mm",
        "z_score"
    ]

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    print(f"Loaded {len(df)} records.")

    return df


# ============================================================
# CALCULATE PERSISTENT HOTSPOTS
# ============================================================

def calculate_hotspots(df):

    print("\nCalculating persistent rainfall patterns...")

    # Only use months with valid standardized anomalies
    valid = df.dropna(
        subset=["z_score"]
    ).copy()

    valid["dry_month"] = (
        valid["z_score"] <= -1
    )

    valid["wet_month"] = (
        valid["z_score"] >= 1
    )

    summary = valid.groupby(
        "cell_id"
    ).agg(
        grid_row=("grid_row", "first"),
        grid_col=("grid_col", "first"),
        center_lon=("center_lon", "first"),
        center_lat=("center_lat", "first"),
        valid_months=("z_score", "count"),
        dry_months=("dry_month", "sum"),
        wet_months=("wet_month", "sum"),
        mean_rainfall_mm=("rainfall_mm", "mean"),
        mean_z_score=("z_score", "mean")
    ).reset_index()

    # Calculate percentages
    summary["dry_frequency_percent"] = (
        summary["dry_months"]
        / summary["valid_months"]
        * 100
    )

    summary["wet_frequency_percent"] = (
        summary["wet_months"]
        / summary["valid_months"]
        * 100
    )

    # Net difference between wet and dry frequencies
    summary["wet_minus_dry_percent"] = (
        summary["wet_frequency_percent"]
        - summary["dry_frequency_percent"]
    )

    summary = summary.sort_values(
        "dry_frequency_percent",
        ascending=False
    )

    return summary


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

def build_grid(summary, boundary):

    print("\nBuilding grid geometries...")

    geometries = []

    for _, row in summary.iterrows():

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

    grid = gpd.GeoDataFrame(
        summary.copy(),
        geometry=geometries,
        crs="EPSG:4326"
    )

    return grid


# ============================================================
# CREATE HOTSPOT MAPS
# ============================================================

def create_maps(grid):

    print("\nGenerating hotspot maps...")

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15, 9)
    )

    map_settings = [
        (
            "dry_frequency_percent",
            "YlOrRd",
            "Frequency of unusually dry months"
        ),
        (
            "wet_frequency_percent",
            "YlGnBu",
            "Frequency of unusually wet months"
        )
    ]

    for ax, (column, cmap, title) in zip(
        axes,
        map_settings
    ):

        grid.plot(
            column=column,
            ax=ax,
            cmap=cmap,
            norm=Normalize(0, 100),
            edgecolor="none",
            legend=False
        )

        grid.boundary.plot(
            ax=ax,
            color="black",
            linewidth=0.25
        )

        ax.set_title(
            title,
            fontsize=12,
            fontweight="bold"
        )

        ax.set_xlim(32.5, 48.5)
        ax.set_ylim(2.5, 15.5)
        ax.set_aspect("equal")
        ax.set_axis_off()

        sm = ScalarMappable(
            norm=Normalize(0, 100),
            cmap=cmap
        )

        sm.set_array([])

        fig.colorbar(
            sm,
            ax=ax,
            fraction=0.035,
            pad=0.02,
            label="Months (%)"
        )

    fig.suptitle(
        "Ethiopia Persistent Rainfall Anomalies (2015–2024)",
        fontsize=16,
        fontweight="bold"
    )

    fig.text(
        0.5,
        0.035,
        "Dry: z-score <= -1 | Wet: z-score >= +1. "
        "Percentages use months with valid z-scores.",
        ha="center",
        fontsize=9
    )

    MAP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        MAP_DIR
        / "ethiopia_persistent_rainfall_hotspots.png"
    )

    plt.savefig(
        output_file,
        dpi=250,
        bbox_inches="tight"
    )

    plt.close(fig)

    print(f"Map saved to: {output_file}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 55)
    print("PERSISTENT RAINFALL HOTSPOT ANALYSIS")
    print("=" * 55)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    df = load_data()

    summary = calculate_hotspots(df)

    boundary = load_boundary()

    grid = build_grid(
        summary,
        boundary
    )

    # Save numerical results
    csv_file = (
        OUTPUT_DIR
        / "chirps_persistent_hotspots.csv"
    )

    summary.to_csv(
        csv_file,
        index=False
    )

    # Generate maps
    create_maps(grid)

    print("\n" + "=" * 55)
    print("PERSISTENT HOTSPOT ANALYSIS COMPLETE")
    print("=" * 55)

    print("\nGrid cells analyzed:")
    print(len(summary))

    print("\nHighest dry-month frequencies:")
    print(
        summary.nlargest(
            10,
            "dry_frequency_percent"
        )[
            [
                "cell_id",
                "dry_frequency_percent",
                "wet_frequency_percent",
                "mean_rainfall_mm"
            ]
        ].to_string(index=False)
    )

    print("\nHighest wet-month frequencies:")
    print(
        summary.nlargest(
            10,
            "wet_frequency_percent"
        )[
            [
                "cell_id",
                "wet_frequency_percent",
                "dry_frequency_percent",
                "mean_rainfall_mm"
            ]
        ].to_string(index=False)
    )

    print(f"\nCSV saved to: {csv_file}")


if __name__ == "__main__":
    main()
