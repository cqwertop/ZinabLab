import asyncio

import httpx

_client: httpx.AsyncClient | None = None
_power_gate = asyncio.Semaphore(6)


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=12.0),
            headers={"User-Agent": "ZinabLab/2.0 (NASA Space Apps rainfall research dashboard)"},
            follow_redirects=True,
        )
    return _client


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
    return _power_gate


async def close():
    if _client is not None and not _client.is_closed:
        await _client.aclose()
