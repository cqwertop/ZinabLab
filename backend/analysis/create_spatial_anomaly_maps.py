
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
    / "maps"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "spatial_anomalies_2024.png"
)

WEST = 33.0
SOUTH = 3.0
GRID_SIZE = 0.5

YEAR = "2024"


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("Loading anomaly dataset...")

    df = pd.read_csv(INPUT_FILE)

    df["month"] = df["month"].astype(str)

    df = df[
        df["month"].str.startswith(YEAR)
    ].copy()

    if df.empty:
        raise ValueError(
            f"No anomaly data found for {YEAR}."
        )

    print(f"Loaded {len(df)} records for {YEAR}.")

    return df


# ============================================================
# LOAD ETHIOPIA BOUNDARY
# ============================================================

def load_boundary():

    print("Loading Ethiopia boundary...")

    countries = gpd.read_file(
        "zip://" + BOUNDARY_FILE.as_posix()
    )

    countries = countries.to_crs("EPSG:4326")

    ethiopia = countries[
        countries["ADMIN"] == "Ethiopia"
    ]

    if ethiopia.empty:
        raise ValueError(
            "Ethiopia boundary not found."
        )

    return ethiopia.geometry.union_all()


# ============================================================
# CREATE GRID CELL GEOMETRIES
# ============================================================

def create_geometries(df, boundary):

    print("Building grid cell geometries...")

    cells = df[
        ["cell_id", "grid_row", "grid_col"]
    ].drop_duplicates("cell_id").copy()

    geometries = []

    for _, row in cells.iterrows():

        west = WEST + row["grid_col"] * GRID_SIZE
        south = SOUTH + row["grid_row"] * GRID_SIZE

        east = west + GRID_SIZE
        north = south + GRID_SIZE

        cell = box(
            west,
            south,
            east,
            north
        )

        # Clip cell to Ethiopia's actual boundary
        clipped_cell = cell.intersection(boundary)

        geometries.append(clipped_cell)

    cells = gpd.GeoDataFrame(
        cells,
        geometry=geometries,
        crs="EPSG:4326"
    )

    return cells


# ============================================================
# CREATE MONTHLY MAPS
# ============================================================

def create_maps(df, cells, boundary):

    print("Generating monthly maps...")

    months = sorted(df["month"].unique())

    fig, axes = plt.subplots(
        3,
        4,
        figsize=(16, 13)
    )

    axes = axes.flatten()

    # Identical color scale for every month
    norm = Normalize(
        vmin=-2,
        vmax=2
    )

    cmap = "RdBu_r"

    for index, month in enumerate(months):

        ax = axes[index]

        monthly_data = df[
            df["month"] == month
        ]

        # Join rainfall anomaly values to grid geometries
        map_data = cells.merge(
            monthly_data[
                ["cell_id", "z_score", "anomaly_mm"]
            ],
            on="cell_id",
            how="left"
        )

        map_data = gpd.GeoDataFrame(
            map_data,
            geometry="geometry",
            crs="EPSG:4326"
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

        # Draw Ethiopia's national boundary
        gpd.GeoSeries(
            [boundary],
            crs="EPSG:4326"
        ).boundary.plot(
            ax=ax,
            color="black",
            linewidth=0.8
        )

        ax.set_xlim(32.5, 48.5)
        ax.set_ylim(2.5, 15.5)
        ax.set_aspect("equal")

        date = pd.to_datetime(
            month + "-01"
        )

        ax.set_title(
            date.strftime("%B %Y"),
            fontsize=11,
            fontweight="bold"
        )

        ax.set_axis_off()

        print(f"Mapped {month}")

    # Shared colorbar
    sm = ScalarMappable(
        norm=norm,
        cmap=cmap
    )

    sm.set_array([])

    fig.subplots_adjust(
        top=0.91,
        bottom=0.09,
        right=0.90,
        hspace=0.15,
        wspace=0.08
    )

    cax = fig.add_axes(
        [0.92, 0.22, 0.018, 0.55]
    )

    colorbar = fig.colorbar(
        sm,
        cax=cax
    )

    colorbar.set_label(
        "Rainfall anomaly (standard deviations)",
        fontsize=10
    )

    fig.suptitle(
        "Ethiopia Monthly Rainfall Anomalies - 2024",
        fontsize=17,
        fontweight="bold"
    )

    fig.text(
        0.5,
        0.035,
        "Reference: 2015-2024 historical average for "
        "the same calendar month. "
        "Statistical anomalies, not official drought classifications.",
        ha="center",
        fontsize=9
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    plt.savefig(
        OUTPUT_FILE,
        dpi=250,
        bbox_inches="tight"
    )

    plt.close(fig)

    print("\nMAP GENERATION COMPLETE!")
    print(f"Saved to: {OUTPUT_FILE}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 55)
    print("ETHIOPIA SPATIAL ANOMALY MAPPING")
    print("=" * 55)

    df = load_data()

    boundary = load_boundary()

    cells = create_geometries(
        df,
        boundary
    )

    create_maps(
        df,
        cells,
        boundary
    )


if __name__ == "__main__":
    main()
