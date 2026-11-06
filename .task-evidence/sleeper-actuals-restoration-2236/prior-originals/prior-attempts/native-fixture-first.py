"""Real 2 GiB unused-reference recovery; reuse the sealed prior study's inputs.

This is not a Granite payload profile or a proposed allocation multiplier.
Explicit harness pressure is included in raw cgroup usage without deductions.
"""
import argparse
import asyncio
import gc
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch
import weakref
import zipfile

STUDY_SHA256 = "df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439"
LIMIT = 2 * 1024**3
MIB = 1024**2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-actuals', action='store_true',
                        help='Add explicit fictional native matchup rows to copies of the sealed inputs.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assert args.archive.stat().st_size == 9072793
    assert hashlib.sha256(args.archive.read_bytes()).hexdigest() == STUDY_SHA256
    result = {'scope': __doc__, 'prior_archive_sha256': STUDY_SHA256,
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
              'working_tree_clean': not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip(),
              'samples': [], 'liveness': [], 'passed': False}
    if os.environ.get('DTOS_EXPECTED_HEAD'):
        assert result['head'] == os.environ['DTOS_EXPECTED_HEAD'] and result['working_tree_clean']
    scratch = tempfile.TemporaryDirectory(prefix='restoration-unused-')
    root = Path(scratch.name)
    with zipfile.ZipFile(args.archive) as archive:
        for name in ('oneqb.json', 'superflex.json', 'projections.sqlite3'):
            with archive.open('granite-scale/' + name) as reader, (root/name).open('wb') as writer:
                shutil.copyfileobj(reader, writer)
    for key in ('CACHE', 'METADATA_DB', 'INTELLIGENCE_CHECKPOINT', 'FOIS_DB', 'HISTORY_DB', 'ACCOUNT_DB'):
        os.environ['DTOS_' + key + '_FILE'] = str(root / (key.lower() + '.sqlite3'))
    os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),
                      DTOS_DURABLE_HISTORY_REQUIRED='0', DTOS_HISTORY_STORAGE_ROOT=str(root),
                      DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'),
                      SLEEPER_BASE_URL='http://127.0.0.1:9/v1')
    if args.native_actuals:
        from services.matchup_season import prepare_season_matchups
        from src.core.player_value_projection.sleeper_actuals import scoring_identity
        native_expected = {}
        for name in ('oneqb.json', 'superflex.json'):
            path = root/name
            payload = json.loads(path.read_bytes())
            data = payload['data']
            league = data['league']
            league.update(sport='nfl', status='in_season')
            league['settings'].update(leg=9, last_scored_leg=8, start_week=1,
                playoff_week_start=15, playoff_teams=6, playoff_round_type=0, playoff_type=0)
            data['week'] = 9
            rows = []
            for team in data['teams']:
                ids = [str(p['id']) for p in team['players']]
                scores = {pid:(0 if i == 0 else -2.125 if i == 1 else 23.4738) for i,pid in enumerate(ids)}
                rows.append(dict(roster_id=team['roster_id'], players=ids, starters=ids[:1],
                    players_points=scores, starters_points=[scores[ids[0]]]))
            async def fetch(_):
                return rows
            data['season_matchups'] = asyncio.run(prepare_season_matchups(league,9,rows,fetch,
                observed_at='2026-11-06T00:00:00Z'))
            data['canonical_player_production'] = dict(league_id=str(league['league_id']),
                season=league['season'], scoring_fingerprint=scoring_identity(data['scoring_settings']),
                reference_generation='frozen-disposable-reference', players={})
            path.write_text(json.dumps(payload,separators=(',',':')))
            native_expected[name] = rows[0]['players_points']
        result['native_fixture_scope'] = 'New explicit fictional matchup rows added to copies only; original archive unchanged. Not live scores or a private Granite profile.'
        del data, payload, rows, scores
    import dtos_app
    import psutil
    from fastapi.testclient import TestClient
    from services import league_preparation as prep
    from src.core.league_runtime import LeagueRuntime
    from src.core.intelligence.context import IntelligenceContext
    from src.core.intelligence.models import IntelligenceResult
    from src.core.intelligence.cache import intelligence_cache
    from src.core.fois import process_execution as workers
    from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot, HeavyWorkDeferred
    from src.platform.memory_reclamation import release_unused_allocator_pages

    assert memory_snapshot()['cgroup_limit_bytes'] == LIMIT
    assert Path('/sys/fs/cgroup/memory.swap.max').read_text().strip() == '0'
    timings = []
    class Timing(logging.Handler):
        def emit(self, record):
            if getattr(record, 'event', None) == 'request_complete' and getattr(record, 'path', None) == '/health/live':
                timings.append(record.duration_ms)
    handler = Timing()
    logging.getLogger('dtos.request').addHandler(handler)
    client = TestClient(dtos_app.app)
    def live(label):
        n = len(timings)
        started = time.monotonic()
        assert client.get('/health/live').status_code == 200
        assert len(timings) == n+1 and timings[-1] < 500
        result['liveness'].append({'label':label, 'server_ms':timings[-1], 'client_ms':(time.monotonic()-started)*1000})
    def sample(label):
        stat = dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        record = dict(label=label, monotonic=time.monotonic(), **memory_snapshot(),
                      **{k:int(stat[k]) for k in ('anon', 'file', 'inactive_file', 'kernel')}, processes=[])
        for proc in (psutil.Process(), *psutil.Process().children(recursive=True)):
            try:
                record['processes'].append(dict(pid=proc.pid, parent=proc.ppid(), rss=proc.memory_info().rss))
            except psutil.Error:
                pass
        result['samples'].append(record)
        return record
    def context(data):
        teams = tuple(data['teams'])
        ctx = IntelligenceContext(league_id=str(data['league']['league_id']), active_roster_id=1,
            league=data['league'], roster=teams[0], teams=teams, picks=(), settings=data['league']['scoring_settings'],
            opponents=teams[1:], market={}, front_offices=(), cached_data=data, user_preferences={}, snapshot_key='control')
        return IntelligenceResult(context=ctx, decision=None, decisions={}, player_portfolio=None,
            pick_portfolio=None, player_reports={}, front_office_model=None, trades=(), market=None,
            player_values={}, roster=None, league=None, recommendation=None, timings_ms={}, cache_hit=False)
    cache = root/'oneqb.json'
    result['cache_bytes'] = cache.stat().st_size
    result['cache_sha256'] = hashlib.sha256(cache.read_bytes()).hexdigest()
    result['limitations'] = ['Reused 10000-identity/two-week synthetic catalog, not private Granite payload.',
        'Expired ownership graphs are real cache/context types; no completed FOIS/intelligence grade is claimed.',
        'Five-ms samples may miss brief peaks. Kernel lifetime peak includes harness pressure.',
        'This is disposable execution, not live league recovery or Sleeper parity.']
    active, recovered, warm_values, refs = [], [], [], []
    padding = None
    try:
        for name in ('oneqb.json', 'superflex.json'):
            data = json.loads((root/name).read_text())['data']
            runtime = LeagueRuntime(str(data['league']['league_id']))
            runtime.apply_data(data)
            runtime.active_requests = 1
            active.append(runtime)
            warm_values.append(data)
        result['warm_structures'] = [{k:len(d.get(k) or ()) for k in ('teams','players','normalized_players')} for d in warm_values]
        fresh = intelligence_cache.get_or_create('unused-proof:fresh', lambda:context(warm_values[0]), ttl=3600)
        for number in range(3):
            value = intelligence_cache.get_or_create('unused-proof:old-'+str(number),
                lambda:context(json.loads(cache.read_text())['data']), ttl=0)
            refs.append(weakref.ref(value))
            del value
        worker = workers.warm_fois_executor_sync()
        result['idle_worker_pid'] = worker['pid']
        gc.collect()
        release_unused_allocator_pages()
        initial = sample('warm_and_expired_ownership')
        padding = bytearray(max(0, LIMIT-initial['cgroup_current_bytes']-304*MIB))
        for i in range(0, len(padding), 4096):
            padding[i] = 1
        result['harness_padding_bytes'] = len(padding)
        before = sample('before_restore')
        plan = prep.restoration_admission(cache.stat().st_size, before, False,
            fois_working_bytes=prep.FOIS_WORKING, fois_safety_bytes=prep.FOIS_SAFETY)
        assert plan['would_admit'] is False
        result['before_plan'] = plan
        target = LeagueRuntime(active[0].league_id)
        recovered.append(target)
        def publish(runtime):
            projection = dtos_app.ProjectionService(league_id=runtime.league_id, scoring_profile_id=runtime.scoring_profile)
            result['attached_projection_rows'] = projection.restore_into(runtime.state['data'])
            dtos_app._publish_runtime_context(runtime, projection)
        samples, stop = [], threading.Event()
        def watch():
            while not stop.wait(.005):
                samples.append(memory_snapshot()['cgroup_current_bytes'])
        monitor = threading.Thread(target=watch)
        monitor.start()
        started = time.monotonic()
        try:
            with patch.object(prep, 'league_cache_file', return_value=cache):
                assert prep.restore_cached_runtime(target, publish, expected_season=2026)
        finally:
            stop.set()
            monitor.join()
        result['restore_seconds'] = time.monotonic()-started
        result['recovery'] = target.lifecycle['cache_restore_memory_recovery']
        result['raw_bytes_released'] = result['recovery']['before_bytes']-result['recovery']['after_bytes']
        result['sampled_increment_from_post_cleanup_bytes'] = max([result['recovery']['after_bytes'], *samples])-result['recovery']['after_bytes']
        assert result['recovery']['would_admit'] and result['recovery']['required_bytes'] == plan['required_bytes']
        assert all(ref() is None for ref in refs)
        assert intelligence_cache.peek('unused-proof:fresh') is fresh
        assert not psutil.pid_exists(worker['pid'])
        assert all(r.state['data'] is d and r.active_requests == 1 for r,d in zip(active,warm_values))
        assert target.state['data']['league'] == warm_values[0]['league']
        if args.native_actuals:
            actuals = target.state['data']['canonical_player_production']['sleeper_actuals']
            source = target.state['data']['season_matchups']
            expected = native_expected['oneqb.json']
            for pid, value in expected.items():
                assert actuals['players'][pid][0]['points'] == value
            assert actuals['source_generation'] == source['semantic_generation']
            result['native_actuals'] = dict(passed=True, source_generation=actuals['source_generation'],
                admitted_generation=source['semantic_generation'], method=actuals['method_version'],
                expected_first_scores=list(expected.values())[:2],
                admitted_first_scores=[actuals['players'][pid][0]['points'] for pid in list(expected)[:2]],
                league_id=actuals['league_id'],season=actuals['season'],
                scoring_fingerprint=actuals['scoring_fingerprint'],
                observations=sum(len(v) for v in actuals['players'].values()))
        result['expired_released_active_and_fresh_preserved'] = True
        sample('restored')
        live('restored_with_warm_resources')
        padding = None
        # Hold actual unexpired ownership graphs. Cleanup must not delete them
        # merely to manufacture headroom. At fixed measured pressure, defer.
        for number in range(3):
            intelligence_cache.get_or_create('unused-proof:held-'+str(number),
                lambda:context(json.loads(cache.read_text())['data']), ttl=3600)
        gc.collect()
        release_unused_allocator_pages()
        pressure = sample('unexpired_contexts')
        padding = bytearray(max(0, LIMIT-pressure['cgroup_current_bytes']-304*MIB))
        for i in range(0, len(padding), 4096):
            padding[i] = 1
        result['held_harness_padding_bytes'] = len(padding)
        blocked = LeagueRuntime(active[0].league_id)
        with patch.object(prep, 'league_cache_file', return_value=cache):
            try:
                prep.restore_cached_runtime(blocked, publish)
            except HeavyWorkDeferred:
                pass
            else:
                raise AssertionError('Unexpired context pressure was unsafely admitted')
        assert not blocked.state['data']
        assert all(intelligence_cache.peek('unused-proof:held-'+str(n)) is not None for n in range(3))
        result['unsafe_pressure_deferred'] = blocked.lifecycle['cache_restore_memory_recovery']
        assert result['unsafe_pressure_deferred']['would_admit'] is False
        live('capacity_deferred')
        padding = None
        release_unused_allocator_pages()
        retry = LeagueRuntime(active[0].league_id)
        recovered.append(retry)
        with patch.object(prep, 'league_cache_file', return_value=cache):
            assert prep.restore_cached_runtime(retry, publish, expected_season=2026)
        result['explicit_retry_completed'] = True
        sample('recovered_after_pressure_relief')
        live('recovered')
        # Existing FOIS ownership, including its between-submission idle worker,
        # retains its full policy. This is a diagnostic task, not historical grading.
        worker = workers.warm_fois_executor_sync()
        lifecycle_coordinator.reserve_fois_generation()
        try:
            base = sample('fois_reserved')
            padding = bytearray(max(0, LIMIT-base['cgroup_current_bytes']-600*MIB))
            for i in range(0, len(padding), 4096):
                padding[i] = 1
            owner_blocked = LeagueRuntime(active[0].league_id)
            with patch.object(prep, 'league_cache_file', return_value=cache):
                try:
                    prep.restore_cached_runtime(owner_blocked, publish)
                except HeavyWorkDeferred:
                    pass
                else:
                    raise AssertionError('FOIS outstanding demand was spent on restoration')
            assert psutil.pid_exists(worker['pid']) and not owner_blocked.state['data']
            result['fois_reserved_plan'] = owner_blocked.lifecycle['cache_restore_memory_recovery']
            assert result['fois_reserved_plan']['required_bytes'] > plan['required_bytes']
            live('fois_reserved_deferral')
        finally:
            lifecycle_coordinator.release_fois_generation()
            padding = None
        result['fois_reserve_preserved'] = True
        workers.shutdown_fois_executor_sync()
        for runtime in recovered:
            asyncio.run(runtime.close())
        for runtime in active:
            runtime.active_requests = 0
            asyncio.run(runtime.close())
        recovered.clear()
        active.clear()
        warm_values.clear()
        del data, fresh, target, retry, runtime
        intelligence_cache.invalidate()
        gc.collect()
        release_unused_allocator_pages()
        final = sample('after_cleanup')
        children = psutil.Process().children(recursive=True)
        result['cleanup_processes'] = [dict(pid=p.pid, name=p.name(), resource_tracker=any('multiprocessing.resource_tracker' in v for v in p.cmdline())) for p in children]
        assert all(p['resource_tracker'] for p in result['cleanup_processes'])
        assert not psutil.pid_exists(worker['pid'])
        assert not lifecycle_coordinator.fois_generation_active()
        assert lifecycle_coordinator.snapshot()['phase'] == 'idle'
        assert final['cgroup_memory_events']['oom'] == final['cgroup_memory_events']['oom_kill'] == 0
        assert hashlib.sha256(cache.read_bytes()).hexdigest() == result['cache_sha256']
        result['kernel_lifetime_peak_bytes'] = int(Path('/sys/fs/cgroup/memory.peak').read_text())
        scratch.cleanup()
        result['scratch_removed'] = not root.exists()
        assert result['scratch_removed']
        result['passed'] = True
    finally:
        padding = None
        workers.shutdown_fois_executor_sync()
        client.close()
        logging.getLogger('dtos.request').removeHandler(handler)
        (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
