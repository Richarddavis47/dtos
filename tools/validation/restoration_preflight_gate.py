"""Metadata-only HTTP acceptance in an actually enforced disposable 2 GiB job.

This is not a restoration profile or live Granite acceptance. The fixture file
has a declared logical size, contains no real roster, and is never decoded.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import gc
import json
import logging
import os
from pathlib import Path
import platform
from secrets import token_urlsafe
import subprocess
import tempfile
from time import perf_counter
from unittest.mock import patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix='dtos-preflight-')
    fixture = Path(temporary.name)
    for key, filename in {'CACHE': 'cache.json', 'METADATA_DB': 'metadata.sqlite3',
                          'PROJECTION_DB': 'projection.sqlite3', 'FOIS_DB': 'fois.sqlite3',
                          'INTELLIGENCE_CHECKPOINT': 'intelligence.sqlite3',
                          'HISTORY_DB': 'history.sqlite3', 'ACCOUNT_DB': 'accounts.sqlite3'}.items():
        os.environ['DTOS_' + key + '_FILE'] = str(fixture / filename)
    token = token_urlsafe(32)  # Disposable in-process credential; never serialized.
    os.environ.update(DTOS_INSPECTION_AUTH_TOKEN=token, DTOS_DURABLE_HISTORY_REQUIRED='0',
                      SLEEPER_BASE_URL='http://127.0.0.1:9/v1', SLEEPER_LEAGUE_ID='1800000000000000000',
                      DTOS_HISTORY_STORAGE_ROOT=str(fixture),
                      DTOS_SLEEPER_SEASON_CACHE_ROOT=str(fixture / 'seasons'))
    import psutil
    import dtos_app
    from fastapi.testclient import TestClient
    from services import league_preparation
    from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot
    from src.platform.memory_reclamation import release_unused_allocator_pages

    limit = 2 * 1024**3
    assert memory_snapshot()['cgroup_limit_bytes'] == limit
    assert Path('/sys/fs/cgroup/memory.swap.max').read_text().strip() == '0'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if os.environ.get('DTOS_EXPECTED_HEAD'):
        assert head == os.environ['DTOS_EXPECTED_HEAD']
        assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    report = {'head': head, 'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
              'python': platform.python_version(), 'enforced_limit': limit, 'swap_limit': 0,
              'scope': 'Disposable metadata-only HTTP; not actual Granite cache, restoration, FOIS rebuild or live acceptance.',
              'cases': [], 'liveness': [], 'complete': False, 'passed': False}
    report_path = args.output / 'result.json'
    league = '1314695233040052224'
    cache = dtos_app.league_cache_file(league)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open('wb') as handle:
        handle.write(b'DISPOSABLE_NOT_JSON_NEVER_DECODE')
        handle.truncate(23_048_708)
    original = cache.stat()
    before_runtimes = tuple(dtos_app.league_runtime_manager._runtimes)
    padding = None
    times = []

    class Timing(logging.Handler):
        def emit(self, record):
            if getattr(record, 'event', None) == 'request_complete' and getattr(record, 'path', None) == '/health/live':
                times.append(record.duration_ms)

    timing = Timing()
    logging.getLogger('dtos.request').addHandler(timing)
    client = TestClient(dtos_app.app)

    def release_pressure():
        nonlocal padding
        padding = None
        gc.collect()
        release_unused_allocator_pages()

    def pressure(headroom):
        nonlocal padding
        release_pressure()
        current = memory_snapshot()['cgroup_current_bytes']
        padding = bytearray(max(0, limit - headroom - current))
        for index in range(0, len(padding), 4096):
            padding[index] = 1

    def observe(name, verdict, reason):
        start = perf_counter()
        response = client.get('/api/inspect/operations/restoration-preflight',
                              params={'league_id': league}, headers={'X-DTOS-Inspection-Auth': token})
        assert response.status_code == 200, response.status_code
        body = response.json()
        assert body['verdict'] == verdict and body['reason'] == reason, (name, body['verdict'], body['reason'])
        assert body['advisory_only'] and body['non_atomic'] and body['recheck_required']
        assert body['process']['pid'] == os.getpid()
        assert body['cache']['size_bytes'] == 23_048_708
        assert body['cache']['payload_readability'] == 'not_checked'
        assert body['cache']['content_compatibility'] == 'not_evaluated'
        assert tuple(dtos_app.league_runtime_manager._runtimes) == before_runtimes
        assert cache.stat().st_mtime_ns == original.st_mtime_ns
        report['cases'].append({'name': name, 'elapsed_ms': (perf_counter() - start) * 1000,
                                'harness_padding_bytes': len(padding) if padding is not None else 0,
                                'response': body})
        count = len(times)
        started = perf_counter()
        assert client.get('/health/live').status_code == 200
        assert len(times) == count + 1 and times[-1] < 500
        report['liveness'].append({'case': name, 'server_ms': times[-1],
                                   'client_ms': (perf_counter() - started) * 1000})

    try:
        with ExitStack() as guards:
            sentinels = [
                guards.enter_context(patch.object(dtos_app.account_service.store, 'context_for_session', side_effect=AssertionError('No account lookup'))),
                guards.enter_context(patch.object(dtos_app.league_runtime_manager, 'acquire_request', side_effect=AssertionError('No hydration'))),
                guards.enter_context(patch.object(league_preparation, 'restore_cached_runtime', side_effect=AssertionError('No restoration'))),
                guards.enter_context(patch.object(lifecycle_coordinator, 'phase', side_effect=AssertionError('No heavyweight lease'))),
                guards.enter_context(patch.object(league_preparation, 'load_cache_json', side_effect=AssertionError('No JSON decode'))),
            ]
            observe('healthy', 'would_admit', 'sufficient_headroom')
            pressure(350 * 1024**2)
            observe('capacity_deferred', 'would_defer', 'insufficient_headroom')
            release_pressure()
            observe('pressure_relieved', 'would_admit', 'sufficient_headroom')
            lifecycle_coordinator.reserve_fois_generation()
            try:
                pressure(900 * 1024**2)
                observe('fois_reserve_protected', 'would_defer', 'insufficient_headroom')
            finally:
                lifecycle_coordinator.release_fois_generation()
            observe('fois_released_same_pressure', 'would_admit', 'sufficient_headroom')
            release_pressure()
            assert all(mock.call_count == 0 for mock in sentinels)
            report['guarded_operation_calls'] = [mock.call_count for mock in sentinels]
        assert not psutil.Process().children(recursive=True)
        assert not memory_snapshot()['cgroup_memory_events']['oom_kill']
        report.update(passed=True, complete=True, final_memory=memory_snapshot(),
                      kernel_peak_bytes=int(Path('/sys/fs/cgroup/memory.peak').read_text()),
                      children_after=[], runtime_population_unchanged=True,
                      no_private_payload_decoded=True)
    finally:
        release_pressure()
        client.close()
        logging.getLogger('dtos.request').removeHandler(timing)
        temporary.cleanup()
        report['scratch_removed'] = not fixture.exists()
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    assert report['scratch_removed']
    print(json.dumps({'passed': report['passed'], 'complete': report['complete'],
                      'cases': len(report['cases']), 'source': head}, indent=2))


if __name__ == '__main__':
    main()
