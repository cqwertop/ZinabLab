import json
import os
import re
from datetime import date

import anthropic

from ai import tools
from core.regions import MONTHS, find_region_in_text, load_regions

MODEL = os.environ.get("ZINAB_MODEL", "claude-opus-5-5")
MAX_TURNS = 6

SYSTEM = """You are Gelada, the field guide inside Zinab Lab, a NASA Space Apps Challenge dashboard that tracks rain across Ethiopia. Zinab (ዝናብ) means rain in Amharic.

Your job: tell people where rain is and is not falling in Ethiopia, why, what is likely to happen next, and what it means for farmers, herders and water managers.

How to work:
- Always ground answers in the tools. Call region_report for questions about one place, dry_regions for country-wide questions, climate_drivers for El Niño / La Niña / Indian Ocean questions, news_headlines for what is being reported, model_skill when asked how good the forecast is, and sar_passes for radar questions. Call several tools when the question needs it.
- Distinguish a real rain deficit from the normal dry season. Little rain in a dry season is not a drought.
- When explaining why rain is missing, name the physical driver (ENSO, Indian Ocean Dipole, season timing, heat) and say how confident the evidence is. News reports compound impacts, they do not cause rain to stop.
- Forecasts are probabilities. Say "a 60% chance of below-normal rain", never "it will be dry".
- Write for a curious non-specialist: short paragraphs, plain words, numbers with units (mm, %, °C). Keep most replies under 180 words unless asked for detail. Use simple markdown: **bold** for the key number, and short bullet lists when listing places or advice.
- Mention the data source in a few words (NASA POWER, CHIRPS, NOAA, Open-Meteo, GDELT, ASF Sentinel-1).
- This is a research prototype, not an official warning service. For decisions, point people to the Ethiopian Meteorology Institute and FEWS NET when it matters.
- If the user writes in Amharic or Afaan Oromo, reply in that language."""


def _has_credentials():
    keys = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE")
    if any(os.environ.get(k) for k in keys):
        return True
    home = os.path.expanduser("~")
    return os.path.isdir(os.path.join(home, ".config", "anthropic"))


