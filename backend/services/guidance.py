import calendar
from datetime import date

from core.regions import MONTHS, Region


def nowcast(status: dict, outlook16: dict | None):
    last = status.get("lastObserved")
    if not last or not status.get("series"):
        return None
    y, m, d = int(last[:4]), int(last[5:7]), int(last[8:10])
    month_key = f"{y}-{m:02d}"
    observed = sum(p["rain"] for p in status["series"] if p["date"].startswith(month_key))
    days_total = calendar.monthrange(y, m)[1]
    clim_daily = status["climatology"][m - 1]["mmPerDay"]
    normal = clim_daily * days_total
    forecast_part = 0.0
    forecast_days = 0
    if outlook16:
        for day in outlook16["days"]:
            if day["date"].startswith(month_key) and day["date"] > last and day["rain"] is not None:
                forecast_part += day["rain"]
                forecast_days += 1
    remaining = max(0, days_total - d - forecast_days)
    climo_part = remaining * clim_daily
    projected = observed + forecast_part + climo_part
    return {
        "month": month_key,
        "monthName": MONTHS[m - 1],
        "observedMm": round(observed, 1),
        "observedThrough": last,
        "forecastMm": round(forecast_part, 1),
        "forecastDays": forecast_days,
        "climatologyMm": round(climo_part, 1),
        "projectedMm": round(projected, 1),
        "normalMm": round(normal, 1),
        "pctOfNormal": round(projected / normal * 100, 0) if normal >= 5 else None,
    }


def field_kit(region: Region, status: dict, outlook: dict | None, outlook16: dict | None):
    state = status.get("status")
    month = status.get("season", {}).get("month") or date.today().month
    next_rain = status.get("season", {}).get("nextRainyMonth")
    water = (outlook16 or {}).get("waterBalance")
    rain16 = (outlook16 or {}).get("totalRain")
    upcoming = next((mo for mo in (outlook or {}).get("months", []) if not mo["drySeason"]), None)
    dry_lean = upcoming and upcoming["lean"] == "dry"
    wet_lean = upcoming and upcoming["lean"] == "wet"
    pastoral = region.id in ("afar", "somali") or "pastoral" in region.livelihood.lower()
    tips = []

    if state == "seasonal-dry":
        tips.append({"audience": "Farmers", "icon": "sprout", "title": "Prepare for the next season", "text": f"Rain is not expected now. Use the time to repair terraces and water-harvesting pits before {MONTHS[next_rain - 1] if next_rain else 'the next rains'}." + (" The outlook for that season leans dry, so line up short-cycle seed." if dry_lean else "")})
    elif state in ("severe-deficit", "deficit"):
        tips.append({"audience": "Farmers", "icon": "sprout", "title": "Protect what is in the ground", "text": "Mulch and weed to save soil moisture. If you have not planted yet, consider short-cycle or drought-tolerant varieties (early sorghum, teff, chickpea) and plant only once the topsoil is wet to about a hand's depth."})
    elif state == "wet":
        tips.append({"audience": "Farmers", "icon": "sprout", "title": "Manage the extra water", "text": "Clear drainage channels and watch low fields for waterlogging. Wet spells raise fungal disease risk in wheat and teff."})
    else:
        tips.append({"audience": "Farmers", "icon": "sprout", "title": "Conditions are close to normal", "text": "Follow the usual calendar and keep an eye on the 16-day outlook for dry spells longer than ten days."})

    if pastoral or region.group == "south":
        if state in ("severe-deficit", "deficit") or dry_lean:
            tips.append({"audience": "Herders", "icon": "hoof", "title": "Move early, sell early", "text": "Pasture and water points will thin out. Planning moves and selling weaker animals early, while prices are still good, protects the core herd."})
        else:
            tips.append({"audience": "Herders", "icon": "hoof", "title": "Pasture is holding", "text": "Rain is close to normal. Rotate grazing so wet-season pasture lasts into the dry months."})

    if water is not None:
        if water < -40:
            tips.append({"audience": "Water managers", "icon": "drop", "title": f"Losing more water than it gains ({water:+.0f} mm over 16 days)", "text": f"The forecast brings about {rain16:.0f} mm of rain, but evaporation is higher. Expect falling ponds and reservoirs; prioritise drinking water and storage."})
        elif water > 20:
            tips.append({"audience": "Water managers", "icon": "drop", "title": f"Water surplus ahead ({water:+.0f} mm over 16 days)", "text": "Good time to fill storage tanks and check spillways and river crossings for flood risk."})
        else:
            tips.append({"audience": "Water managers", "icon": "drop", "title": "Roughly balanced water budget", "text": f"About {rain16:.0f} mm of rain is forecast over the next 16 days, close to what evaporation will take."})

    if wet_lean:
        tips.append({"audience": "Everyone", "icon": "bolt", "title": "Flood watch", "text": f"The outlook leans wet for {upcoming['monthName']}. Low-lying riverbanks and dry riverbeds can flood quickly."})
    elif dry_lean:
        tips.append({"audience": "Everyone", "icon": "sun", "title": "Drought watch", "text": f"There is a {upcoming['probabilities']['below'] * 100:.0f}% chance that {upcoming['monthName']} will be drier than normal. Follow local early-warning bulletins from the Ethiopian Meteorology Institute and FEWS NET."})

    return tips
