"""Retain standard discovery imports; execute normal browser fixture first.

This is a disposable ordering experiment, not replacement canonical validation.
No application memory observation, admission, or browser assertion is mocked.
"""
import gc
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest

import psutil

ROOT = Path('/app')
OUTPUT = Path('/evidence/collection-isolation')
FIXTURE = OUTPUT / 'fixture'
OUTPUT.mkdir(exist_ok=True)
FIXTURE.mkdir(exist_ok=True)
# Use the same disposable canonical source/environment boundaries.
canonical = Path('/evidence/canonical/runner.py').read_text()
exec(canonical[canonical.index('os.environ.setdefault'):canonical.index('git_n =')])
sys.path.insert(0, str(ROOT))
from src.platform.memory_reclamation import release_unused_allocator_pages
from src.platform.trade_execution import assess_memory, observe_memory

process = psutil.Process()
samples = []
stop = threading.Event()
def sample():
    while not stop.wait(.5):
        samples.append(dict(time=time.time(), memory=observe_memory(),
                            rss=process.memory_info().rss))

initial = observe_memory()
assert initial['cgroup_limit_bytes'] == 2147483648
thread = threading.Thread(target=sample)
thread.start()
started = time.monotonic()
try:
    # Same collection used by the full canonical unittest gate.
    collection = unittest.defaultTestLoader.discover('tests')
    collection_count = collection.countTestCases()
    gc.collect()
    release_unused_allocator_pages()
    collected = dict(memory=observe_memory(), rss=process.memory_info().rss)
    print('FULL_COLLECTION_BASELINE ' + json.dumps(dict(
        tests=collection_count, **collected)), flush=True)
    module = os.environ.get('DTOS_BROWSER_MODULE', 'tests.test_trade_simple_browser')
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    del suite, collection
    gc.collect()
    release_unused_allocator_pages()
    time.sleep(.2)
    report = dict(scope='Full standard discovery imports followed by isolated normal browser journey before accumulated test execution; actual 2 GiB cgroup',
        collection_tests=collection_count, tests=result.testsRun,
        errors=len(result.errors), failures=len(result.failures),
        success=result.wasSuccessful(), initial=initial, collected=collected,
        final_memory=observe_memory(), final_rss=process.memory_info().rss,
        peak_bytes=int(Path('/sys/fs/cgroup/memory.peak').read_text()),
        elapsed_seconds=time.monotonic()-started,
        memory_events=Path('/sys/fs/cgroup/memory.events').read_text(),
        live_children=[dict(pid=p.pid, name=p.name()) for p in process.children(recursive=True)
                       if p.is_running() and p.status()!=psutil.STATUS_ZOMBIE])
    (OUTPUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COLLECTION_ISOLATION_RESULT ' + json.dumps(report), flush=True)
finally:
    stop.set()
    thread.join()
    (OUTPUT/'memory.json').write_text(json.dumps(samples,indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
