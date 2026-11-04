"""Isolated observer; no route, cache, generation, or application mutation."""
import ctypes
import json
import os
from pathlib import Path
import sys
import threading
import time

if sys.platform != "linux" or os.environ.get("RENDER") or os.environ.get("DTOS_PRODUCTION_SHAPED_FIXTURE") != "1":
    raise RuntimeError("Sustained observer requires isolated Linux fixture")

from dtos_app import app  # noqa: E402,F401
from src.core.intelligence.cache import intelligence_cache  # noqa: E402


class MallInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_size_t) for name in (
        "arena", "ordblks", "smblks", "hblks", "hblkhd", "usmblks",
        "fsmblks", "uordblks", "fordblks", "keepcost")]


def observe():
    libc = ctypes.CDLL(None)
    mallinfo = getattr(libc, "mallinfo2", None)
    if mallinfo:
        mallinfo.restype = MallInfo
    with Path("/output/server-memory.jsonl").open("w") as stream:
        while True:
            row = {"timestamp": time.time(), "python_allocated_blocks": sys.getallocatedblocks()}
            if mallinfo:
                info = mallinfo()
                row["glibc"] = {key: getattr(info, key) for key in ("arena", "hblkhd", "uordblks", "fordblks", "keepcost")}
            if intelligence_cache._lock.acquire(blocking=False):
                try:
                    row["intelligence_cache"] = {
                        "entries": len(intelligence_cache._entries),
                        "hits": intelligence_cache.hits, "misses": intelligence_cache.misses,
                        "invalidations": intelligence_cache.invalidations}
                finally:
                    intelligence_cache._lock.release()
            else:
                row["cache_lock_busy"] = True
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            time.sleep(.25)


threading.Thread(target=observe, name="fixture-memory-observer", daemon=True).start()