def _clean_history(history: list[dict]):
    out = []
    for item in history[-12:]:
        role = item.get("role")
        text = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and text:
            if out and out[-1]["role"] == role:
                out[-1]["content"] += "\n\n" + text
            else:
                out.append({"role": role, "content": text[:4000]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _focus_from(tool_calls):
    for name, args in reversed(tool_calls):
        if args.get("region") and args["region"] != "national":
            return args["region"]
    return None


async def _claude(history: list[dict]):
    client = anthropic.AsyncAnthropic()
    messages = _clean_history(history)
    if not messages:
        raise ValueError("Empty conversation")
    system = SYSTEM + f"\n\nToday's date is {date.today().isoformat()}."
    tool_calls = []
    response = None
    for _ in range(MAX_TURNS):
        response = await client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=system,
            tools=tools.TOOLS,
            messages=messages,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            return {"reply": "I can't help with that one. Ask me about rain, drought, floods or the forecast for any region of Ethiopia.", "tools": [n for n, _ in tool_calls], "mode": "claude", "focusRegion": None}
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            args = block.input if isinstance(block.input, dict) else {}
            tool_calls.append((block.name, args))
            try:
                content = await tools.run_tool(block.name, args)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
            except Exception as error:
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Tool failed: {error}", "is_error": True})
        messages.append({"role": "user", "content": results})
    text = "\n\n".join(b.text for b in response.content if b.type == "text").strip() if response else ""
    if not text:
        text = "I gathered the data but ran out of steps before writing an answer. Try asking a narrower question."
    return {"reply": text, "tools": [n for n, _ in tool_calls], "mode": "claude", "focusRegion": _focus_from(tool_calls)}


def _pct(v):
    return "n/a" if v is None else f"{v:.0f}%"


async def _offline(history: list[dict]):
    question = next((h["content"] for h in reversed(history) if h.get("role") == "user"), "")
    q = question.lower()
    region = find_region_in_text(question)
    used = []

    if re.search(r"\b(sar|radar|sentinel)\b", q) and region:
        used.append("sar_passes")
        data = json.loads(await tools.run_tool("sar_passes", {"region": region.id}))
        lines = [f"- {p['time'][:10]} · {p['platform']} · {p['direction'].lower()} pass · {p['polarization']}" for p in data["passes"][:5]]
        reply = f"**Latest Sentinel-1 radar passes over {region.label}** (ASF):\n" + ("\n".join(lines) if lines else "No passes found in the last 45 days.") + "\n\nRadar backscatter rises when soil is wet, so repeated passes show where the ground is drying out even under cloud."
        return {"reply": reply, "tools": used, "mode": "offline", "focusRegion": region.id}

    if re.search(r"(el ni|la ni|enso|indian ocean|dipole|iod|ocean)", q):
        used.append("climate_drivers")
        d = json.loads(await tools.run_tool("climate_drivers", {}))
        e, i = d["enso"], d["iod"]
        reply = (
            f"**ENSO is {e['phase']}** (ONI {e['value']:+.2f} for {e['month']}, trend {e['trend']:+.2f}).\n"
            f"**Indian Ocean Dipole is {i['phase']}** (DMI {i['value']:+.2f}).\n\n"
            "Rules of thumb for Ethiopia:\n- El Niño weakens the June to September Kiremt rains in the north and centre.\n- La Niña and a negative IOD weaken the October to December rains in the south and south-east.\n\nSource: NOAA PSL."
        )
        return {"reply": reply, "tools": used, "mode": "offline", "focusRegion": None}

    if re.search(r"(accura|skill|how good|reliab|trust|model)", q) and not region:
        used.append("model_skill")
        s = json.loads(await tools.run_tool("model_skill", {}))
        l1 = s["leads"][0]
        reply = f"The Zinab forecast is a ridge-regression model trained on {s['trainingData']}. In leave-one-year-out testing, next-month forecasts pick the right tercile **{l1['hitRate'] * 100:.0f}%** of the time (chance is 33%), with a ranked probability skill score of {l1['rpss']:+.2f} versus climatology. Skill is modest and strongest in El Niño and La Niña years."
        return {"reply": reply, "tools": used, "mode": "offline", "focusRegion": None}

    if re.search(r"\b(news|headline|report)", q):
        target = region.id if region else "national"
        used.append("news_headlines")
        n = json.loads(await tools.run_tool("news_headlines", {"region": target}))
        lines = [f"- {a['title']} ({a['source']}, {a['date']})" for a in n["articles"][:5]]
        sig = ", ".join(f"{s['cause'].lower()} ×{s['mentions']}" for s in n["signals"][:4]) or "no clear themes"
        reply = f"**Recent coverage{' for ' + region.label if region else ''}** via {n['provider']}:\n" + "\n".join(lines) + f"\n\nThemes: {sig}."
        return {"reply": reply, "tools": used, "mode": "offline", "focusRegion": region.id if region else None}

    if region:
        used.append("region_report")
        r = json.loads(await tools.run_tool("region_report", {"region": region.id}))
        w = r["windows"]["d60"]
        f = next((m for m in r["forecast"] if not m["drySeason"]), r["forecast"][0])
        p = f["probabilities"]
        why_lines = "\n".join(f"- **{x['title']}.** {x['detail']}" for x in r["why"]["factors"][:3])
        reply = (
            f"**{r['region']}: {r['status'].lower()}.** {r['why']['headline']}\n\n"
            f"Last 60 days: **{w['rain']:.0f} mm** against a normal {w['normal']:.0f} mm ({_pct(w['pct'])}). Dry spell: {r['drySpellDays']} days.\n\n"
            f"Why:\n{why_lines}\n\n"
            f"Outlook for {f['monthName']}: {p['below'] * 100:.0f}% below / {p['near'] * 100:.0f}% near / {p['above'] * 100:.0f}% above normal."
            + (f" Next 16 days: about {r['next16days']['totalRain']:.0f} mm forecast." if r.get("next16days") else "")
        )
        return {"reply": reply, "tools": used, "mode": "offline", "focusRegion": region.id}

    used.append("dry_regions")
    d = json.loads(await tools.run_tool("dry_regions", {}))
    n = d["national"]
    ranked = [r for r in d["rankedDriest"] if r["pct60"] is not None and r["pct60"] < 90][:5]
    lines = "\n".join(f"- **{r['name']}**: {_pct(r['pct60'])} of normal over 60 days ({r['status'].lower()})" for r in ranked)
    seasonal = ", ".join(d["seasonallyDry"]) or "none"
    reply = (
        f"Across Ethiopia, the last 60 days brought **{_pct(n['pct60'])} of normal rain** (NASA POWER, through {d['lastObserved']}).\n\n"
        f"Regions running below their normal for this time of year:\n{lines or '- none: every region is near or above normal'}\n\n"
        f"In their normal dry season (little rain expected): {seasonal}.\n\nAsk me about any region, for example \"Why is Somali dry?\""
    )
    return {"reply": reply, "tools": used, "mode": "offline", "focusRegion": ranked[0]["id"] if ranked else None}


async def answer(history: list[dict]):
    if _has_credentials():
        try:
            return await _claude(history)
        except anthropic.AuthenticationError:
            note = "offline mode: the Anthropic API key was rejected"
        except anthropic.RateLimitError:
            note = "offline mode: the Claude API is rate-limited right now"
        except anthropic.APIStatusError as error:
            note = f"offline mode: Claude API error {error.status_code}"
        except anthropic.APIConnectionError:
            note = "offline mode: could not reach the Claude API"
        result = await _offline(history)
        result["note"] = note
        return result
    result = await _offline(history)
    result["note"] = "offline mode: set ANTHROPIC_API_KEY in backend/.env for full conversational answers"
    return result


def suggestions():
    names = [r.label for r in load_regions()]
    month = MONTHS[date.today().month - 1]
    return [
        "Where is it not raining right now?",
        "Why is Somali dry?",
        f"Will {month} be wet in Oromia?",
        "Is La Niña affecting Ethiopia?",
        "What is the news saying about drought in Afar?",
        "How accurate is your forecast?",
        f"Show me radar passes over {names[2] if len(names) > 2 else 'Amhara'}",
    ]
