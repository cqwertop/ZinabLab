from core import cache
from core.http import get_text

ONI_URL = "https://psl.noaa.gov/data/correlation/oni.data"
DMI_URL = "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data"


def _parse_psl(text: str) -> dict[str, float]:
    lines = text.strip().splitlines()
    out: dict[str, float] = {}
    if not lines:
        return out
    header = lines[0].split()
    first, last = int(header[0]), int(header[1])
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 13:
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue
        if year < first or year > last:
            continue
        for month, raw in enumerate(parts[1:], start=1):
            value = float(raw)
            if value <= -99:
                continue
            out[f"{year}-{month:02d}"] = value
    return out


async def oni_series():
    async def produce():
        return _parse_psl(await get_text(ONI_URL))

    return await cache.cached("drivers:oni", 24 * 3600, produce)


async def dmi_series():
    async def produce():
        return _parse_psl(await get_text(DMI_URL))

    return await cache.cached("drivers:dmi", 24 * 3600, produce)


def enso_phase(value: float | None):
    if value is None:
        return "unknown"
    if value >= 1.5:
        return "strong El Niño"
    if value >= 0.5:
        return "El Niño"
    if value <= -1.5:
        return "strong La Niña"
    if value <= -0.5:
        return "La Niña"
    return "neutral"


def iod_phase(value: float | None):
    if value is None:
        return "unknown"
    if value >= 0.4:
        return "positive IOD"
    if value <= -0.4:
        return "negative IOD"
    return "neutral"


def latest(series: dict[str, float], count: int = 1):
    keys = sorted(series)
    return [(k, series[k]) for k in keys[-count:]]


async def snapshot():
    oni = await oni_series()
    dmi = await dmi_series()
    oni_recent = latest(oni, 24)
    dmi_recent = latest(dmi, 24)
    oni_now = oni_recent[-1] if oni_recent else (None, None)
    dmi_now = dmi_recent[-1] if dmi_recent else (None, None)
    oni_trend = (oni_recent[-1][1] - oni_recent[-4][1]) if len(oni_recent) >= 4 else 0.0
    dmi_trend = (dmi_recent[-1][1] - dmi_recent[-4][1]) if len(dmi_recent) >= 4 else 0.0
    return {
        "enso": {
            "index": "ONI",
            "month": oni_now[0],
            "value": oni_now[1],
            "phase": enso_phase(oni_now[1]),
            "trend": round(oni_trend, 2),
            "history": [{"month": k, "value": v} for k, v in oni_recent],
            "source": "NOAA PSL / CPC Oceanic Niño Index",
            "url": ONI_URL,
        },
        "iod": {
            "index": "DMI",
            "month": dmi_now[0],
            "value": dmi_now[1],
            "phase": iod_phase(dmi_now[1]),
            "trend": round(dmi_trend, 2),
            "history": [{"month": k, "value": round(v, 3)} for k, v in dmi_recent],
            "source": "NOAA PSL Dipole Mode Index (HadISST)",
            "url": DMI_URL,
        },
    }
