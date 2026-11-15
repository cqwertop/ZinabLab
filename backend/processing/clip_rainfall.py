
from pathlib import Path
import json
import requests
import geopandas as gpd

from shapely.geometry import shape, mapping
from shapely.ops import unary_union

# Project paths
BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR / "data" / "outputs" / "maps"
    / "ethiopia_rainfall.geojson"
)

OUTPUT_FILE = (
    BASE_DIR / "data" / "outputs" / "maps"
    / "ethiopia_rainfall_clipped.geojson"
)

BOUNDARY_DIR = BASE_DIR / "data" / "raw" / "boundaries"
BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)

BOUNDARY_ZIP = BOUNDARY_DIR / "countries.zip"

BOUNDARY_URL = (
    "https://naturalearth.s3.amazonaws.com/"
    "10m_cultural/ne_10m_admin_0_countries.zip"
)


def download_boundary():
    if BOUNDARY_ZIP.exists():
        print("Country boundary file already downloaded.")
        return

    print("Downloading Natural Earth country boundaries...")

    response = requests.get(BOUNDARY_URL, timeout=120)
    response.raise_for_status()

    BOUNDARY_ZIP.write_bytes(response.content)

    print("Boundary download complete.")


def load_ethiopia_boundary():
    print("Loading country boundaries...")

    countries = gpd.read_file(BOUNDARY_ZIP)

    ethiopia = countries[countries["ADMIN"] == "Ethiopia"]

    if ethiopia.empty:
        raise ValueError("Could not find Ethiopia in boundary dataset.")

    boundary = unary_union(ethiopia.geometry)

    print("Ethiopia boundary loaded.")

    return boundary


def clip_rainfall(boundary):
    print("Loading rainfall GeoJSON...")

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    clipped_features = []

    print("Clipping rainfall grid cells...")

    for feature in geojson["features"]:
        cell = shape(feature["geometry"])

        clipped = cell.intersection(boundary)

        if clipped.is_empty:
            continue

        # Keep only polygon geometry.
        if clipped.geom_type == "GeometryCollection":
            polygons = [
                part for part in clipped.geoms
                if part.geom_type in ("Polygon", "MultiPolygon")
            ]

            if not polygons:
                continue

            clipped = unary_union(polygons)

        if clipped.geom_type not in ("Polygon", "MultiPolygon"):
            continue

        clipped_feature = {
            "type": "Feature",
            "geometry": mapping(clipped),
            "properties": feature["properties"]
        }

        clipped_features.append(clipped_feature)

    output = {
        "type": "FeatureCollection",
        "features": clipped_features
    }

    print("Saving clipped GeoJSON...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, allow_nan=False)

    print("\nCLIPPING COMPLETE!")
    print("Original features:", len(geojson["features"]))
    print("Clipped features:", len(clipped_features))
    print("Saved to:", OUTPUT_FILE)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Rainfall GeoJSON not found: {INPUT_FILE}"
        )

    download_boundary()
    boundary = load_ethiopia_boundary()
    clip_rainfall(boundary)


if __name__ == "__main__":
    main()
