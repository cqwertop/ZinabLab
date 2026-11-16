import asyncio
import hashlib
import json
import time
from typing import Any, Awaitable, Callable

from .paths import CACHE_DIR

_memory: dict[str, tuple[float, Any]] = {}
_locks: dict[tuple[int, str], asyncio.Lock] = {}


def _file(key: str):
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def _load(key: str):
    hit = _memory.get(key)
    if hit:
        return hit
    path = _file(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    entry = (payload["t"], payload["v"])
    _memory[key] = entry
    return entry


def read(key: str, ttl: float):
    entry = _load(key)
    if entry and time.time() - entry[0] < ttl:
        return entry[1]
    return None


def read_stale(key: str):
    entry = _load(key)
    return entry[1] if entry else None


def write(key: str, value: Any):
    stamp = time.time()
    _memory[key] = (stamp, value)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _file(key).with_suffix(".tmp")
    tmp.write_text(json.dumps({"t": stamp, "k": key, "v": value}), "utf-8")
    tmp.replace(_file(key))


async def cached(key: str, ttl: float, producer: Callable[[], Awaitable[Any]]):
    value = read(key, ttl)
    if value is not None:
        return value
    lock = _locks.setdefault((id(asyncio.get_running_loop()), key), asyncio.Lock())
    async with lock:
        value = read(key, ttl)
        if value is not None:
            return value
        try:
            value = await producer()
        except Exception:
            stale = read_stale(key)
            if stale is not None:
                return stale
            raise
        if value is not None:
            write(key, value)
        return value
