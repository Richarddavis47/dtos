"""Real Sleeper sync-thread publication versus the full-history ASGI handoff.

Only provider inputs and the post-commit preparation boundary are controlled.
The source assignment, sync thread, runtime lock and history child are real.
"""
import asyncio
from contextlib import ExitStack
import inspect
import json
import os
from pathlib import Path
import threading
from time import monotonic_ns
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

import httpx

from services import sleeper
from tests import test_fois_history_qualification as qualification


class SleeperHistoryPublicationTests(IsolatedAsyncioTestCase):
    asyncSetUp = qualification.HistoryQualificationTests.asyncSetUp
    asyncTearDown = qualification.HistoryQualificationTests.asyncTearDown

    def record(self, **fields):
        print('SLEEPER_PUBLICATION_CONTROL ' + json.dumps(fields, sort_keys=True), flush=True)
        destination = os.getenv('DTOS_SLEEPER_PUBLICATION_EVIDENCE')
        if destination:
            with Path(destination).open('a') as output:
                output.write(json.dumps(fields, sort_keys=True) + '\n')

    def source_worker(self, stack):
        """Stop real sync just after source installation, before hydration apply_data.

        The optional argument permits the same adversarial control on 2180.
        It is absent there; the actual released worker writes without a guard.
        """
        loop = asyncio.get_running_loop()
        prepared, installed, queued = asyncio.Event(), asyncio.Event(), asyncio.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        events = []

        async def get(_client, path):
            if path == '/league/A':
                return {'league_id': 'A', 'season': '2026', 'status': 'in_season',
                        'roster_positions': ['QB', 'BN'], 'scoring_settings': {'pass_td': 4},
                        'settings': {'leg': 1}}
            if path == '/state/nfl':
                return {'season': '2026', 'week': 1, 'season_type': 'regular'}
            return {} if path == '/players/nfl' else []

        def normalize(_):
            events.append(('worker_prepared_B', monotonic_ns()))
            loop.call_soon_threadsafe(prepared.set)

        def after_install(*_args, **_kwargs):
            events.append(('worker_installed_B', monotonic_ns()))
            loop.call_soon_threadsafe(installed.set)
            if not release.wait(10):
                raise AssertionError('Fixture post-publication barrier timed out')
            # Exercise the actual rollback path too, without unrelated compute.
            raise RuntimeError('Disposable post-publication preparation failure')

        stack.enter_context(patch.object(sleeper, 'sleeper_get', side_effect=get))
        stack.enter_context(patch.object(sleeper, 'refresh_public_market', return_value={'provider_status': {}}))
        stack.enter_context(patch.object(sleeper, 'player_history_evidence_batch', return_value={}))
        stack.enter_context(patch('src.core.valuation.normalization.prepare_market_normalization', side_effect=normalize))
        stack.enter_context(patch('src.core.intelligence.pick_context.prepare_pick_context', return_value=None))
        stack.enter_context(patch('src.core.history_context.canonical_history_store.update_current', side_effect=after_install))
        stack.enter_context(patch.object(sleeper, 'save_cache'))
        projections = Mock()
        projections.begin_external_refresh.return_value = False
        options = {'projections': projections}
        if 'publish_data' in inspect.signature(sleeper.sync_sleeper_league).parameters:
            options['publish_data'] = self.runtime.publish_source
        original = asyncio.run_coroutine_threadsafe

        def submitted(coroutine, owner):
            result = original(coroutine, owner)
            events.append(('worker_queued_commit', monotonic_ns()))
            owner.call_soon_threadsafe(queued.set)
            return result

        stack.enter_context(patch.object(asyncio, 'run_coroutine_threadsafe', side_effect=submitted))
        self.runtime.state['syncing'] = False
        worker = asyncio.create_task(sleeper.sync_sleeper_league('A', self.runtime.state, **options))
        return worker, prepared, installed, queued, release, events

    async def test_real_worker_cannot_replace_source_during_header_or_first_body(self):
        for suffix in ('/timeline', ''):
            for boundary in ('http.response.start', 'http.response.body'):
                with self.subTest(api=suffix or 'profile', boundary=boundary), ExitStack() as stack:
                    self.context.fois_state = 'ready'
                    self.runtime.state['data'] = {'league': {'league_id': 'A'}}
                    original_data = self.runtime.state['data']
                    entered, resume = asyncio.Event(), asyncio.Event()
                    first = True
                    published = []

                    async def app(scope, receive, send):
                        async def handoff(message):
                            nonlocal first
                            if message['type'] == boundary and first:
                                first = False
                                events_before = ('before_header' if boundary == 'http.response.start'
                                                 else 'before_first_body', monotonic_ns())
                                entered.set()
                                await resume.wait()
                                published.append({'source': 'A' if self.runtime.state['data'] is original_data else 'B',
                                                  'at': monotonic_ns(), 'boundary': events_before})
                            await send(message)
                        await self.app(scope, receive, handoff)

                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
                        request = asyncio.create_task(client.get('/api/fois/leagues/A/gms/gm' + suffix))
                        await asyncio.wait_for(entered.wait(), 10)
                        worker, prepared, installed, queued, release, events = self.source_worker(stack)
                        try:
                            await asyncio.wait_for(prepared.wait(), 10)
                            waiters = [asyncio.create_task(event.wait()) for event in (installed, queued)]
                            await asyncio.wait_for(asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED), 10)
                            for waiter in waiters:
                                waiter.cancel()
                            await asyncio.gather(*waiters, return_exceptions=True)
                            # Both possible producer boundaries are observed, rather than a timing sleep.
                            source_before_resume = 'A' if self.runtime.state['data'] is original_data else 'B'
                            resume.set()
                            response = await request
                            self.record(api=suffix or 'profile', boundary=boundary,
                                source_before_resume=source_before_resume, published=published,
                                evidence_state=response.json()['evidence_state'], events=events)
                            self.assertEqual(source_before_resume, 'A')
                            self.assertEqual(published[0]['source'], 'A')
                            self.assertEqual(response.json()['evidence_state'], 'current')
                            await asyncio.wait_for(installed.wait(), 10)
                            self.assertIsNot(self.runtime.state['data'], original_data)
                            self.assertEqual(self.context.fois_state, 'pending')
                        finally:
                            resume.set()
                            release.set()
                            await asyncio.gather(request, worker, return_exceptions=True)
                        self.assertIs(self.runtime.state['data'], original_data)
                        self.assertEqual(self.context.fois_state, 'pending')
                        self.assertFalse(self.runtime.fois_publication_lock.locked())

    async def test_real_worker_transition_before_final_qualification_is_retained(self):
        for suffix in ('/timeline', ''):
            with self.subTest(api=suffix or 'profile'), ExitStack() as stack:
                self.context.fois_state = 'ready'
                self.runtime.state['data'] = {'league': {'league_id': 'A'}}
                original = qualification.execution._stop
                changed = False

                async def transition(process):
                    nonlocal changed
                    await original(process)
                    if not changed:
                        changed = True
                        worker, _, installed, _, release, _ = self.source_worker(stack)
                        await asyncio.wait_for(installed.wait(), 10)
                        release.set()
                        await worker

                stack.enter_context(patch.object(qualification.execution, '_stop', side_effect=transition))
                response = await self.client.get('/api/fois/leagues/A/gms/gm' + suffix)
                self.assertEqual(response.status_code, 200, response.text)
                self.record(api=suffix or 'profile', boundary='before_qualification_with_rollback',
                            evidence_state=response.json()['evidence_state'], revision=self.runtime.fois_publication_revision)
                self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')

    async def test_source_commit_is_per_runtime_and_validates_ownership(self):
        from src.core.league_runtime import LeagueRuntime, LeagueRuntimeError
        other = LeagueRuntime('B')
        original = self.runtime.state['data']
        async with self.runtime.fois_publication_lock:
            blocked = asyncio.create_task(self.runtime.publish_source({'league': {'league_id': 'A'}}))
            await asyncio.wait_for(other.publish_source({'league': {'league_id': 'B'}}), 2)
            self.assertFalse(blocked.done())
            self.assertIs(self.runtime.state['data'], original)
        await asyncio.wait_for(blocked, 2)
        prior = self.runtime.state['data']
        revision = self.runtime.fois_publication_revision
        with self.assertRaises(LeagueRuntimeError):
            await self.runtime.publish_source({'league': {'league_id': 'B'}})
        self.assertIs(self.runtime.state['data'], prior)
        self.assertEqual(self.runtime.fois_publication_revision, revision)

    async def test_repeated_sync_cancellation_drains_real_blocked_publication(self):
        with ExitStack() as stack:
            await self.runtime.fois_publication_lock.acquire()
            worker, prepared, installed, queued, release, _ = self.source_worker(stack)
            try:
                await asyncio.wait_for(prepared.wait(), 10)
                await asyncio.wait_for(queued.wait(), 10)
                worker.cancel()
                await asyncio.sleep(0)
                worker.cancel()
                await asyncio.sleep(0)
                self.assertFalse(worker.done())
                self.assertFalse(installed.is_set())
            finally:
                self.runtime.fois_publication_lock.release()
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(worker, 10)
            self.assertTrue(installed.is_set())
            self.assertFalse(self.runtime.state['syncing'])
            self.assertFalse(self.runtime.fois_publication_lock.locked())

    async def test_default_and_selected_application_syncs_supply_the_owner(self):
        import dtos_app
        from unittest.mock import AsyncMock
        with patch.object(dtos_app, '_sync_sleeper', new_callable=AsyncMock) as sync:
            await dtos_app.sync_sleeper()
            self.assertIs(sync.call_args.kwargs['publish_data'].__self__, dtos_app.default_league_runtime)
        with patch.object(dtos_app, '_start_sleeper_sync') as start:
            dtos_app.start_sleeper_sync()
            self.assertIs(start.call_args.kwargs['publish_data'].__self__, dtos_app.default_league_runtime)
        with patch.object(dtos_app, 'sync_sleeper_league', new_callable=AsyncMock,
                          side_effect=RuntimeError('stop before source request')) as selected:
            with self.assertRaises(RuntimeError):
                await dtos_app._hydrate_league_runtime(self.runtime)
            self.assertIs(selected.call_args.kwargs['publish_data'].__self__, self.runtime)

    async def test_cold_default_recovery_passes_publication_to_tracked_worker(self):
        with patch.object(sleeper, 'STATE', {'data': {}}), patch.object(sleeper, 'start_sleeper_sync') as start:
            await sleeper.ensure_data_fresh(publish_data=self.runtime.publish_source)
            self.assertTrue(start.call_args.kwargs['force_players'])
            self.assertIs(start.call_args.kwargs['publish_data'].__self__, self.runtime)

    async def test_actual_transaction_refresh_cannot_mutate_source_during_prefix(self):
        import dtos_app
        for suffix in ('/timeline', ''):
            with self.subTest(api=suffix), ExitStack() as stack:
                entered, resume, acquired = asyncio.Event(), asyncio.Event(), asyncio.Event()
                self.runtime.state['data'] = {'league': {'league_id': 'A'}, 'transactions': []}
                old = self.runtime.state['data']
                self.context.fois_state = 'ready'
                self.context.state = self.runtime.state
                self.context.refresh_generations = lambda: self.runtime.source_generations.update(transactions='B')

                async def get(client, path):
                    acquired.set()
                    return [{'transaction_id': 'B', 'status': 'complete'}]

                stack.enter_context(patch.object(sleeper, 'sleeper_get', side_effect=get))
                stack.enter_context(patch('src.core.history_context.canonical_history_store.update_current'))
                stack.enter_context(patch('src.core.intelligence_memory.checkpoint_pipeline.ingest_transactions'))
                stack.enter_context(patch.object(sleeper, 'save_cache'))

                async def app(scope, receive, send):
                    first = True
                    async def handoff(message):
                        nonlocal first
                        if message['type'] == 'http.response.body' and first:
                            first = False
                            entered.set()
                            await resume.wait()
                        await send(message)
                    await self.app(scope, receive, handoff)

                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
                    request = asyncio.create_task(client.get('/api/fois/leagues/A/gms/gm' + suffix))
                    await asyncio.wait_for(entered.wait(), 10)
                    writer = asyncio.create_task(dtos_app.sync_current_transactions())
                    try:
                        await asyncio.wait_for(acquired.wait(), 10)
                        # The real producer has reached its first suspension
                        # after retrieval: publication or post-mutation work.
                        self.assertEqual(old['transactions'], [])
                        self.assertIs(self.runtime.state['data'], old)
                        resume.set()
                        response = await request
                        self.assertTrue(await writer)
                        self.assertEqual(response.json()['evidence_state'], 'current')
                        self.assertIs(self.runtime.state['data'], old)
                        self.assertEqual(old['transactions'][0]['transaction_id'], 'B')
                        self.assertEqual(self.context.fois_state, 'pending')
                    finally:
                        resume.set()
                        await asyncio.gather(request, writer, return_exceptions=True)

    async def test_transaction_source_advanced_during_fetch_is_not_overwritten(self):
        newer = {'league': {'league_id': 'A'}, 'roster_generation': 'newer'}
        self.runtime.state['data']['transactions'] = []
        prior = self.runtime.state['data']

        async def get(client, path):
            await self.runtime.publish_source(newer)
            return [{'transaction_id': 'late', 'status': 'complete'}]

        with patch.object(sleeper, 'sleeper_get', side_effect=get), \
                patch('src.core.history_context.canonical_history_store.update_current') as history, \
                patch.object(sleeper, 'save_cache') as save:
            result = await sleeper.sync_transactions(state=self.runtime.state, league_id='A',
                                                     publish_data=self.runtime.publish_transactions)
        self.assertFalse(result)
        self.assertIs(self.runtime.state['data'], newer)
        self.assertEqual(prior['transactions'], [])
        history.assert_not_called()
        save.assert_not_called()
