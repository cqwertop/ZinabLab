from functools import lru_cache

import numpy as np
import pandas as pd

from core.paths import CHIRPS_CELLS_FILE, CHIRPS_NATIONAL_FILE, CHIRPS_SEASONAL_FILE
from core.regions import assign_cells, load_regions

DRY_BASELINE_MM = 8.0


@lru_cache(maxsize=1)
def cells_frame() -> pd.DataFrame:
    df = pd.read_csv(CHIRPS_CELLS_FILE)
    df["month_number"] = df["month"].str.slice(5, 7).astype(int)
    stats = df.groupby(["cell_id", "month_number"])["rainfall_mm"].agg(["mean", "std"]).reset_index()
    df = df.merge(stats, on=["cell_id", "month_number"], how="left")
    std = df["std"].replace(0, np.nan)
    z = (df["rainfall_mm"] - df["mean"]) / std
    z = z.where(df["mean"] >= DRY_BASELINE_MM, 0.0)
    df["z"] = z.fillna(0.0).clip(-3, 3)
    return df


@lru_cache(maxsize=1)
def cell_regions() -> dict[str, list[str]]:
    df = cells_frame()
    cells = df.drop_duplicates("cell_id")[["cell_id", "center_lon", "center_lat"]]
    return assign_cells([(r.cell_id, r.center_lon, r.center_lat) for r in cells.itertuples()])


@lru_cache(maxsize=1)
def grid_payload():
    df = cells_frame()
    cells = df.drop_duplicates("cell_id").sort_values(["center_lat", "center_lon"])[["cell_id", "center_lon", "center_lat"]]
    order = list(cells["cell_id"])
    months = sorted(df["month"].unique())
    z_pivot = df.pivot(index="month", columns="cell_id", values="z").reindex(index=months, columns=order)
    mm_pivot = df.pivot(index="month", columns="cell_id", values="rainfall_mm").reindex(index=months, columns=order)
    return {
        "source": "CHIRPS v3.0 monthly (UCSB Climate Hazards Center), aggregated to 0.5° cells",
        "cellSize": 0.5,
        "cells": [{"id": c, "lon": float(x), "lat": float(y)} for c, x, y in cells.itertuples(index=False)],
        "months": months,
        "z": np.round(z_pivot.fillna(0).to_numpy(), 1).tolist(),
        "mm": np.round(mm_pivot.fillna(0).to_numpy(), 0).astype(int).tolist(),
    }


@lru_cache(maxsize=1)
def regional_monthly() -> pd.DataFrame:
    df = cells_frame()
    rows = []
    for region_id, cell_ids in cell_regions().items():
        part = df[df["cell_id"].isin(cell_ids)].groupby("month")["rainfall_mm"].mean().reset_index()
        part["region"] = region_id
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    out["month_number"] = out["month"].str.slice(5, 7).astype(int)
    stats = out.groupby(["region", "month_number"])["rainfall_mm"].agg(["mean", "std"]).reset_index()
    out = out.merge(stats, on=["region", "month_number"], how="left")
    std = out["std"].replace(0, np.nan)
    out["z"] = ((out["rainfall_mm"] - out["mean"]) / std).where(out["mean"] >= DRY_BASELINE_MM, 0.0).fillna(0.0).clip(-3, 3)
    return out.sort_values(["region", "month"]).reset_index(drop=True)


def region_history(region_id: str):
    df = regional_monthly()
    part = df[df["region"] == region_id]
    clim = part.groupby("month_number")["rainfall_mm"].agg(["mean", lambda s: s.quantile(0.1), lambda s: s.quantile(0.9)])
    clim.columns = ["mean", "p10", "p90"]
    yearly = part.assign(year=part["month"].str.slice(0, 4).astype(int)).groupby("year")["rainfall_mm"].sum()
    normal_year = float(yearly.mean())
    return {
        "monthly": [
            {"month": r.month, "rain": round(float(r.rainfall_mm), 1), "normal": round(float(r.mean), 1), "z": round(float(r.z), 2)}
            for r in part.itertuples()
        ],
        "climatology": [
            {"month": int(m), "mean": round(float(row["mean"]), 1), "p10": round(float(row["p10"]), 1), "p90": round(float(row["p90"]), 1)}
            for m, row in clim.iterrows()
        ],
        "years": [{"year": int(y), "rain": round(float(v), 0), "pct": round(float(v / normal_year * 100), 0)} for y, v in yearly.items()],
    }


@lru_cache(maxsize=1)
def national_history():
    monthly = pd.read_csv(CHIRPS_NATIONAL_FILE)
    seasonal = pd.read_csv(CHIRPS_SEASONAL_FILE)
    return {
        "source": "CHIRPS v3.0, Ethiopia national mean",
        "monthly": [
            {
                "month": f"{int(r.year)}-{int(r.month_number):02d}",
                "rain": round(float(r.mean_rainfall_mm), 1),
                "normal": round(float(r.normal_rainfall_mm), 1),
                "anomaly": round(float(r.anomaly_mm), 1),
                "z": round(float(r.anomaly_z_score), 2),
            }
            for r in monthly.itertuples()
        ],
        "seasonal": [
            {
                "year": int(r.season_year),
                "season": r.season,
                "rain": round(float(r.rainfall_mm), 0),
                "normal": round(float(r.normal_rainfall_mm), 0),
                "pct": round(float(r.rainfall_mm / r.normal_rainfall_mm * 100), 0),
                "z": round(float(r.anomaly_z_score), 2),
            }
            for r in seasonal.itertuples()
        ],
    }


def region_cell_count():
    return {k: len(v) for k, v in cell_regions().items()}


def regions_ready():
    return [r.id for r in load_regions()]
