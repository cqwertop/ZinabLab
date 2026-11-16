from core.regions import MONTHS, Region


def _current_season(region: Region, month: int):
    for season in region.seasons:
        if month in season["months"]:
            return season
    return None


def _weight(verdict: str) -> int:
    return {"primary": 3, "contributing": 2, "evidence": 1, "context": 0, "counter": -1}.get(verdict, 0)


def explain(region: Region, status: dict, drivers: dict, outlook: dict | None, news: dict | None):
    factors = []
    month = status.get("season", {}).get("month") or 1
    season = _current_season(region, month)
    tseason = "kiremt" if month in (6, 7, 8, 9) else "ond" if month in (10, 11, 12) else "mam" if month in (3, 4, 5) else "dry"
    w60 = (status.get("windows") or {}).get("d60") or {}
    pct = w60.get("pct")
    state = status.get("status")
    oni = drivers["enso"]["value"]
    dmi = drivers["iod"]["value"]
    enso_phase = drivers["enso"]["phase"]
    iod_phase = drivers["iod"]["phase"]

    if state == "seasonal-dry":
        nxt = status.get("season", {}).get("nextRainyMonth")
        factors.append({
            "key": "season",
            "title": "It is the normal dry season",
            "verdict": "primary",
            "detail": f"Only about {w60.get('normal', 0):.0f} mm usually falls here over 60 days at this time of year. Little rain now is expected, not a failure." + (f" The next rainy month is usually {MONTHS[nxt - 1]}." if nxt else ""),
            "source": "NASA POWER climatology",
        })
    elif season:
        factors.append({
            "key": "season",
            "title": f"{season['name']} season is under way",
            "verdict": "context",
            "detail": f"{MONTHS[month - 1]} falls in the {season['name']} ({season['role']}), so rain is expected and a shortfall matters for {region.livelihood.split(';')[0].lower()}.",
            "source": "Ethiopian seasonal calendar",
        })

    if oni is not None:
        if region.group == "north" and tseason == "kiremt" and oni >= 0.5:
            factors.append({"key": "enso", "title": f"El Niño is suppressing Kiremt rain (ONI {oni:+.1f})", "verdict": "primary", "detail": "El Niño weakens the monsoon flow that carries moisture to Ethiopia's northern and central highlands in June to September. The 2015 drought, one of the worst in 50 years, followed a strong El Niño.", "source": drivers["enso"]["source"]})
        elif region.group == "north" and tseason == "kiremt" and oni <= -0.5:
            factors.append({"key": "enso", "title": f"La Niña usually boosts Kiremt (ONI {oni:+.1f})", "verdict": "counter", "detail": "La Niña tends to strengthen highland summer rains, so it argues against a large-scale cause for any deficit here; look at local factors.", "source": drivers["enso"]["source"]})
        elif region.group == "south" and tseason == "ond" and oni <= -0.5:
            factors.append({"key": "enso", "title": f"La Niña is suppressing the autumn rains (ONI {oni:+.1f})", "verdict": "primary", "detail": "La Niña cools the western Indian Ocean surface and weakens the October to December (Deyr / Hagaya) rains in southern and south-eastern Ethiopia. Five failed seasons in a row in 2020 to 2023 came with back-to-back La Niña.", "source": drivers["enso"]["source"]})
        elif region.group == "south" and tseason == "mam" and oni <= -0.5:
            factors.append({"key": "enso", "title": f"La Niña is weighing on the spring rains (ONI {oni:+.1f})", "verdict": "contributing", "detail": "La Niña winters are often followed by poor March to May (Gu / Belg) rains in the south and south-east.", "source": drivers["enso"]["source"]})
        elif region.group == "south" and tseason == "ond" and oni >= 0.5:
            factors.append({"key": "enso", "title": f"El Niño usually brings a wet autumn (ONI {oni:+.1f})", "verdict": "counter", "detail": "El Niño tends to enhance October to December rains in the south-east (the 2023 Deyr floods). A deficit now would be unusual and points to other causes.", "source": drivers["enso"]["source"]})
        else:
            factors.append({"key": "enso", "title": f"ENSO is {enso_phase} (ONI {oni:+.1f})", "verdict": "context", "detail": "ENSO has a weak direct link to rainfall in this region at this time of year.", "source": drivers["enso"]["source"]})

    if dmi is not None and region.group == "south" and tseason == "ond":
        if dmi <= -0.4:
            factors.append({"key": "iod", "title": f"Negative Indian Ocean Dipole (DMI {dmi:+.2f})", "verdict": "contributing", "detail": "A cooler western Indian Ocean means less moisture for East Africa's short rains.", "source": drivers["iod"]["source"]})
        elif dmi >= 0.4:
            factors.append({"key": "iod", "title": f"Positive Indian Ocean Dipole (DMI {dmi:+.2f})", "verdict": "counter", "detail": "A warm western Indian Ocean normally boosts the short rains (2019 and 2023 floods).", "source": drivers["iod"]["source"]})
        else:
            factors.append({"key": "iod", "title": f"Indian Ocean Dipole is {iod_phase}", "verdict": "context", "detail": "The IOD is not pushing strongly either way right now.", "source": drivers["iod"]["source"]})

    heat = status.get("heat") or {}
    if heat.get("anomaly") is not None and heat["anomaly"] >= 1.0:
        factors.append({"key": "heat", "title": f"Days are {heat['anomaly']:.1f} °C hotter than normal", "verdict": "contributing", "detail": "Extra heat raises evaporation, so the rain that does fall dries out faster and crops and pasture stress sooner.", "source": "NASA POWER T2M"})

    soil = status.get("soil") or {}
    if soil.get("anomaly") is not None and soil["anomaly"] <= -0.05:
        factors.append({"key": "soil", "title": "Topsoil is drier than normal", "verdict": "evidence", "detail": f"Surface soil wetness is {soil['wetness']:.2f} against a normal of {soil['normal']:.2f} (0 = bone dry, 1 = saturated).", "source": "NASA POWER GWETTOP (MERRA-2)"})

    spell = status.get("drySpellDays") or 0
    if spell >= 15 and state != "seasonal-dry":
        factors.append({"key": "dryspell", "title": f"{spell} days without meaningful rain", "verdict": "evidence", "detail": "A dry spell of more than two weeks in a rainy season can wilt young crops and stop pasture regrowth.", "source": "NASA POWER daily precipitation"})

    if news and news.get("signals"):
        top = [s for s in news["signals"] if s["cause"] not in ("Drought",)][:3]
        if top:
            names = ", ".join(f"{s['cause'].lower()} ({s['mentions']})" for s in top)
            verdict = "evidence" if state in ("severe-deficit", "deficit") else "context"
            factors.append({"key": "news", "title": "What the news is reporting", "verdict": verdict, "detail": f"Recent headlines mention {names}. Conflict and food insecurity do not stop rain, but they make a dry season far more damaging.", "source": news.get("provider")})

    if outlook and outlook.get("months"):
        nxt = next((m for m in outlook["months"] if not m["drySeason"]), None)
        if nxt:
            p = nxt["probabilities"]
            if nxt["lean"] == "dry":
                factors.append({"key": "outlook", "title": f"Outlook: {nxt['monthName']} leans dry ({p['below'] * 100:.0f}% chance below normal)", "verdict": "evidence", "detail": "The Zinab model expects the pattern to continue. Its strongest driver is " + (nxt["drivers"][0]["feature"].lower() if nxt["drivers"] else "persistence") + ".", "source": "Zinab ridge forecast"})
            elif nxt["lean"] == "wet":
                factors.append({"key": "outlook", "title": f"Outlook: {nxt['monthName']} leans wet ({p['above'] * 100:.0f}% chance above normal)", "verdict": "counter", "detail": "The model expects some recovery.", "source": "Zinab ridge forecast"})

    factors.sort(key=lambda f: -_weight(f["verdict"]))

    if state == "seasonal-dry":
        headline = f"{region.label} is in its normal dry season. Little rain is expected right now, so this is not a drought signal."
        confidence = "high"
    elif state in ("severe-deficit", "deficit"):
        causes = [f for f in factors if f["verdict"] in ("primary", "contributing")]
        lead = causes[0]["title"].split(" (")[0].lower() if causes else "local weather variability rather than a large-scale climate driver"
        headline = f"{region.label} has had about {pct:.0f}% of its normal rain over the last 60 days. The most likely cause is {lead}."
        confidence = "high" if any(f["verdict"] == "primary" for f in factors) and len(causes) >= 2 else "medium" if causes else "low"
    elif state == "wet":
        headline = f"{region.label} is wetter than normal ({pct:.0f}% of normal over 60 days). Watch for flooding rather than drought."
        confidence = "medium"
    else:
        headline = f"{region.label} is close to normal ({pct:.0f}% of normal over 60 days)." if pct is not None else f"Not enough recent data for {region.label}."
        confidence = "medium"

    return {"headline": headline, "confidence": confidence, "factors": factors}
