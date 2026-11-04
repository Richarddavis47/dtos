"""Authenticated concurrent reads must release temporary runtime over-capacity."""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi import FastAPI, Request

from src.core.accounts import AccountService, AccountStore
from src.core.league_runtime import LeagueRuntimeManager, RuntimeState
from src.platform.account_context import AccountContextMiddleware
from src.platform.league_context import LeagueContextMiddleware


class NavigationResidencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_last_cancelled_cold_reader_cannot_leave_idle_overflow(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def hydrate(runtime):
            entered.set()
            await release.wait()
            return {'league': {'league_id': runtime.league_id, 'season': '2026'}}

        manager = LeagueRuntimeManager(max_warm=1, hydrator=hydrate)
        manager.attach_default('100', {'data': {'league': {'league_id': '100', 'season': '2026'}}}, warm=True)
        reader = asyncio.create_task(manager.acquire_request('200'))
        await entered.wait()
        for _ in range(5):
            reader.cancel()
            await asyncio.sleep(0)
            self.assertFalse(reader.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(reader, 2)
        self.assertEqual(manager.health()['warm_runtime_count'], 1)
        self.assertIsNone(manager.resident('200'))
        self.assertEqual(manager.resident('100').active_requests, 0)
        await manager.shutdown()

    async def test_cancelled_reader_cannot_cancel_shared_hydration(self):
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def hydrate(runtime):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {'league': {'league_id': runtime.league_id, 'season': '2026'}}

        manager = LeagueRuntimeManager(max_warm=1, hydrator=hydrate)
        first = asyncio.create_task(manager.get('200'))
        await entered.wait()
        second = asyncio.create_task(manager.acquire_request('200'))
        await asyncio.sleep(0)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        self.assertFalse(second.done())
        release.set()
        runtime = await asyncio.wait_for(second, 2)
        self.assertEqual(calls, 1)
        self.assertEqual(runtime.active_requests, 1)
        self.assertEqual(runtime.status, RuntimeState.WARM)
        await manager.release_request(runtime)
        self.assertEqual(runtime.active_requests, 0)
        await manager.shutdown()

    async def test_failed_hydration_releases_lease_and_allows_real_retry(self):
        calls = 0

        async def hydrate(runtime):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('controlled source failure')
            return {'league': {'league_id': runtime.league_id, 'season': '2026'}}

        manager = LeagueRuntimeManager(max_warm=1, hydrator=hydrate)
        with self.assertRaises(OSError):
            await manager.acquire_request('200')
        self.assertEqual(manager.resident('200').active_requests, 0)
        runtime = await manager.acquire_request('200')
        self.assertEqual(runtime.status, RuntimeState.WARM)
        self.assertEqual(runtime.active_requests, 1)
        await manager.release_request(runtime)
        await manager.shutdown()

    async def test_repeated_cancellation_drains_evicted_runtime_writer(self):
        async def hydrate(runtime):
            return {'league': {'league_id': runtime.league_id, 'season': '2026'}}

        manager = LeagueRuntimeManager(max_warm=1, hydrator=hydrate)
        old = await manager.acquire_request('200')
        current = await manager.acquire_request('300')
        entered, release = asyncio.Event(), asyncio.Event()
        finished = []

        async def writer():
            entered.set()
            await release.wait()
            finished.append(True)

        work = asyncio.create_task(writer())

        async def owner():
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                await asyncio.gather(work)
                raise

        owned = asyncio.create_task(owner())
        old.background_tasks.add(owned)
        await entered.wait()
        cleanup = asyncio.create_task(manager.release_request(old))
        while old.status is not RuntimeState.EVICTING:
            await asyncio.sleep(0)
        for _ in range(5):
            cleanup.cancel()
            await asyncio.sleep(0)
            self.assertFalse(cleanup.done())
            self.assertFalse(work.cancelled())
            self.assertEqual(current.state['data']['league']['league_id'], '300')
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await cleanup
        self.assertEqual(finished, [True])
        self.assertEqual(old.status, RuntimeState.CLOSED)
        self.assertEqual(old.state['data'], {})
        self.assertFalse(old.background_tasks)
        self.assertIs(manager.resident('300'), current)
        await manager.release_request(current)
        await manager.shutdown()

    async def test_quiescent_authenticated_reads_restore_existing_residency_bound(self):
        await self.concurrent_reads(sequential=True)

    async def test_simultaneous_cold_readers_keep_their_runtime_until_release(self):
        await self.concurrent_reads(sequential=False)

    async def concurrent_reads(self, *, sequential):
        with tempfile.TemporaryDirectory() as directory:
            store = AccountStore(Path(directory) / 'accounts.sqlite3')
            service = AccountService(store)
            tokens = {}
            for league in ('200', '300', '400'):
                account, _ = service.create_account('user' + league, 'Disposable manager', 'disposable account password')
                store.link_sleeper(account, sleeper_user_id='owner' + league, username='fixture', display_name='Fixture')
                store.upsert_membership(account, {'league_id': league, 'name': 'Fixture', 'season': '2026'},
                                        'owner' + league, 1, 'Fixture franchise', 'active')
                store.activate(account, league)
                tokens[league] = service.new_session(account)[0]

            async def hydrate(runtime):
                return {'league': {'league_id': runtime.league_id, 'season': '2026'}}

            manager = LeagueRuntimeManager(max_warm=2, hydrator=hydrate)
            manager.attach_default('100', {'data': {'league': {'league_id': '100', 'season': '2026'}}}, warm=True)
            app = FastAPI()
            app.add_middleware(LeagueContextMiddleware, manager=manager, default_league_id='100', import_enabled=False)
            app.add_middleware(AccountContextMiddleware, service=service, required=True)
            entered, release = {league: asyncio.Event() for league in tokens}, asyncio.Event()

            @app.get('/')
            async def home(request: Request):
                league = request.scope['dtos_authorized_league']
                entered[league].set()
                await release.wait()
                return {'league_id': league}

            tasks = []
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://testserver') as client:
                    for league, token in tokens.items():
                        tasks.append(asyncio.create_task(client.get('/', headers={'Cookie': 'dtos_session=' + token})))
                        if sequential:
                            await asyncio.wait_for(entered[league].wait(), 5)
                    if not sequential:
                        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered.values())), 5)
                    # Temporary excess is required while every nondefault runtime
                    # has a real active reader. Never evict an active request.
                    self.assertEqual(manager.health()['warm_runtime_count'], 4)
                    self.assertTrue(all(manager.resident(league).active_requests == 1 for league in tokens))
                    release.set()
                    responses = await asyncio.gather(*tasks)
                    self.assertTrue(all(row.status_code == 200 for row in responses))
                    self.assertEqual({row.json()['league_id'] for row in responses}, set(tokens))
                    self.assertTrue(all(runtime.active_requests == 0 for runtime in manager.resident_runtimes()))
                    self.assertLessEqual(manager.health()['warm_runtime_count'], 2,
                        'Completed navigation must not retain every temporarily protected runtime indefinitely.')
            finally:
                release.set()
                await asyncio.gather(*tasks, return_exceptions=True)
                await manager.shutdown()
