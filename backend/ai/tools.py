import asyncio
import json

from core.regions import load_regions, region_by_id
from ml.forecast import engine
from services import drivers, guidance, news, openmeteo, sar, status, why

REGION_IDS = [r.id for r in load_regions()]

TOOLS = [
    {
        "name": "dry_regions",
        "description": "Rank Ethiopian regions by how far their last 60 days of rain fall below normal, using live NASA POWER data. Also returns the national picture and which regions are simply in their normal dry season. Use this for questions like 'where is it not raining' or 'which areas are in drought'.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "region_report",
        "description": "Full live report for one region: rain over the last 30/60/90 days vs normal, dry spell, heat and soil anomalies, why rain is or is not falling (climate drivers, season, news), this month's nowcast, the 3-month Zinab forecast with tercile probabilities, the 16-day weather outlook, and practical advice.",
        "input_schema": {
            "type": "object",
            "properties": {"region": {"type": "string", "enum": REGION_IDS, "description": "Region id"}},
            "required": ["region"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "climate_drivers",
        "description": "Current ENSO (Oceanic Niño Index) and Indian Ocean Dipole values from NOAA, with phase and 3-month trend. These ocean patterns are the main large-scale reasons Ethiopian rainy seasons fail or flood.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "news_headlines",
        "description": "Recent news headlines about rain, drought and floods in Ethiopia or one region, with automatically tagged causes (La Niña, conflict, failed rains, livestock losses and so on).",
        "input_schema": {
            "type": "object",
            "properties": {"region": {"type": "string", "enum": REGION_IDS + ["national"], "description": "Region id, or national"}},
            "required": ["region"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "model_skill",
        "description": "How the Zinab rainfall forecast model works and how accurate it has been in cross-validation (correlation, skill scores versus climatology, hit rate, CHIRPS check).",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "sar_passes",
        "description": "Most recent Sentinel-1 synthetic aperture radar (SAR) satellite passes over a region from the Alaska Satellite Facility. Radar sees through clouds and is sensitive to soil moisture and standing water.",
        "input_schema": {
            "type": "object",
            "properties": {"region": {"type": "string", "enum": REGION_IDS}},
            "required": ["region"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


async def dry_regions():
    pulse = await status.national_pulse()
    return {
        "lastObserved": pulse["lastObserved"],
        "national": pulse["national"],
        "rankedDriest": [{"id": r["id"], "name": r["name"], "status": r["label"], "pct60": r["windows"]["d60"]["pct"], "drySpellDays": r["drySpellDays"]} for r in pulse["ranking"]],
        "seasonallyDry": [r["name"] for r in pulse["regions"] if r["status"] == "seasonal-dry"],
    }


async def region_report(region_id: str):
    region = region_by_id(region_id)
    if not region:
        return {"error": f"Unknown region {region_id}"}
    st = await status.region_status(region)
    drv, outlook16_all, headlines = await asyncio.gather(drivers.snapshot(), openmeteo.regional_outlook(), news.headlines(region.label))
    outlook16 = outlook16_all.get(region.id)
    await engine.ensure()
    outlook = engine.forecast(region, st.get("recentMonths", {}))
    explanation = why.explain(region, st, drv, outlook, headlines)
    return {
        "region": region.label,
        "livelihood": region.livelihood,
        "status": st["label"],
        "lastObserved": st.get("lastObserved"),
        "windows": st.get("windows"),
        "drySpellDays": st.get("drySpellDays"),
        "heat": st.get("heat"),
        "soil": st.get("soil"),
        "why": explanation,
        "nowcast": guidance.nowcast(st, outlook16),
        "forecast": [{k: m[k] for k in ("monthName", "drySeason", "expectedMm", "normalMm", "probabilities", "lean", "drivers")} for m in outlook["months"]],
        "next16days": {k: outlook16[k] for k in ("totalRain", "wetDays", "waterBalance")} if outlook16 else None,
        "advice": guidance.field_kit(region, st, outlook, outlook16),
        "topHeadlines": [{"title": a["title"], "date": a["date"], "source": a["source"]} for a in (headlines or {}).get("articles", [])[:4]],
    }


async def climate_drivers():
    snap = await drivers.snapshot()
    return {k: {kk: vv for kk, vv in v.items() if kk != "history"} for k, v in snap.items()}


async def news_headlines(region_id: str):
    region = region_by_id(region_id) if region_id != "national" else None
    data = await news.headlines(region.label if region else None)
    return {"provider": data["provider"], "signals": data["signals"], "articles": [{"title": a["title"], "date": a["date"], "source": a["source"], "causes": a["causes"]} for a in data["articles"][:8]]}


async def model_skill():
    await engine.ensure()
    return {k: v for k, v in engine.skill.items() if k != "coefficients"}


async def sar_passes(region_id: str):
    region = region_by_id(region_id)
    if not region:
        return {"error": f"Unknown region {region_id}"}
    data = await sar.recent_passes(region)
    return {"searchUrl": data["searchUrl"], "passes": [{k: p[k] for k in ("platform", "time", "direction", "mode", "polarization")} for p in data["passes"]]}


async def run_tool(name: str, args: dict):
    if name == "dry_regions":
        result = await dry_regions()
    elif name == "region_report":
        result = await region_report(args["region"])
    elif name == "climate_drivers":
        result = await climate_drivers()
    elif name == "news_headlines":
        result = await news_headlines(args.get("region", "national"))
    elif name == "model_skill":
        result = await model_skill()
    elif name == "sar_passes":
        result = await sar_passes(args["region"])
    else:
        raise ValueError(f"Unknown tool {name}")
    return json.dumps(result, default=str)
