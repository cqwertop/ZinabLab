import asyncio
import html
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from core import cache
from core.http import client

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_RSS = "https://news.google.com/rss/search"

CAUSES = {
    "El Niño": ["el nino", "el niño"],
    "La Niña": ["la nina", "la niña"],
    "Failed or late rains": ["failed rain", "rains failed", "rain failure", "late rain", "delayed rain", "below-average rain", "below average rain", "poor rain", "erratic rain", "dry spell", "no rain", "consecutive failed", "rainy season fail"],
    "Drought": ["drought", "dry conditions", "water shortage"],
    "Heat": ["heatwave", "heat wave", "high temperature", "record heat", "extreme heat"],
    "Conflict": ["conflict", "fighting", "war ", "clashes", "insecurity", "armed"],
    "Pests": ["locust", "armyworm", "pest"],
    "Flooding": ["flood", "flash flood", "overflow"],
    "Food insecurity": ["hunger", "famine", "food insecurity", "malnutrition", "food aid", "starv"],
    "Livestock losses": ["livestock", "cattle", "camel", "goats", "pasture"],
    "Displacement": ["displaced", "displacement", "idp", "migrat"],
}

_gdelt_lock = asyncio.Lock()
_gdelt_last = 0.0


def tag_causes(text: str) -> list[str]:
    lowered = f" {text.lower()} "
    return [cause for cause, words in CAUSES.items() if any(w in lowered for w in words)]


async def _gdelt(query: str):
    global _gdelt_last
    async with _gdelt_lock:
        wait = 5.6 - (time.time() - _gdelt_last)
        if wait > 0:
            await asyncio.sleep(wait)
        _gdelt_last = time.time()
        response = await client().get(
            GDELT_URL,
            params={
                "query": f"{query} sourcelang:english",
                "mode": "artlist",
                "format": "json",
                "maxrecords": 25,
                "timespan": "4months",
                "sort": "datedesc",
            },
        )
    if response.status_code != 200 or not response.text.strip().startswith("{"):
        raise RuntimeError("GDELT unavailable")
    articles = response.json().get("articles", [])
    out = []
    for item in articles:
        seen = item.get("seendate", "")
        stamp = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) >= 8 else None
        out.append({"title": item.get("title", "").strip(), "url": item.get("url"), "source": item.get("domain"), "date": stamp, "image": item.get("socialimage") or None})
    return out


async def _google(query: str):
    response = await client().get(GOOGLE_RSS, params={"q": f"{query} when:120d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    response.raise_for_status()
    root = ET.fromstring(response.text)
    out = []
    for item in root.iter("item"):
        title = html.unescape(item.findtext("title") or "")
        source = item.findtext("source") or ""
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        stamp = None
        raw_date = item.findtext("pubDate")
        if raw_date:
            try:
                stamp = parsedate_to_datetime(raw_date).date().isoformat()
            except (TypeError, ValueError):
                stamp = None
        out.append({"title": title.strip(), "url": item.findtext("link"), "source": source, "date": stamp, "image": None})
        if len(out) >= 25:
            break
    return out


def _dedupe(items):
    seen = set()
    out = []
    for item in items:
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def headlines(region_label: str | None = None):
    place = f'"{region_label}" Ethiopia' if region_label else "Ethiopia"
    gdelt_query = f'{place} (drought OR rainfall OR "dry spell" OR flood OR "El Nino" OR "La Nina")'
    google_query = f"{place} drought OR rainfall OR rains OR flood"
    key = f"news:{region_label or 'national'}"

    async def produce():
        provider = "GDELT 2.0 DOC API"
        try:
            items = await _gdelt(gdelt_query)
            if len(items) < 3:
                raise RuntimeError("thin")
        except Exception:
            provider = "Google News RSS"
            items = await _google(google_query)
        items = _dedupe(items)[:14]
        relevant_words = ["rain", "drought", "dry", "flood", "water", "harvest", "crop", "el ni", "la ni", "climate", "hunger", "food", "pasture", "livestock"]
        filtered = [i for i in items if any(w in i["title"].lower() for w in relevant_words)] or items
        for item in filtered:
            item["causes"] = tag_causes(item["title"])
        counts: dict[str, int] = {}
        for item in filtered:
            for cause in item["causes"]:
                counts[cause] = counts.get(cause, 0) + 1
        signals = sorted(({"cause": c, "mentions": n} for c, n in counts.items()), key=lambda s: -s["mentions"])
        return {"provider": provider, "query": google_query if provider.startswith("Google") else gdelt_query, "articles": filtered[:10], "signals": signals}

    return await cache.cached(key, 4 * 3600, produce)
