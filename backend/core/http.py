import asyncio

import httpx

_clients: dict[int, httpx.AsyncClient] = {}
_gates: dict[int, asyncio.Semaphore] = {}


def loop_key() -> int:
    return id(asyncio.get_running_loop())


def client() -> httpx.AsyncClient:
    key = loop_key()
    existing = _clients.get(key)
    if existing is None or existing.is_closed:
        existing = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=12.0),
            headers={"User-Agent": "ZinabLab/2.0 (NASA Space Apps rainfall research dashboard)"},
            follow_redirects=True,
        )
        _clients[key] = existing
    return existing


async def get_json(url: str, params: dict | None = None, gate: asyncio.Semaphore | None = None, retries: int = 2):
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if gate:
                async with gate:
                    response = await client().get(url, params=params)
            else:
                response = await client().get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Request failed for {url}: {last_error}")


async def get_text(url: str, params: dict | None = None):
    response = await client().get(url, params=params)
    response.raise_for_status()
    return response.text


def power_gate() -> asyncio.Semaphore:
    return _gates.setdefault(loop_key(), asyncio.Semaphore(6))


async def close():
    existing = _clients.pop(loop_key(), None)
    if existing is not None and not existing.is_closed:
        await existing.aclose()
