import asyncio
from datetime import date, datetime

from core.regions import MONTHS, Region, load_regions, region_by_id
from services import power
from services.chirps import region_cell_count

MONTH_KEYS = [m.upper() for m in MONTHS]


def _mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _merge_daily(daily_list):
    merged: dict[str, dict[str, float | None]] = {}
    for param in ("PRECTOTCORR", "T2M", "GWETTOP"):
        keys = set()
        for d in daily_list:
            keys.update(d.get(param, {}).keys())
        for k in keys:
            merged.setdefault(k, {})[param] = _mean([d.get(param, {}).get(k) for d in daily_list])
    return dict(sorted(merged.items()))


def _merge_clim(clim_list):
    out = {}
    for param in ("PRECTOTCORR", "T2M", "GWETTOP"):
        out[param] = {m: _mean([c.get(param, {}).get(m) for c in clim_list]) for m in MONTH_KEYS}
    return out


def _clim_for(clim, param, day_key):
    return clim[param][MONTH_KEYS[int(day_key[4:6]) - 1]]


def classify(pct60, normal60):
    if normal60 is not None and normal60 < 20:
        return "seasonal-dry"
    if pct60 is None:
        return "unknown"
    if pct60 < 50:
        return "severe-deficit"
    if pct60 < 75:
        return "deficit"
    if pct60 <= 130:
        return "near-normal"
    return "wet"


LABELS = {
    "seasonal-dry": "Dry season, as expected",
    "severe-deficit": "Severe rain deficit",
    "deficit": "Below-normal rain",
    "near-normal": "Near-normal rain",
    "wet": "Wetter than normal",
    "unknown": "No recent data",
}


async def region_status(region: Region):
    daily_list, clim_list = await asyncio.gather(
        power.gather_points(power.daily, region.points),
        power.gather_points(power.climatology, region.points),
    )
    daily = _merge_daily(daily_list)
    clim = _merge_clim(clim_list)
    keys = [k for k, v in daily.items() if v.get("PRECTOTCORR") is not None]
    if not keys:
        return {"id": region.id, "name": region.label, "status": "unknown", "label": LABELS["unknown"]}
    last = keys[-1]
    keys = [k for k in daily if k <= last]

    def window(n):
        span = keys[-n:]
        rain = sum(daily[k].get("PRECTOTCORR") or 0 for k in span)
        normal = sum(_clim_for(clim, "PRECTOTCORR", k) or 0 for k in span)
        pct = rain / normal * 100 if normal >= 5 else None
        return {"days": n, "rain": round(rain, 1), "normal": round(normal, 1), "pct": None if pct is None else round(pct, 0)}

    w30, w60, w90 = window(30), window(60), window(90)

    dry_spell = 0
    for k in reversed(keys):
        if (daily[k].get("PRECTOTCORR") or 0) < 1.0:
            dry_spell += 1
        else:
            break

    longest = run = 0
    for k in keys[-90:]:
        if (daily[k].get("PRECTOTCORR") or 0) < 1.0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    tmax_obs = _mean([daily[k].get("T2M") for k in keys[-30:]])
    tmax_norm = _mean([_clim_for(clim, "T2M", k) for k in keys[-30:]])
    soil_obs = _mean([daily[k].get("GWETTOP") for k in keys[-10:]])
    soil_norm = _mean([_clim_for(clim, "GWETTOP", k) for k in keys[-10:]])

    status = classify(w60["pct"], w60["normal"])
    month_now = int(last[4:6])
    in_season = month_now in region.rainy_months
    upcoming = next(((m - 1) % 12 + 1 for m in range(month_now + 1, month_now + 13) if ((m - 1) % 12 + 1) in region.rainy_months), None)

    cumulative = []
    c_rain = c_norm = 0.0
    for k in keys[-90:]:
        c_rain += daily[k].get("PRECTOTCORR") or 0
        c_norm += _clim_for(clim, "PRECTOTCORR", k) or 0
        cumulative.append({"date": f"{k[:4]}-{k[4:6]}-{k[6:]}", "rain": round(daily[k].get("PRECTOTCORR") or 0, 1), "normalDaily": round(_clim_for(clim, "PRECTOTCORR", k) or 0, 2), "cumRain": round(c_rain, 1), "cumNormal": round(c_norm, 1)})

    monthly_recent: dict[str, float] = {}
    for k in keys:
        mk = f"{k[:4]}-{k[4:6]}"
        monthly_recent[mk] = monthly_recent.get(mk, 0.0) + (daily[k].get("PRECTOTCORR") or 0)
    first_month = keys[0][:6]
    complete = {m: round(v, 1) for m, v in monthly_recent.items() if m.replace("-", "") != first_month and m.replace("-", "") != last[:6]}

    return {
        "id": region.id,
        "name": region.label,
        "status": status,
        "label": LABELS[status],
        "lastObserved": f"{last[:4]}-{last[4:6]}-{last[6:]}",
        "windows": {"d30": w30, "d60": w60, "d90": w90},
        "drySpellDays": dry_spell,
        "longestDrySpell90": longest,
        "heat": {"t30": None if tmax_obs is None else round(tmax_obs, 1), "normal": None if tmax_norm is None else round(tmax_norm, 1), "anomaly": None if tmax_obs is None or tmax_norm is None else round(tmax_obs - tmax_norm, 1)},
        "soil": {"wetness": None if soil_obs is None else round(soil_obs, 2), "normal": None if soil_norm is None else round(soil_norm, 2), "anomaly": None if soil_obs is None or soil_norm is None else round(soil_obs - soil_norm, 2)},
        "season": {"month": month_now, "inSeason": in_season, "nextRainyMonth": upcoming, "seasons": region.seasons},
        "climatology": [{"month": i + 1, "mmPerDay": round(clim["PRECTOTCORR"][m] or 0, 2), "mm": round((clim["PRECTOTCORR"][m] or 0) * [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][i], 0)} for i, m in enumerate(MONTH_KEYS)],
        "series": cumulative,
        "recentMonths": complete,
        "source": "NASA POWER daily (PRECTOTCORR, T2M, GWETTOP) vs NASA POWER long-term climatology",
    }


