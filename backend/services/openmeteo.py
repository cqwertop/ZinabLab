from core import cache
from core.http import get_json
from core.regions import load_regions

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def regional_outlook():
    regions = load_regions()

    async def produce():
        lats = ",".join(f"{r.anchor[1]:.3f}" for r in regions)
        lons = ",".join(f"{r.anchor[0]:.3f}" for r in regions)
        payload = await get_json(
            FORECAST_URL,
            {
                "latitude": lats,
                "longitude": lons,
                "daily": "precipitation_sum,precipitation_probability_max,temperature_2m_max,et0_fao_evapotranspiration",
                "forecast_days": 16,
                "timezone": "Africa/Addis_Ababa",
            },
        )
        items = payload if isinstance(payload, list) else [payload]
        result = {}
        for region, item in zip(regions, items):
            daily = item.get("daily", {})
            days = []
            for i, day in enumerate(daily.get("time", [])):
                days.append(
                    {
                        "date": day,
                        "rain": _num(daily.get("precipitation_sum"), i),
                        "chance": _num(daily.get("precipitation_probability_max"), i),
                        "tmax": _num(daily.get("temperature_2m_max"), i),
                        "et0": _num(daily.get("et0_fao_evapotranspiration"), i),
                    }
                )
            total = sum(d["rain"] or 0 for d in days)
            et0 = sum(d["et0"] or 0 for d in days)
            wet_days = sum(1 for d in days if (d["rain"] or 0) >= 1)
            result[region.id] = {
                "days": days,
                "totalRain": round(total, 1),
                "totalEt0": round(et0, 1),
                "waterBalance": round(total - et0, 1),
                "wetDays": wet_days,
            }
        return result

    return await cache.cached("openmeteo:outlook", 3 * 3600, produce)


def _num(values, index):
    if not values or index >= len(values) or values[index] is None:
        return None
    return round(float(values[index]), 2)
