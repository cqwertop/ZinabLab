import asyncio
from datetime import date, timedelta

from core import cache
from core.http import get_json, power_gate

BASE = "https://power.larc.nasa.gov/api/temporal"
DAILY_PARAMS = "PRECTOTCORR,T2M,GWETTOP"
FILL = -999.0


def _clean(series: dict) -> dict:
    return {k: (None if v is None or v <= FILL + 1 else float(v)) for k, v in series.items()}


async def daily(lat: float, lon: float, days: int = 150):
    end = date.today()
    start = end - timedelta(days=days)
    key = f"power:daily:{lat:.2f}:{lon:.2f}:{start:%Y%m%d}"

    async def produce():
        payload = await get_json(
            f"{BASE}/daily/point",
            {
                "parameters": DAILY_PARAMS,
                "community": "AG",
                "latitude": lat,
                "longitude": lon,
                "start": f"{start:%Y%m%d}",
                "end": f"{end:%Y%m%d}",
                "format": "JSON",
            },
            gate=power_gate(),
        )
        params = payload["properties"]["parameter"]
        return {name: _clean(values) for name, values in params.items()}

    return await cache.cached(key, 6 * 3600, produce)


async def climatology(lat: float, lon: float):
    key = f"power:clim:{lat:.2f}:{lon:.2f}"

    async def produce():
        payload = await get_json(
            f"{BASE}/climatology/point",
            {
                "parameters": DAILY_PARAMS,
                "community": "AG",
                "latitude": lat,
                "longitude": lon,
                "format": "JSON",
            },
            gate=power_gate(),
        )
        return payload["properties"]["parameter"]

    return await cache.cached(key, 60 * 24 * 3600, produce)


async def monthly_history(lat: float, lon: float, start_year: int = 1981):
    end_year = date.today().year - 1
    key = f"power:monthly:{lat:.2f}:{lon:.2f}:{start_year}:{end_year}"

    async def produce():
        payload = await get_json(
            f"{BASE}/monthly/point",
            {
                "parameters": "PRECTOTCORR",
                "community": "AG",
                "latitude": lat,
                "longitude": lon,
                "start": start_year,
                "end": end_year,
                "format": "JSON",
            },
            gate=power_gate(),
        )
        series = payload["properties"]["parameter"]["PRECTOTCORR"]
        return {k: v for k, v in _clean(series).items() if not k.endswith("13")}

    return await cache.cached(key, 90 * 24 * 3600, produce)


async def gather_points(fn, points: list[tuple[float, float]]):
    return await asyncio.gather(*(fn(lat, lon) for lon, lat in points))
