"""Validation-only completed-fixture cleanup; never imported by production."""
import gc
import json
from pathlib import Path
import time


def reclaim_completed_fixtures(module, output):
    from src.platform.lifecycle import memory_snapshot
    from src.platform.memory_reclamation import release_unused_allocator_pages
    before = memory_snapshot()
    started = time.monotonic()
    collected = gc.collect()
    trimmed = release_unused_allocator_pages()
    after = memory_snapshot()
    row = dict(scope='Between completed unittest modules only: unreachable Python fixtures and free native allocator pages; no cache eviction, worker retirement, admission override or live reference removal',
               module=module, collected=collected, allocator_trimmed=trimmed,
               elapsed_seconds=time.monotonic()-started, before=before, after=after)
    path = Path(output)
    with path.open('a') as stream:
        stream.write(json.dumps(row,separators=(',',':'))+'\n')
    return row
