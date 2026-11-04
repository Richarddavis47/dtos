"""Authenticated residency/cleanup control requiring an actual 2 GiB cgroup.

Uses disposable accounts and generated canonical DTOs, not live accounts,
providers, FOIS scores or a production cold-latency benchmark. Three readers
hold separate scopes concurrently; active readers may temporarily exceed the
warm-cache limit, but completed reads must release that excess.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile


async def _exercise(root: Path) -> dict:
    import httpx
    import psutil
    from fastapi import FastAPI, Request
    from types import SimpleNamespace
    from tools.validation import generate_sanitized_market_fixture as source
    from src.core.accounts import AccountService, AccountStore
    from src.core.asset_market.resource_diagnostics import diagnostic_deep_size
    from src.core.history_context.store import CanonicalHistoryStore
    from src.core.league_runtime import LeagueRuntimeManager
    from src.core.league_runtime.context import CanonicalLeagueContext
    from src.platform.account_context import AccountContextMiddleware
    from src.platform.league_context import LeagueContextMiddleware, current_league_context
    from src.platform.lifecycle import memory_snapshot

    assert memory_snapshot()['cgroup_limit_bytes'] == 2_147_483_648, 'This resource control requires a real 2 GiB cgroup.'
    data = source._cache(root / 'canonical-fixture.json')
    encoded = json.dumps(data, separators=(',', ':'))
    del data
    source_identity = hashlib.sha256(encoded.encode()).hexdigest()
    history = CanonicalHistoryStore()
    store = AccountStore(root / 'accounts.sqlite3')
    service = AccountService(store)
    tokens = {}
    for league in ('200', '300', '400'):
        account, _ = service.create_account('fixture' + league, 'Disposable manager', 'disposable fixture password')
        store.link_sleeper(account, sleeper_user_id='owner' + league, username='fixture', display_name='Fixture')
        store.upsert_membership(account, {'league_id': league, 'name': 'Fixture', 'season': '2026'},
                                'owner' + league, 1, 'Fixture franchise', 'active')
        store.activate(account, league)
        tokens[league] = service.new_session(account)[0]

    async def hydrate(runtime):
        current = json.loads(encoded)
        current['league']['league_id'] = runtime.league_id
        runtime.apply_data(current)
        history.update_current(runtime.league_id, current)
        unavailable = SimpleNamespace(health=lambda: {'status': 'unavailable'})
        runtime.canonical_context = CanonicalLeagueContext(runtime, history, unavailable, unavailable, unavailable,
                                                          fois_state='unavailable', history_state='unavailable')
        return current

    manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
    manager.attach_default('100', {'data': {'league': {'league_id': '100', 'season': '2026'}}}, warm=True)
    app = FastAPI()
    app.add_middleware(LeagueContextMiddleware, manager=manager, default_league_id='100', import_enabled=False)
    app.add_middleware(AccountContextMiddleware, service=service, required=True)
    entered = {league: asyncio.Event() for league in tokens}
    release = asyncio.Event()

    @app.get('/')
    async def home(request: Request):
        selected = current_league_context()
        league = request.scope['dtos_authorized_league']
        entered[league].set()
        await release.wait()
        assert selected is not None and selected.data['league']['league_id'] == league
        return {'league_id': selected.league_id}

    def sample():
        parent = psutil.Process()
        info = parent.memory_full_info()
        row = {**memory_snapshot(), 'parent_pss': getattr(info, 'pss', None), 'parent_uss': getattr(info, 'uss', None),
               'history_current_leagues': len(history._current)}
        stat = dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        row.update(anonymous_bytes=int(stat['anon']), file_bytes=int(stat['file']),
                   kernel_cgroup_peak_bytes=int(Path('/sys/fs/cgroup/memory.peak').read_text()))
        return row

    tasks = []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://testserver') as client:
            for league, token in tokens.items():
                tasks.append(asyncio.create_task(client.get('/', headers={'Cookie': 'dtos_session=' + token})))
                ready = asyncio.create_task(entered[league].wait())
                done, _ = await asyncio.wait((ready, tasks[-1]), timeout=15, return_when=asyncio.FIRST_COMPLETED)
                if not entered[league].is_set():
                    ready.cancel()
                    await asyncio.gather(ready, return_exceptions=True)
                    if tasks[-1] in done:
                        response = await tasks[-1]
                        raise AssertionError(f'Fixture never entered authenticated Home: HTTP {response.status_code}')
                    raise TimeoutError('Fixture did not reach its scoped Home barrier')
            active = {'warm': manager.health()['warm_runtime_count'], 'memory': sample()}
            release.set()
            responses = await asyncio.gather(*tasks)
            completed = {'warm': manager.health()['warm_runtime_count'], 'memory': sample(),
                         'retained_data_sizes': [diagnostic_deep_size(r.state.get('data'), object_limit=1_000_000)
                                                 for r in manager.resident_runtimes()]}
            assert all(row.status_code == 200 for row in responses)
            assert {row.json()['league_id'] for row in responses} == set(tokens)
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await manager.shutdown()
    result = {'schema': 'navigation-residency-control-v1', 'python': os.sys.version, 'scope': __doc__,
              'source_identity': source_identity, 'source_assets': source.ASSET_COUNT, 'configured_warm_limit': 2,
              'readers_active': active, 'readers_completed': completed, 'after_shutdown': sample(),
              'account_isolation': 'Three distinct authenticated accounts returned only their admitted league.',
              'provider_calls': 0, 'fois_calculations': 0}
    result['passed'] = (active['warm'] == 4 and completed['warm'] <= 2
                        and completed['memory']['history_current_leagues'] <= 1
                        and result['after_shutdown']['history_current_leagues'] == 0
                        and not any(result['after_shutdown']['cgroup_memory_events'][key]
                                    for key in ('oom', 'oom_kill', 'oom_group_kill')))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.fixture_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='navigation-residency-', dir=args.fixture_root) as temporary:
        root = Path(temporary)
        for key in ('CACHE', 'PROJECTION_DB', 'METADATA_DB', 'INTELLIGENCE_CHECKPOINT', 'FOIS_DB', 'HISTORY_DB', 'ACCOUNT_DB'):
            os.environ['DTOS_' + key + '_FILE'] = str(root / (key.lower() + ('.json' if key == 'CACHE' else '.sqlite3')))
        os.environ.update(DTOS_DURABLE_HISTORY_REQUIRED='0', DTOS_HISTORY_STORAGE_ROOT=str(root),
                          DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root / 'season-cache'))
        result = asyncio.run(_exercise(root))
    result['temporary_residue'] = len(list(args.fixture_root.glob('navigation-residency-*')))
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in ('passed', 'configured_warm_limit', 'source_assets', 'temporary_residue')}))
    return 0 if result['passed'] and not result['temporary_residue'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