async def all_status():
    regions = load_regions()
    results = await asyncio.gather(*(region_status(r) for r in regions), return_exceptions=True)
    out = []
    for region, result in zip(regions, results):
        if isinstance(result, Exception):
            out.append({"id": region.id, "name": region.label, "status": "unknown", "label": LABELS["unknown"], "error": str(result)})
        else:
            out.append(result)
    return out


def lite(entry):
    return {k: entry.get(k) for k in ("id", "name", "status", "label", "lastObserved", "windows", "drySpellDays", "heat", "soil", "season")}


async def national_pulse():
    statuses = await all_status()
    weights = region_cell_count()
    valid = [s for s in statuses if s.get("windows")]
    total_w = sum(weights.get(s["id"], 1) for s in valid) or 1
    rain60 = sum(s["windows"]["d60"]["rain"] * weights.get(s["id"], 1) for s in valid) / total_w
    norm60 = sum(s["windows"]["d60"]["normal"] * weights.get(s["id"], 1) for s in valid) / total_w
    rain30 = sum(s["windows"]["d30"]["rain"] * weights.get(s["id"], 1) for s in valid) / total_w
    norm30 = sum(s["windows"]["d30"]["normal"] * weights.get(s["id"], 1) for s in valid) / total_w
    in_deficit = [s for s in valid if s["status"] in ("severe-deficit", "deficit")]
    deficit_share = sum(weights.get(s["id"], 1) for s in in_deficit) / total_w * 100
    ranking = sorted(
        (s for s in valid if s["status"] != "seasonal-dry" and s["windows"]["d60"]["pct"] is not None),
        key=lambda s: s["windows"]["d60"]["pct"],
    )
    return {
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "today": date.today().isoformat(),
        "lastObserved": max((s.get("lastObserved") or "" for s in valid), default=None),
        "national": {
            "rain60": round(rain60, 1),
            "normal60": round(norm60, 1),
            "pct60": round(rain60 / norm60 * 100, 0) if norm60 >= 5 else None,
            "rain30": round(rain30, 1),
            "normal30": round(norm30, 1),
            "pct30": round(rain30 / norm30 * 100, 0) if norm30 >= 5 else None,
            "deficitAreaPct": round(deficit_share, 0),
            "regionsInDeficit": len(in_deficit),
            "regionsInSeason": sum(1 for s in valid if s["season"]["inSeason"]),
        },
        "ranking": [lite(s) for s in ranking],
        "regions": [lite(s) for s in statuses],
    }


async def status_for(region_id: str):
    region = region_by_id(region_id)
    if not region:
        return None
    return await region_status(region)
