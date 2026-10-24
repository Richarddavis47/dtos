"""Prepared league identity → authenticated Builder HTTP → rendered client."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock

from routes.trades import create_trades_router
from tests import test_trade_workspace_batch1 as boundary
from tests import test_trade_decision_http_browser as decisions


class BuilderPlainEnglishHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = boundary.AuthenticatedTradeBoundaryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.addCleanup(self.f.client.close)

    def test_supported_league_name_is_display_metadata_without_identity_changes(self):
        self.f.data['league']['name'] = 'Day Traders & Friends'
        before = deepcopy(self.f.data)
        payload = self.f.client.get('/api/trades/workspace?mode=calculator').json()
        self.assertEqual(payload['league_name'], 'Day Traders & Friends')
        self.assertEqual(payload['manager_context']['league_id'], 'league-1')
        self.assertEqual(self.f.data, before)
        self.assertEqual(self.f.client.get('/api/trades/workspace?mode=calculator').json(), payload)

    def test_missing_name_has_no_invented_label_or_identity_substitution(self):
        self.f.data['league'].pop('name', None)
        self.f.store.upsert_membership(self.f.account_id, {'league_id': 'league-1', 'season': '2026'},
            'fixture-user', 1, 'Team 1', 'active')
        payload = self.f.client.get('/api/trades/workspace?mode=calculator').json()
        self.assertEqual(payload['league_name'], '')
        self.assertEqual(payload['manager_context']['league_id'], 'league-1')

    def test_matching_prepared_membership_label_is_usable_when_source_name_missing(self):
        self.f.data['league'].pop('name', None)
        payload = self.f.client.get('/api/trades/workspace?mode=calculator').json()
        self.assertEqual(payload['league_name'], 'Fixture')
        self.assertEqual(payload['manager_context']['league_id'], 'league-1')

    def test_source_name_uses_same_pinned_snapshot_as_workspace_build(self):
        old = deepcopy(self.f.data)
        old['league']['name'] = 'Source A'
        new = deepcopy(old)
        new['league']['name'] = 'Source B'
        reads = Mock(side_effect=[old] + [new] * 1000)
        app = self.f.client.app
        app.router.routes.clear()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=reads,
            page=lambda title, body: body))
        payload = self.f.client.get('/api/trades/workspace?mode=calculator').json()
        self.assertEqual(payload['league_name'], 'Source A')
        self.assertEqual(payload['manager_context']['league_id'], old['league']['league_id'])


class BuilderPlainEnglishBrowserTests(unittest.TestCase):
    def test_actual_prepared_league_name_market_numbers_and_keyboard_details(self):
        f = decisions.DecisionHTTPBrowserTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            with self.subTest(width=width), f.browser(width, height) as page:
                f.data['league']['name'] = 'Day Traders & Friends <not markup>'
                f.ready(page)
                page.select_option('#trade-partner', '2')
                f.select(page, 'sent', 'a')
                f.select(page, 'received', 'c')
                self.assertIn('Active league · Day Traders & Friends <not markup>', page.locator('#trade-context').inner_text())
                self.assertNotIn('league-1', page.locator('#trade-context').inner_text())
                self.assertEqual(page.locator('#trade-context not').count(), 0)
                balance = page.locator('#trade-balance').inner_text()
                self.assertIn('Market comparison', balance)
                self.assertIn('You send: 611', balance)
                self.assertIn('You receive: 929', balance)
                self.assertIn('Value gap: 318 Market points', balance)
                self.assertNotIn('canonical', balance.lower())
                self.assertNotIn('canonical Market', page.locator('#trade-builder').inner_text())
                detail = page.locator('#trade-source-context')
                self.assertFalse(detail.evaluate('e=>e.open'))
                page.keyboard.press('Tab')
                summary = detail.locator('summary')
                summary.focus()
                self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                summary.press('Enter')
                self.assertTrue(detail.evaluate('e=>e.open'))
                self.assertIn('League ID: league-1', detail.inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                self.assertEqual(f.requests, [])
                output = os.environ.get('DTOS_BUILDER_WORDING_EVIDENCE')
                if output:
                    root = Path(output)
                    root.mkdir(parents=True, exist_ok=True)
                    detail.locator('summary').press('Enter')
                    page.locator('#trade-context').scroll_into_view_if_needed()
                    page.screenshot(path=str(root / f'builder-{width}.png'), full_page=True)
                    (root / f'builder-{width}.json').write_text(json.dumps(dict(
                        width=width, height=height, league=page.locator('#trade-context').inner_text(),
                        market=balance, overflow=page.evaluate('document.documentElement.scrollWidth-innerWidth'),
                        posts=f.requests, environment='Responsive Chromium; disposable authenticated HTTP fixture'), indent=2))
