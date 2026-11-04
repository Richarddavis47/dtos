"""Return unused native allocator pages without evicting application state."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import lru_cache
import sys


@lru_cache(maxsize=1)
def _native_trim():
    if sys.platform != "linux":
        return None
    import ctypes

    try:
        trim = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


def release_unused_allocator_pages() -> bool:
    """glibc releases only free pages; no GC, caches, database or provider work."""
    trim = _native_trim()
    return bool(trim(0)) if trim is not None else False


async def maintain_unused_memory(
    request_count: Callable[[], int], ready: Callable[[], bool],
    *, interval: float = 1.0, retire_idle: Callable[[], bool] | None = None,
    expire_one: Callable[[], bool] | None = None,
    expiry_limit: int = 1,
) -> None:
    """At most one off-loop reclamation per interval, only after read activity.

    This is not memory admission and never discounts or alters cgroup metrics.
    Unlike full Python GC it does not traverse live intelligence under the GIL.
    """
    previous = request_count()
    while True:
        await asyncio.sleep(interval)
        current = request_count()
        if not ready() or current == previous:
            continue
        previous = current
        if retire_idle is not None:
            await asyncio.to_thread(retire_idle)
        if expire_one is not None:
            # Drain the expired backlog, bounded by the cache's capacity.
            # Each disposal yields separately; no large graph destruction batch
            # holds the event loop or the cache lock. Busy caches stop the pass.
            for _ in range(expiry_limit):
                if not await asyncio.to_thread(expire_one):
                    break
        await asyncio.to_thread(release_unused_allocator_pages)
