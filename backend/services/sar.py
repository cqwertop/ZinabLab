from datetime import date, timedelta

from core import cache
from core.http import get_json
from core.regions import Region

ASF_URL = "https://api.daac.asf.alaska.edu/services/search/param"


async def recent_passes(region: Region, limit: int = 6):
    lon, lat = region.anchor
    start = date.today() - timedelta(days=45)
    key = f"sar:{region.id}:{start:%Y%m%d}"

    async def produce():
        payload = await get_json(
            ASF_URL,
            {
                "platform": "Sentinel-1",
                "processingLevel": "GRD_HD",
                "intersectsWith": f"POINT({lon:.3f} {lat:.3f})",
                "start": f"{start:%Y-%m-%d}T00:00:00Z",
                "maxResults": limit * 2,
                "output": "geojson",
            },
        )
        passes = []
        for feature in payload.get("features", []):
            props = feature.get("properties", {})
            browse = props.get("browse") or []
            passes.append(
                {
                    "scene": props.get("sceneName") or props.get("fileID"),
                    "platform": props.get("platform"),
                    "time": props.get("startTime"),
                    "direction": (props.get("flightDirection") or "").title(),
                    "mode": props.get("beamModeType"),
                    "polarization": props.get("polarization"),
                    "orbit": props.get("pathNumber"),
                    "browse": browse[0] if browse else None,
                    "footprint": feature.get("geometry"),
                }
            )
        passes.sort(key=lambda p: p["time"] or "", reverse=True)
        return {
            "source": "Alaska Satellite Facility (ASF) DAAC search API",
            "searchUrl": f"https://search.asf.alaska.edu/#/?zoom=6&center={lon:.2f},{lat:.2f}&dataset=SENTINEL-1&productTypes=GRD_HD",
            "passes": passes[:limit],
        }

    return await cache.cached(key, 12 * 3600, produce)
