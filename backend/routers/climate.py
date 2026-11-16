import asyncio

from fastapi import APIRouter, HTTPException

from core.regions import country_outline, display_geojson, load_regions, region_by_id
from ml.forecast import engine
from services import chirps, drivers, guidance, news, openmeteo, sar, status, why

router = APIRouter()


async def _safe(coro, default=None):
    try:
        return await coro
    except Exception:
        return default


@router.get("/regions")
async def regions():
    return {"regions": [r.summary() for r in load_regions()], "geojson": display_geojson(), "outline": country_outline()}


@router.get("/pulse")
async def pulse():
    pulse_data, drv, outlook16 = await asyncio.gather(status.national_pulse(), _safe(drivers.snapshot()), _safe(openmeteo.regional_outlook(), {}))
    for entry in pulse_data["regions"]:
        o = (outlook16 or {}).get(entry["id"])
        entry["next16"] = {k: o[k] for k in ("totalRain", "wetDays", "waterBalance")} if o else None
    pulse_data["drivers"] = drv
    return pulse_data


@router.get("/regions/{region_id}")
async def region_detail(region_id: str):
    region = region_by_id(region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Unknown region")
    st = await status.region_status(region)
    drv, outlook16_all, headlines = await asyncio.gather(drivers.snapshot(), _safe(openmeteo.regional_outlook(), {}), _safe(news.headlines(region.label)))
    outlook16 = (outlook16_all or {}).get(region.id)
    outlook = None
    try:
        await engine.ensure()
        outlook = engine.forecast(region, st.get("recentMonths", {}))
    except Exception as error:
        outlook = {"error": str(error), "months": []}
    return {
        "region": region.summary(),
        "status": st,
        "history": chirps.region_history(region.id),
        "outlook": outlook,
        "next16": outlook16,
        "nowcast": guidance.nowcast(st, outlook16),
        "why": why.explain(region, st, drv, outlook, headlines),
        "fieldKit": guidance.field_kit(region, st, outlook, outlook16),
        "news": headlines,
    }


@router.get("/regions/{region_id}/sar")
async def region_sar(region_id: str):
    region = region_by_id(region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Unknown region")
    try:
        return await sar.recent_passes(region)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"ASF search unavailable: {error}")


@router.get("/history/grid")
def history_grid():
    return chirps.grid_payload()


@router.get("/history/national")
def history_national():
    return chirps.national_history()


@router.get("/drivers")
async def climate_drivers():
    return await drivers.snapshot()


@router.get("/news")
async def national_news():
    return await news.headlines(None)


@router.get("/model")
async def model_card():
    await engine.ensure()
    return engine.skill


@router.get("/forecast/{region_id}")
async def region_forecast(region_id: str):
    region = region_by_id(region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Unknown region")
    st = await status.region_status(region)
    await engine.ensure()
    return engine.forecast(region, st.get("recentMonths", {}))
