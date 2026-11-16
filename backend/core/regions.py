import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union

from .paths import ADM1_FILE

PROFILES = {
    "Addis Ababa": {
        "id": "addis-ababa",
        "label": "Addis Ababa",
        "points": 1,
        "group": "north",
        "rainy_months": [6, 7, 8, 9],
        "seasons": [
            {"name": "Belg", "months": [3, 4, 5], "role": "short rains"},
            {"name": "Kiremt", "months": [6, 7, 8, 9], "role": "main rains"},
        ],
        "livelihood": "Urban water supply from the Legedadi, Dire and Gefersa reservoirs",
        "sentinel": {"name": "Entoto juniper forest", "note": "The capital's forested ridge holds Kiremt rain that feeds city springs."},
        "aliases": ["addis", "finfinne", "capital"],
    },
    "Afar": {
        "id": "afar",
        "label": "Afar",
        "points": 2,
        "group": "north",
        "rainy_months": [3, 4, 7, 8, 9],
        "seasons": [
            {"name": "Sugum", "months": [3, 4], "role": "short rains"},
            {"name": "Karma", "months": [7, 8, 9], "role": "main rains"},
        ],
        "livelihood": "Pastoralism: camels, goats and cattle moving between dry-season wells and wet-season pasture",
        "sentinel": {"name": "African wild ass", "note": "One of the rarest equids on Earth, it survives in Afar only where Karma rains refill waterholes."},
        "aliases": ["semera", "danakil", "awash"],
    },
    "Amhara": {
        "id": "amhara",
        "label": "Amhara",
        "points": 3,
        "group": "north",
        "rainy_months": [6, 7, 8, 9],
        "seasons": [
            {"name": "Belg", "months": [2, 3, 4, 5], "role": "short rains in the east"},
            {"name": "Kiremt", "months": [6, 7, 8, 9], "role": "main rains"},
        ],
        "livelihood": "Highland teff, wheat and barley farming; Lake Tana and the Blue Nile headwaters",
        "sentinel": {"name": "Gelada and Walia ibex", "note": "Simien Mountains grasslands green up with Kiremt rain; geladas graze almost nothing but grass."},
        "aliases": ["bahir dar", "gondar", "dessie", "simien", "lake tana", "debre markos", "wollo"],
    },
    "Beneshangul Gumu": {
        "id": "benishangul-gumuz",
        "label": "Benishangul-Gumuz",
        "points": 2,
        "group": "north",
        "rainy_months": [5, 6, 7, 8, 9, 10],
        "seasons": [{"name": "Long rains", "months": [5, 6, 7, 8, 9, 10], "role": "single long season"}],
        "livelihood": "Maize and sorghum farming; inflow to the Grand Ethiopian Renaissance Dam",
        "sentinel": {"name": "Abay gorge woodland", "note": "Combretum and bamboo woodland that turns brown fast when May rains are late."},
        "aliases": ["benishangul", "assosa", "gumuz", "gerd"],
    },
    "Dire Dawa": {
        "id": "dire-dawa",
        "label": "Dire Dawa",
        "points": 1,
        "group": "south",
        "rainy_months": [3, 4, 7, 8, 9],
        "seasons": [
            {"name": "Belg", "months": [3, 4, 5], "role": "short rains"},
            {"name": "Kiremt", "months": [7, 8, 9], "role": "main rains"},
        ],
        "livelihood": "Urban and agro-pastoral; groundwater from the Sabian aquifer",
        "sentinel": {"name": "Hamadryas baboon", "note": "Troops follow the dry riverbeds that flash-flood after Belg storms."},
        "aliases": ["dire"],
    },
    "Gambela": {
        "id": "gambela",
        "label": "Gambela",
        "points": 2,
        "group": "north",
        "rainy_months": [4, 5, 6, 7, 8, 9, 10],
        "seasons": [{"name": "Long rains", "months": [4, 5, 6, 7, 8, 9, 10], "role": "single long season"}],
        "livelihood": "Flood-recession farming, fishing and cattle along the Baro and Akobo rivers",
        "sentinel": {"name": "White-eared kob", "note": "Hundreds of thousands migrate across Gambela and South Sudan following floodplain grass."},
        "aliases": ["baro", "akobo"],
    },
    "Hareri": {
        "id": "harari",
        "label": "Harari",
        "points": 1,
        "group": "south",
        "rainy_months": [3, 4, 5, 7, 8, 9],
        "seasons": [
            {"name": "Belg", "months": [3, 4, 5], "role": "short rains"},
            {"name": "Kiremt", "months": [7, 8, 9], "role": "main rains"},
        ],
        "livelihood": "Sorghum, coffee and khat farming on the Harar plateau",
        "sentinel": {"name": "Spotted hyena", "note": "Harar's famous hyenas widen their range into farmland when dry years thin out wild prey."},
        "aliases": ["harar", "hareri"],
    },
    "Oromia": {
        "id": "oromia",
        "label": "Oromia",
        "points": 4,
        "group": "south",
        "rainy_months": [3, 4, 5, 6, 7, 8, 9, 10],
        "seasons": [
            {"name": "Belg / Ganna", "months": [3, 4, 5], "role": "short rains, main rains in Borena"},
            {"name": "Kiremt", "months": [6, 7, 8, 9], "role": "main rains in the highlands"},
            {"name": "Hagaya", "months": [10, 11], "role": "short rains in Borena and Guji"},
        ],
        "livelihood": "Coffee, maize and wheat in the highlands; Borena and Guji pastoralists in the south",
        "sentinel": {"name": "Ethiopian wolf", "note": "Africa's rarest carnivore hunts giant mole-rats on the Bale plateau, where rain sets the rodent boom."},
        "aliases": ["adama", "jimma", "borena", "borana", "bale", "nekemte", "guji", "arsi", "shashemene", "nazret"],
    },
    "SNNPR": {
        "id": "snnpr",
        "label": "South (SNNPR)",
        "points": 3,
        "group": "south",
        "rainy_months": [3, 4, 5, 6, 7, 8, 9, 10],
        "seasons": [
            {"name": "Belg", "months": [3, 4, 5], "role": "short rains"},
            {"name": "Kiremt", "months": [6, 7, 8, 9], "role": "main rains"},
            {"name": "Autumn rains", "months": [10, 11], "role": "second season in the far south"},
        ],
        "livelihood": "Enset (false banana), coffee and root crops; agro-pastoralism in South Omo",
        "sentinel": {"name": "Omo riverine forest", "note": "Gallery forest along the Omo depends on highland rain carried downstream to Lake Turkana."},
        "aliases": ["hawassa", "awasa", "sidama", "omo", "arba minch", "wolaita", "south", "southern", "south west", "gamo", "konso"],
    },
    "Somali": {
        "id": "somali",
        "label": "Somali",
        "points": 4,
        "group": "south",
        "rainy_months": [4, 5, 10, 11],
        "seasons": [
            {"name": "Gu", "months": [4, 5, 6], "role": "main rains"},
            {"name": "Deyr", "months": [10, 11, 12], "role": "short rains"},
        ],
        "livelihood": "Pastoralism: camels, goats and sheep that depend on both Gu and Deyr pasture",
        "sentinel": {"name": "Gerenuk", "note": "The long-necked gazelle can live without drinking, but its acacia browse still needs Gu and Deyr."},
        "aliases": ["jijiga", "gode", "ogaden", "dolo", "korahe", "liben"],
    },
    "Tigray": {
        "id": "tigray",
        "label": "Tigray",
        "points": 2,
        "group": "north",
        "rainy_months": [7, 8, 9],
        "seasons": [
            {"name": "Belg", "months": [3, 4], "role": "minor rains in the south"},
            {"name": "Kiremt", "months": [7, 8, 9], "role": "main rains, short and intense"},
        ],
        "livelihood": "Smallholder teff, sorghum and barley farming on steep, terraced land",
        "sentinel": {"name": "Lammergeier", "note": "The bearded vulture rides thermals over the escarpment; carcasses rise in drought years."},
        "aliases": ["mekelle", "mekele", "axum", "adigrat", "shire"],
    },
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class Region:
    id: str
    name: str
    label: str
    group: str
    rainy_months: list[int]
    seasons: list[dict]
    livelihood: str
    sentinel: dict
    aliases: list[str]
    geometry: object
    anchor: tuple[float, float]
    points: list[tuple[float, float]] = field(default_factory=list)

    def summary(self):
        return {
            "id": self.id,
            "name": self.label,
            "group": self.group,
            "rainyMonths": self.rainy_months,
            "seasons": self.seasons,
            "livelihood": self.livelihood,
            "sentinel": self.sentinel,
            "anchor": {"lat": round(self.anchor[1], 3), "lon": round(self.anchor[0], 3)},
            "samplePoints": [{"lat": round(p[1], 3), "lon": round(p[0], 3)} for p in self.points],
        }


def _sample_points(geometry, count: int, anchor: tuple[float, float]):
    if count <= 1:
        return [anchor]
    minx, miny, maxx, maxy = geometry.bounds
    step = 0.25
    candidates = []
    y = miny + step / 2
    while y < maxy:
        x = minx + step / 2
        while x < maxx:
            if geometry.contains(Point(x, y)):
                candidates.append((x, y))
            x += step
        y += step
    chosen = [anchor]
    while len(chosen) < count and candidates:
        best = max(candidates, key=lambda c: min((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2 for p in chosen))
        chosen.append(best)
        candidates.remove(best)
    return [(round(x * 4) / 4, round(y * 4) / 4) for x, y in chosen]


@lru_cache(maxsize=1)
def load_regions() -> list[Region]:
    data = json.loads(ADM1_FILE.read_text("utf-8"))
    regions = []
    for feature in data["features"]:
        name = feature["properties"]["shapeName"]
        profile = PROFILES.get(name)
        if not profile:
            continue
        geometry = shape(feature["geometry"])
        point = geometry.representative_point()
        anchor = (point.x, point.y)
        regions.append(
            Region(
                id=profile["id"],
                name=name,
                label=profile["label"],
                group=profile["group"],
                rainy_months=profile["rainy_months"],
                seasons=profile["seasons"],
                livelihood=profile["livelihood"],
                sentinel=profile["sentinel"],
                aliases=profile["aliases"],
                geometry=geometry,
                anchor=anchor,
                points=_sample_points(geometry, profile["points"], anchor),
            )
        )
    return sorted(regions, key=lambda r: r.label)


def region_by_id(region_id: str) -> Region | None:
    for region in load_regions():
        if region.id == region_id:
            return region
    return None


def find_region_in_text(text: str) -> Region | None:
    lowered = text.lower()
    best = None
    best_len = 0
    for region in load_regions():
        names = [region.label.lower(), region.name.lower(), region.id.replace("-", " ")] + region.aliases
        for alias in names:
            if re.search(rf"\b{re.escape(alias)}\b", lowered) and len(alias) > best_len:
                best = region
                best_len = len(alias)
    return best


def _round_coords(obj):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(obj[0], 3), round(obj[1], 3)]
        return [_round_coords(item) for item in obj]
    return obj


@lru_cache(maxsize=1)
def display_geojson():
    features = []
    for region in load_regions():
        simplified = region.geometry.simplify(0.02, preserve_topology=True)
        geom = mapping(simplified)
        features.append(
            {
                "type": "Feature",
                "properties": {"id": region.id, "name": region.label},
                "geometry": {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"])},
            }
        )
    return {"type": "FeatureCollection", "features": features}


@lru_cache(maxsize=1)
def country_outline():
    union = unary_union([r.geometry for r in load_regions()]).simplify(0.03, preserve_topology=True)
    geom = mapping(union)
    return {"type": "Feature", "properties": {"name": "Ethiopia"}, "geometry": {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"])}}


def assign_cells(cells: list[tuple[str, float, float]]):
    regions = load_regions()
    mapping_: dict[str, list[str]] = {r.id: [] for r in regions}
    for cell_id, lon, lat in cells:
        p = Point(lon, lat)
        for region in regions:
            if region.geometry.contains(p):
                mapping_[region.id].append(cell_id)
                break
    for region in regions:
        if not mapping_[region.id]:
            ax, ay = region.anchor
            nearest = sorted(cells, key=lambda c: (c[1] - ax) ** 2 + (c[2] - ay) ** 2)[:2]
            mapping_[region.id] = [c[0] for c in nearest]
    return mapping_
