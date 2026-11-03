"""Bounded league-entry proof in an enforced 2 GiB disposable container.

External source-shape fixture preparation is separate from observation. Padding
is explicitly harness memory and is never subtracted to claim usable headroom.
"""
import argparse
import asyncio
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        from datetime import datetime, timezone
        data = json.loads(args.input.read_text())
        target = args.output / 'source-cache.json'
        target.write_text(json.dumps({'data':data, 'last_sync':datetime.now(timezone.utc).isoformat()},separators=(',',':')))
        print(json.dumps({'phase':'fixture preparation before application observation', 'cache_bytes':target.stat().st_size}))
        return
    from services import league_preparation as preparation
    import dtos_app
    import psutil
    from fastapi.testclient import TestClient
    import logging
    from src.core.fois import process_execution as workers
    from src.core.league_runtime import LeagueRuntime
    from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot
    from src.platform.memory_reclamation import release_unused_allocator_pages
    from tests.test_league_entry_coordination import EntryHTTPTests
    from tests.test_trade_resource_admission import TradeResourceHTTPTests

    assert memory_snapshot()['cgroup_limit_bytes'] == 2 * 1024**3
    assert Path('/sys/fs/cgroup/memory.swap.max').read_text().strip() == '0'
    result = {'scope':'Disposable enforced 2 GiB; real worker with bounded diagnostic task, not a production FOIS rebuild. Large source-shaped cache plus separate actual one-QB HTTP controls. No live Granite acceptance.',
              'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
              'working_tree_clean':not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),
              'samples':[], 'fixture_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest()}
    if os.environ.get('DTOS_EXPECTED_HEAD'):
        assert result['head'] == os.environ['DTOS_EXPECTED_HEAD'] and result['working_tree_clean']
    server_timings = []
    class Timing(logging.Handler):
        def emit(self, record):
            if getattr(record, 'event', None) == 'request_complete' and getattr(record, 'path', None) == '/health/live':
                server_timings.append(record.duration_ms)
    timing = Timing()
    logging.getLogger('dtos.request').addHandler(timing)
    client = TestClient(dtos_app.app)
    def liveness(label):
        count = len(server_timings)
        started = time.monotonic()
        response = client.get('/health/live')
        elapsed = (time.monotonic() - started) * 1000
        assert response.status_code == 200 and len(server_timings) == count + 1
        assert server_timings[-1] < 500
        result.setdefault('liveness', []).append({'state':label, 'server_ms':server_timings[-1], 'client_ms':elapsed})
    stop = threading.Event()
    def observe(label):
        s = memory_snapshot()
        stat = dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        sample = {'time':time.monotonic(), 'label':label, **s,
                  **{k:int(stat[k]) for k in ('anon','file','inactive_file','kernel')},
                  'processes':[]}
        for p in [psutil.Process(), *psutil.Process().children(recursive=True)]:
            try:
                sample['processes'].append({'pid':p.pid,'parent':p.ppid(),'rss':p.memory_info().rss,'status':p.status()})
            except psutil.Error:
                pass
        result['samples'].append(sample)
        return sample
    def watch():
        while not stop.wait(.05):
            observe('sample')
    thread = threading.Thread(target=watch)
    thread.start()
    padding = None
    runtime = None
    try:
        observe('launch')
        # This uses the actual protected process executor. Submission occurs
        # before pressure is applied; no admission check is bypassed.
        worker = workers.warm_fois_executor_sync()
        future = workers._submit(time.sleep, 10)
        lifecycle_coordinator.reserve_fois_generation()
        try:
            observe('active_fois_worker')
            for name in ('test_warm_league_reads_work_while_fois_is_active_without_new_preparation',
                         'test_saved_publication_serves_cold_entry_during_fois_without_new_heavy_work',
                         'test_busy_cold_entry_has_truthful_status_no_source_calls_or_account_mutations'):
                # These HTTP controls reserve their own lease, symmetrically
                # counted with this real active process owner.
                test = EntryHTTPTests(name)
                test.setUp()
                try:
                    getattr(test,name)()
                finally:
                    test.doCleanups()
            result['warm_cold_saved_http'] = 'passed'
            current = memory_snapshot()['cgroup_current_bytes']
            padding = bytearray(max(0, 1490 * 1024**2 - current))
            for i in range(0, len(padding), 4096):
                padding[i] = 1
            result['harness_padding_bytes'] = len(padding)
            observe('before_large_restore_with_fois')
            liveness('active_fois_and_warm_resources')
            assert not future.done(), 'The overlap control must still be executing'
            runtime = LeagueRuntime('league-1')
            def publish(selected):
                projection = dtos_app.ProjectionService(league_id=selected.league_id, scoring_profile_id=selected.scoring_profile)
                projection.restore_into(selected.state['data'])
                dtos_app._publish_runtime_context(selected, projection)
            with patch.object(preparation, 'league_cache_file', return_value=args.input):
                assert preparation.restore_cached_runtime(runtime, publish, expected_season=2026)
            observe('after_large_restore_with_fois')
            liveness('restored_while_fois_owned')
            assert runtime.lifecycle['cache_restore'] == 'restored'
            # Verify safe deferral before decoding under independently measured
            # low headroom, rather than treating the first restore as capacity proof.
            extra = bytearray(max(0, 2*1024**3 - memory_snapshot()['cgroup_current_bytes'] - 200*1024**2))
            for i in range(0,len(extra),4096):
                extra[i] = 1
            observe('unsafe_pressure')
            liveness('unsafe_pressure_deferred')
            blocked = LeagueRuntime('league-1')
            with patch.object(preparation, 'league_cache_file', return_value=args.input):
                try:
                    preparation.restore_cached_runtime(blocked, publish)
                except preparation.HeavyWorkDeferred:
                    result['pressure_deferred'] = True
                else:
                    raise AssertionError('Unsafe cache decoding was admitted')
            assert not blocked.state['data']
            del extra
            future.result(timeout=15)
        finally:
            lifecycle_coordinator.release_fois_generation()
        padding = None
        asyncio.run(runtime.close())
        gc.collect()
        release_unused_allocator_pages()
        observe('pressure_relieved')
        runtime = LeagueRuntime('league-1')
        with patch.object(preparation, 'league_cache_file', return_value=args.input):
            assert preparation.restore_cached_runtime(runtime, publish, expected_season=2026)
        observe('recovered_restore')
        liveness('recovered')
        result['recovery_completed'] = True
        asyncio.run(runtime.close())
        test = TradeResourceHTTPTests('test_one_qb_supported_legal_pre_post_and_unchanged_source')
        test.setUp()
        try:
            # Use the restored JSON source, not only an already-live fixture.
            cache = args.output / 'one-qb-cache.json'
            from datetime import datetime, timezone
            cache.write_text(json.dumps({'data':test.f.data, 'last_sync':datetime.now(timezone.utc).isoformat()}))
            restored = LeagueRuntime(test.f.data['league']['league_id'])
            with patch.object(preparation, 'league_cache_file', return_value=cache):
                assert preparation.restore_cached_runtime(restored, lambda _:None, expected_season=2026)
            test.f.data = restored.state['data']
            test.test_one_qb_supported_legal_pre_post_and_unchanged_source()
            result['one_qb_k_def_http_evaluation'] = 'passed'
        finally:
            test.doCleanups()
            cache.unlink(missing_ok=True)
        # Cleanup/cancellation have dedicated regression controls; do not call
        # deferred work a historical completion here.
        result['fois_worker_pid'] = worker['pid']
        workers.shutdown_fois_executor_sync()
        assert not psutil.pid_exists(worker['pid'])
        result['worker_reaped'] = True
        observe('cleanup')
        events = memory_snapshot()['cgroup_memory_events']
        assert events['oom'] == events['oom_kill'] == 0
        assert hashlib.sha256(args.input.read_bytes()).hexdigest() == result['fixture_sha256']
        result.update(passed=True, complete=True, cgroup_lifetime_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text()))
    finally:
        padding = None
        workers.shutdown_fois_executor_sync()
        stop.set()
        thread.join()
        client.close()
        logging.getLogger('dtos.request').removeHandler(timing)
        (args.output/'result.json').write_text(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
