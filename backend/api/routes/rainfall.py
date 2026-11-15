
from pathlib import Path
import json
from pathlib import Path
from fastapi import Query

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_FILE = (
    BASE_DIR
    / "data"
    / "outputs"
    / "statistics"
    / "gpm_ethiopia_daily.csv"
)


@router.get("/rainfall")
def get_rainfall():
    if not DATA_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Rainfall data has not been generated yet."
        )

    df = pd.read_csv(DATA_FILE)

    return {
        "region": "Ethiopia (approximate bounding box)",
        "unit": "mm/day",
        "observations": df.to_dict(orient="records"),
        "count": len(df)
    }



MAP_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "outputs"
    / "maps"
    / "ethiopia_rainfall.geojson"
)


@router.get("/rainfall/map")
def get_rainfall_map(date: str | None = Query(default=None)):
    if not MAP_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Rainfall map has not been generated."
        )

    with open(MAP_FILE, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    if date:
        geojson["features"] = [
            feature
            for feature in geojson["features"]
            if feature["properties"]["date"] == date
        ]

    return geojson

