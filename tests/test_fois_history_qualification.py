"""Publication-time qualification of the actual full-history HTTP APIs."""
import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
import httpx

from routes.fois import _metadata, create_fois_router
from services.league_maintenance import ensure_fois_refresh
from src.core.fois import history_execution as execution
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.league_runtime import LeagueRuntime, RuntimeState
from src.platform.league_context import _CURRENT_CONTEXT


class HistoryQualificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.repo = FOISRepository(Path(self.folder.name) / 'fois.db')
        score = FOISEngine().evaluate(FOISFacts('A', 'A:1', 'gm',
            (SeasonResult(2025, 9, 5, 2, league_size=10),), gm_id='gm', tenure_id='A:gm'))
        self.score = replace(score, evidence_state='current')
        self.repo.save(self.score, 'source-A')
        self.runtime = LeagueRuntime('A', status=RuntimeState.WARM)
        self.runtime.state['data'] = {'league': {'league_id': 'A'}}
        self.runtime.source_generations = {'sleeper_canonical': 'A'}
        self.context = SimpleNamespace(runtime=self.runtime, league_id='A', fois_state='ready')
        self.runtime.canonical_context = self.context
        self.token = _CURRENT_CONTEXT.set(self.context)
        self.addCleanup(_CURRENT_CONTEXT.reset, self.token)
        self.app = FastAPI()
        self.app.include_router(create_fois_router(service=FOISService(self.repo), require_data=lambda: {}))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://fixture')
        self.addAsyncCleanup(self.client.aclose)
        self.refresh_release = asyncio.Event()

    async def asyncTearDown(self):
        self.refresh_release.set()
        await asyncio.gather(*tuple(self.runtime.background_tasks))
        self.assertEqual(execution.history_requests.active_count, 0)

    async def refresh(self):
        self.runtime.source_generations = {'sleeper_canonical': 'B'}
        entered = asyncio.Event()
        async def generate(_):
            entered.set()
            await self.refresh_release.wait()
            return ()
        ensure_fois_refresh(self.runtime, generate)
        await asyncio.wait_for(entered.wait(), 5)
        self.assertEqual(self.context.fois_state, 'pending')
        self.assertEqual(_metadata(self.score)['evidence_state'], 'retained_not_revalidated')

    async def test_same_context_refresh_cannot_publish_superseded_current_history(self):
        for suffix in ('/timeline', ''):
            with self.subTest(api=suffix or 'profile'):
                self.runtime.source_generations = {'sleeper_canonical': 'A'}
                self.context.fois_state = 'ready'
                self.refresh_release.clear()
                original = execution._stop
                changed = False
                async def pause_before_publication(process):
                    nonlocal changed
                    await original(process)
                    if not changed:
                        changed = True
                        await self.refresh()
                with patch.object(execution, '_stop', side_effect=pause_before_publication):
                    response = await self.client.get('/api/fois/leagues/A/gms/gm' + suffix)
                try:
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')
                finally:
                    self.refresh_release.set()
                    await asyncio.gather(*tuple(self.runtime.background_tasks))

    async def test_stable_and_previously_retained_qualifications_are_preserved(self):
        for state in ('ready', 'pending', 'unavailable', 'retained'):
            self.context.fois_state = state
            for suffix in ('/timeline', ''):
                response = await self.client.get('/api/fois/leagues/A/gms/gm' + suffix)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['evidence_state'],
                    'current' if state == 'ready' else 'retained_not_revalidated')
                self.assertEqual(int(response.headers['content-length']), len(response.content))

    async def test_generation_identity_and_aba_changes_cannot_revalidate_the_spool(self):
        for mode in ('generation-only', 'same-generation-refresh', 'aba', 'context-replacement'):
            with self.subTest(mode=mode):
                self.context.fois_state = 'ready'
                self.runtime.canonical_context = self.context
                self.runtime.source_generations = {'sleeper_canonical': 'A'}
                original = execution._stop
                changed = False
                async def transition(process):
                    nonlocal changed
                    await original(process)
                    if changed:
                        return
                    changed = True
                    if mode == 'generation-only':
                        async with self.runtime.fois_publication_lock:
                            self.runtime.source_generations = {'sleeper_canonical': 'B'}
                    elif mode == 'context-replacement':
                        async with self.runtime.fois_publication_lock:
                            self.runtime.canonical_context = SimpleNamespace(
                                runtime=self.runtime, league_id='A', fois_state='ready')
                    else:
                        entered = asyncio.Event()
                        async def generate(_):
                            entered.set()
                            return (self.score,)
                        ensure_fois_refresh(self.runtime, generate)
                        await entered.wait()
                        await asyncio.gather(*tuple(self.runtime.background_tasks))
                        self.assertEqual(self.context.fois_state, 'ready')
                        if mode == 'aba':
                            self.runtime.source_generations = {'sleeper_canonical': 'B'}
                            self.runtime.source_generations = {'sleeper_canonical': 'A'}
                with patch.object(execution, '_stop', side_effect=transition):
                    response = await self.client.get('/api/fois/leagues/A/gms/gm/timeline')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')

    async def test_lost_or_foreign_context_fails_before_successful_headers(self):
        for mode in ('closed', 'missing', 'foreign'):
            self.runtime.status = RuntimeState.WARM
            self.runtime.canonical_context = self.context
            original = execution._stop
            async def invalidate(process):
                await original(process)
                if mode == 'closed':
                    self.runtime.status = RuntimeState.CLOSED
                elif mode == 'missing':
                    self.runtime.canonical_context = None
                else:
                    self.runtime.canonical_context = SimpleNamespace(league_id='B', fois_state='ready')
            with patch.object(execution, '_stop', side_effect=invalidate):
                response = await self.client.get('/api/fois/leagues/A/gms/gm/timeline')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers['retry-after'], '5')
            self.assertNotIn('timeline', response.json())

    async def test_refresh_during_actual_child_reconstruction_and_serialization(self):
        import textwrap
        original = asyncio.create_subprocess_exec
        for stage in ('reconstruction', 'serialization'):
            for suffix in ('/timeline', ''):
                with self.subTest(stage=stage, api=suffix or 'profile'):
                    self.context.fois_state = 'ready'
                    self.runtime.source_generations = {'sleeper_canonical': 'A'}
                    self.refresh_release.clear()
                    marker = Path(self.folder.name) / 'child-entered'
                    release = Path(self.folder.name) / 'child-release'
                    marker.unlink(missing_ok=True)
                    release.unlink(missing_ok=True)
                    script = textwrap.dedent('''
                        import sys,json,time
                        from pathlib import Path
                        from src.core.fois.history_request_worker import produce
                        from src.core.fois.repository import FOISRepository
                        marker,release,stage=map(str,sys.argv[1:])
                        def barrier():
                            Path(marker).write_text('entered')
                            deadline=time.monotonic()+10
                            while not Path(release).exists():
                                if time.monotonic()>deadline:raise RuntimeError('Fixture barrier expired')
                                time.sleep(.005)
                        original=FOISRepository.iter_timeline
                        def history(self,*a,**kw):
                            if stage=='reconstruction':barrier()
                            yield from original(self,*a,**kw)
                        FOISRepository.iter_timeline=history
                        dumps=json.dumps
                        seen=False
                        def encode(value,*a,**kw):
                            global seen
                            if stage=='serialization' and isinstance(value,dict) and ('evaluation_kind' in value or 'profile' in value) and not seen:
                                seen=True;barrier()
                            return dumps(value,*a,**kw)
                        json.dumps=encode
                        raise SystemExit(produce(json.loads(sys.stdin.buffer.readline()),sys.stdout.buffer))
                    ''')
                    async def spawn(*args, **kwargs):
                        return await original(args[0], '-c', script, str(marker), str(release), stage, **kwargs)
                    with patch.object(asyncio, 'create_subprocess_exec', side_effect=spawn):
                        task = asyncio.create_task(self.client.get('/api/fois/leagues/A/gms/gm' + suffix))
                        try:
                            async with asyncio.timeout(10):
                                while not marker.exists():
                                    if task.done():
                                        self.fail(f'Child did not reach barrier: {task.result().status_code}')
                                    await asyncio.sleep(.005)
                            await self.refresh()
                        finally:
                            release.write_text('continue')
                        response = await task
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')
                    self.refresh_release.set()
                    await asyncio.gather(*tuple(self.runtime.background_tasks))

    async def test_second_transition_waits_until_successful_header_handoff(self):
        entered, release, refresh_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
        committed = []
        original_app = self.app
        async def app(scope, receive, send):
            async def guarded(message):
                if message['type'] == 'http.response.start' and message['status'] == 200:
                    self.assertTrue(self.runtime.fois_publication_lock.locked())
                    entered.set()
                    await release.wait()
                    committed.append((dict(self.runtime.source_generations), self.context.fois_state))
                await send(message)
            await original_app(scope, receive, guarded)
        async def refresh():
            refresh_entered.set()
            async with self.runtime.fois_publication_lock:
                self.runtime.source_generations = {'sleeper_canonical': 'B'}
            await self.refresh()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            task = asyncio.create_task(client.get('/api/fois/leagues/A/gms/gm/timeline'))
            await asyncio.wait_for(entered.wait(), 10)
            writer = asyncio.create_task(refresh())
            await refresh_entered.wait()
            await asyncio.sleep(0)
            self.assertFalse(writer.done())
            self.assertEqual(self.context.fois_state, 'ready')
            release.set()
            response = await task
            await writer
        self.assertEqual(committed, [({'sleeper_canonical': 'A'}, 'ready')])
        self.assertEqual(response.json()['evidence_state'], 'current')
        self.assertEqual(self.context.fois_state, 'pending')

    async def test_cancellation_during_refresh_releases_publication_and_admission(self):
        entered = asyncio.Event()
        original = execution._stop
        calls = 0
        async def stop(process):
            nonlocal calls
            await original(process)
            calls += 1
            if calls == 1:
                entered.set()
                await asyncio.Event().wait()
        with patch.object(execution, '_stop', side_effect=stop):
            task = asyncio.create_task(self.client.get('/api/fois/leagues/A/gms/gm/timeline'))
            await asyncio.wait_for(entered.wait(), 10)
            await self.refresh()
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(execution.history_requests.active_count, 0)
        self.assertFalse(self.runtime.fois_publication_lock.locked())
        response = await self.client.get('/api/fois/leagues/A/gms/gm/timeline')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')

    async def test_invalid_worker_envelope_is_retryable_without_partial_success(self):
        original = asyncio.create_subprocess_exec
        for body in ('malformed', '{}', '{"metadata":{},"evidence_state":"current","league_id":"B","gm_id":"gm"}'):
            async def spawn(*args, **kwargs):
                return await original(args[0], '-c', 'print(' + repr(body) + ')', **kwargs)
            with patch.object(asyncio, 'create_subprocess_exec', side_effect=spawn):
                response = await self.client.get('/api/fois/leagues/A/gms/gm/timeline')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(execution.history_requests.active_count, 0)
        self.assertEqual((await self.client.get('/api/fois/leagues/A/gms/gm/timeline')).status_code, 200)

    async def test_cancelled_header_handoff_releases_waiting_refresh_and_owned_worker(self):
        entered = asyncio.Event()
        original_app = self.app
        async def app(scope, receive, send):
            async def blocked(message):
                if message['type'] == 'http.response.start' and message['status'] == 200:
                    entered.set()
                    await asyncio.Event().wait()
                await send(message)
            await original_app(scope, receive, blocked)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            task = asyncio.create_task(client.get('/api/fois/leagues/A/gms/gm/timeline'))
            await asyncio.wait_for(entered.wait(), 10)
            refresh = asyncio.create_task(self.refresh())
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(refresh, 5)
        self.assertEqual(self.context.fois_state, 'pending')
        self.assertFalse(self.runtime.fois_publication_lock.locked())
        self.assertEqual(execution.history_requests.active_count, 0)

    async def test_worker_failure_retries_and_competing_contexts_cannot_overlap(self):
        original = asyncio.create_subprocess_exec
        async def fail(*args, **kwargs):
            return await original(args[0], '-c', 'raise SystemExit(5)', **kwargs)
        with patch.object(asyncio, 'create_subprocess_exec', side_effect=fail):
            response = await self.client.get('/api/fois/leagues/A/gms/gm/timeline')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(execution.history_requests.active_count, 0)
        started, release = asyncio.Event(), asyncio.Event()
        stop = execution._stop
        first = True
        async def pause(process):
            nonlocal first
            await stop(process)
            if first:
                first = False
                started.set()
                await release.wait()
        with patch.object(execution, '_stop', side_effect=pause):
            task = asyncio.create_task(self.client.get('/api/fois/leagues/A/gms/gm/timeline'))
            await asyncio.wait_for(started.wait(), 10)
            try:
                for league in ('A', 'B'):
                    other = await self.client.get(f'/api/fois/leagues/{league}/gms/gm/timeline')
                    self.assertEqual(other.status_code, 503)
            finally:
                release.set()
            self.assertEqual((await task).status_code, 200)
        self.assertEqual(execution.history_requests.active_count, 0)

    async def test_authenticated_refresh_preserves_account_and_league_boundaries(self):
        from src.core.accounts import AccountService, AccountStore
        from src.platform.account_context import AccountContextMiddleware, SESSION_COOKIE
        store = AccountStore(Path(self.folder.name) / 'accounts.db')
        service = AccountService(store)
        cookies = {}
        for account, league in (('one', 'A'), ('two', 'B')):
            store.create_account(account, account, 'Disposable', 'unusable-fixture-hash', [])
            store.link_sleeper(account, sleeper_user_id='gm-' + account,
                username='fixture', display_name='Fixture')
            store.upsert_membership(account, {'league_id': league, 'season': '2026'},
                'gm-' + account, 1, 'Fixture', 'active')
            store.activate(account, league)
            cookies[account] = service.new_session(account)[0]
        secured = AccountContextMiddleware(self.app, service=service, required=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=secured), base_url='http://fixture') as client:
            response = await client.get('/api/fois/leagues/A/gms/gm/timeline')
            self.assertEqual(response.status_code, 401)
            for suffix in ('/timeline', ''):
                self.context.fois_state = 'ready'
                self.runtime.source_generations = {'sleeper_canonical': 'A'}
                self.refresh_release.clear()
                original = execution._stop
                changed = False
                async def transition(process):
                    nonlocal changed
                    await original(process)
                    if not changed:
                        changed = True
                        await self.refresh()
                with patch.object(execution, '_stop', side_effect=transition):
                    response = await client.get('/api/fois/leagues/A/gms/gm' + suffix,
                        headers={'Cookie': SESSION_COOKIE + '=' + cookies['one']})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')
                foreign = await client.get('/api/fois/leagues/A/gms/gm' + suffix,
                    headers={'Cookie': SESSION_COOKIE + '=' + cookies['two']})
                self.assertEqual(foreign.status_code, 403)
                self.refresh_release.set()
                await asyncio.gather(*tuple(self.runtime.background_tasks))

    async def test_deferred_headers_are_protected_until_the_bounded_prefix_is_handed_off(self):
        entered, release, writer_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original_app = self.app
        async def app(scope, receive, send):
            first = True
            async def deferred(message):
                nonlocal first
                if message['type'] == 'http.response.body' and first:
                    first = False
                    entered.set()
                    await release.wait()
                    self.assertEqual(self.runtime.source_generations, {'sleeper_canonical': 'A'})
                    self.assertTrue(self.runtime.fois_publication_lock.locked())
                await send(message)
            await original_app(scope, receive, deferred)
        async def publish():
            writer_entered.set()
            async with self.runtime.fois_publication_lock:
                self.runtime.source_generations = {'sleeper_canonical': 'B'}
            await self.refresh()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            task = asyncio.create_task(client.get('/api/fois/leagues/A/gms/gm'))
            await asyncio.wait_for(entered.wait(), 10)
            writer = asyncio.create_task(publish())
            await writer_entered.wait()
            await asyncio.sleep(0)
            self.assertFalse(writer.done())
            release.set()
            response = await task
            await writer
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['evidence_state'], 'current')

    async def test_bulk_output_does_not_hold_the_qualification_lock(self):
        entered, release = asyncio.Event(), asyncio.Event()
        original_app = self.app
        async def app(scope, receive, send):
            bodies = 0
            async def blocked(message):
                nonlocal bodies
                if message['type'] == 'http.response.body':
                    bodies += 1
                    if bodies == 2:
                        entered.set()
                        await release.wait()
                await send(message)
            await original_app(scope, receive, blocked)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            task = asyncio.create_task(client.get('/api/fois/leagues/A/gms/gm/timeline'))
            await asyncio.wait_for(entered.wait(), 10)
            self.assertFalse(self.runtime.fois_publication_lock.locked())
            await asyncio.wait_for(self.refresh(), 5)
            self.assertEqual(execution.history_requests.active_count, 1)
            release.set()
            self.assertEqual((await task).status_code, 200)

    async def test_pending_admission_is_not_upgraded_by_a_later_successful_refresh(self):
        self.context.fois_state = 'pending'
        original = execution._stop
        changed = False
        async def complete(process):
            nonlocal changed
            await original(process)
            if not changed:
                changed = True
                async def generate(_):
                    return (self.score,)
                ensure_fois_refresh(self.runtime, generate)
                await asyncio.gather(*tuple(self.runtime.background_tasks))
        with patch.object(execution, '_stop', side_effect=complete):
            response = await self.client.get('/api/fois/leagues/A/gms/gm/timeline')
        self.assertEqual(self.context.fois_state, 'ready')
        self.assertEqual(response.json()['evidence_state'], 'retained_not_revalidated')
