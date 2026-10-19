"""Disposable authenticated cold/warm/timeout probe; run inside a 2 GiB cgroup.

Uses the real sync/middleware/Home/FOIS process boundaries with a deterministic
12,322-player canonical fixture. External provider/history/Market preparation
is controlled, so this does not establish full-production OOM safety.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import AsyncMock, patch

import psutil


def run(output: Path, scenario: str) -> None:
    with tempfile.TemporaryDirectory(prefix='dtos-fois-memory-') as directory:
        root = Path(directory)
        for key in ('CACHE', 'PROJECTION_DB', 'METADATA_DB', 'INTELLIGENCE_CHECKPOINT', 'FOIS_DB', 'HISTORY_DB', 'ACCOUNT_DB'):
            os.environ['DTOS_' + key + '_FILE'] = str(root / (key.lower() + '.sqlite3' if key != 'CACHE' else 'cache.json'))
        os.environ.update(SLEEPER_BASE_URL='http://127.0.0.1:9/v1', DTOS_DURABLE_HISTORY_REQUIRED='0')
        from tools.validation import generate_sanitized_market_fixture as source
        source._cache(Path(os.environ['DTOS_CACHE_FILE']))
        from tests import test_cold_league_recovery as cold
        from src.core.fois import process_execution as execution
        from src.core.fois.repository import FOISRepository
        from src.core.fois.service import FOISService
        from src.platform.lifecycle import memory_snapshot
        import httpx

        f = cold.ColdLeagueRecoveryTests()
        f.setUp()
        samples, requests = [], []
        stopped = threading.Event()
        process = psutil.Process()

        def sample():
            row = {'elapsed': round(time.monotonic() - start, 3), **memory_snapshot()}
            processes = [process, *process.children(recursive=True)]
            rows = []
            for item in processes:
                try:
                    info = item.memory_full_info()
                    rows.append({'pid': item.pid, 'parent': item.pid == process.pid,
                                 'rss': info.rss, 'pss': getattr(info, 'pss', None),
                                 'uss': getattr(info, 'uss', None)})
                except psutil.Error:
                    pass
            row['processes'] = rows
            stat = Path('/sys/fs/cgroup/memory.stat')
            if stat.exists():
                values = dict(line.split() for line in stat.read_text().splitlines())
                row['anon_bytes'], row['file_bytes'] = int(values['anon']), int(values['file'])
            return row

        def monitor():
            while not stopped.wait(.05):
                samples.append(sample())

        start = time.monotonic()
        watcher = threading.Thread(target=monitor, daemon=True)
        watcher.start()
        try:
            with ExitStack() as stack:
                dtos = f.dtos
                data = json.loads(Path(os.environ['DTOS_CACHE_FILE']).read_text())['data']
                original = f.upstream
                def upstream(request):
                    path = request.url.path
                    for league in ('200', '300'):
                        if path.endswith('/league/' + league):
                            return httpx.Response(200, json={**data['league'], 'league_id': league, 'settings': {**data['league']['settings'], 'leg': 1}})
                        if path.endswith('/league/' + league + '/rosters'):
                            return httpx.Response(200, json=[{'roster_id': t['roster_id'], 'owner_id': 'cold-user' if t['roster_id'] == 1 else t['owner_id'], 'players': [p['id'] for p in t['players']], 'starters': [p['id'] for p in t['players'][:4]], 'settings': {}} for t in data['teams']])
                        if path.endswith('/league/' + league + '/users'):
                            return httpx.Response(200, json=[{'user_id': 'cold-user', 'display_name': 'Cold manager'}])
                    if path.endswith('/players/nfl'):
                        return httpx.Response(200, json=data['players'])
                    return original(request)
                f.upstream = upstream
                f.mode = 'valid'
                f.store.upsert_membership(f.account, {'league_id': '300', 'name': 'Fixture 300', 'season': '2026'}, 'cold-user', 1, 'Franchise 300', 'active')
                for name in ('start_background_backfill', 'resolve_historical_trade_market'):
                    stack.enter_context(patch.object(dtos, name, new_callable=AsyncMock, return_value={'status': 'complete'}))
                stack.enter_context(patch.object(dtos, 'history_progress_contracts'))
                stack.enter_context(patch.object(dtos.AssetMarketCache, 'reconcile'))
                stack.enter_context(patch('services.league_maintenance.ensure_periodic_refresh'))
                repository = FOISRepository(root / 'probe-fois.sqlite3')
                service = FOISService(repository)
                compute_calls = []
                original_submit = execution._submit
                if scenario == 'timeout':
                    stack.enter_context(patch.object(execution, '_submit', side_effect=lambda _f, *_a: original_submit(time.sleep, 15)))

                async def generate(current):
                    compute_calls.append(time.monotonic() - start)
                    # This explicit source fixture carries no historical grades.
                    current['fois_history'] = {}
                    scores, _, _ = await execution.generate_fois_isolated(current, repository, cache_file=None, timeout=1 if scenario == 'timeout' else 30)
                    return scores
                stack.enter_context(patch.object(dtos, 'fois_service', service))
                stack.enter_context(patch.object(dtos, '_generate_fois_coordinated', side_effect=generate))
                async def drain():
                    for runtime in f.manager.resident_runtimes():
                        while runtime.background_tasks:
                            await asyncio.gather(*tuple(runtime.background_tasks), return_exceptions=True)
                def browse(label):
                    began = time.monotonic()
                    response = f.client.get('/')
                    requests.append({'label': label, 'status': response.status_code, 'observed_ms': round((time.monotonic() - began) * 1000, 3), 'memory': sample()})
                    f.client.portal.call(drain)
                browse('cold-200')
                for index in range(5):
                    browse('warm-200-' + str(index))
                began = time.monotonic()
                selected = f.client.post('/api/account/active-league', json={'league_id': '300'}, headers={'X-CSRF-Token': f.csrf})
                requests.append({'label': 'select-cold-300', 'status': selected.status_code, 'observed_ms': round((time.monotonic() - began) * 1000, 3), 'memory': sample()})
                browse('cold-300')
                for index in range(5):
                    browse('warm-300-' + str(index))
                settled = sample()
                f.client.portal.call(execution.shutdown_fois_executor)
                after_worker = sample()
                result = {'scenario': scenario, 'scope': __doc__, 'python': os.sys.version,
                          'requests': requests, 'compute_attempts': len(compute_calls),
                          'peak_cgroup_bytes': max(s['cgroup_current_bytes'] or 0 for s in samples),
                          'peak_parent_rss': max(s['rss_bytes'] for s in samples),
                          'peak_process_pss': max(sum(p['pss'] or 0 for p in s['processes']) for s in samples),
                          'settled': settled, 'after_worker_shutdown': after_worker,
                          'temporary_compute_residue': len(list(root.rglob('.dtos-fois-compute-*'))),
                          'samples': samples}
                output.write_text(json.dumps(result, indent=2))
                print(json.dumps({k: v for k, v in result.items() if k not in {'requests', 'samples', 'scope', 'settled', 'after_worker_shutdown'}}))
        finally:
            stopped.set()
            watcher.join(2)
            f.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', choices=['healthy', 'timeout'], required=True)
    args = parser.parse_args()
    run(args.output, args.scenario)


if __name__ == '__main__':
    main()
