"""Authenticated Home reads must not monopolize the HTTP event loop."""
import asyncio
from threading import Event, get_ident
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.responses import HTMLResponse
from httpx import ASGITransport, AsyncClient

from routes.api import create_api_router
from routes.home import create_home_router
from src.platform.account_context import current_account
from tests import test_trade_workspace_batch1 as boundary
import routes.home as home_routes


class HomeReadResponsivenessTests(unittest.TestCase):
    def test_blocked_prepared_home_keeps_real_liveness_and_account_scope(self):
        f = boundary.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        app, data = f.client.app, f.data
        app.include_router(create_home_router(
            ensure_fresh=AsyncMock(), require_data=lambda: data,
            page=lambda title, body: HTMLResponse(body),
            generation_provider=lambda: (self.id(), data['league']['league_id'], id(data)),
        ))
        app.include_router(create_api_router(
            ensure_fresh=AsyncMock(), require_data=lambda: data,
            sync_sleeper=AsyncMock(), state={'data': data}, league_id='league-1',
        ))
        original = home_routes.capture_news_data

        async def exercise(league):
            entered, resume = Event(), Event()
            event_loop_thread = get_ident()
            observed = []

            def capture(source):
                context = current_account()
                observed.append((get_ident(), context.account_id,
                                 context.membership.league_id))
                entered.set()
                # The pre-fix loop path remains finite, so this regression fails
                # explicitly instead of deadlocking the test runner.
                if get_ident() != event_loop_thread:
                    if not resume.wait(5):
                        raise AssertionError('Home test barrier was not released')
                return original(source)

            async with AsyncClient(transport=ASGITransport(app=app),
                                   base_url='http://testserver',
                                   cookies=f.client.cookies) as client:
                with patch.object(home_routes, 'capture_news_data', capture):
                    pending = asyncio.create_task(client.get('/'))
                    try:
                        self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                        self.assertNotEqual(observed[0][0], event_loop_thread,
                                            'Prepared Home work blocked the event loop')
                        self.assertEqual(observed[0][1:], (f.account_id, league))
                        response = await client.get('/health/live')
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()['status'], 'alive')
                        self.assertFalse(pending.done(),
                                         'Health must finish while Home is still blocked')
                    finally:
                        resume.set()
                        response = await pending
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('Open My Team', response.text)
                    self.assertIn('Team 1', response.text)

        asyncio.run(exercise('league-1'))
        f.store.upsert_membership(f.account_id,
            {'league_id': 'league-2', 'season': '2026', 'name': 'Separate'},
            'fixture-user', 1, 'Separate Franchise', 'active')
        f.store.activate(f.account_id, 'league-2')
        data['league']['league_id'] = 'league-2'
        asyncio.run(exercise('league-2'))
