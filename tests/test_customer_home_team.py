"""Customer-facing Home/team disclosure over unchanged prepared evidence.

HTTP and Chromium cases use disposable accounts/publications; no owner live claim.
"""
from copy import deepcopy
from html.parser import HTMLParser
from types import SimpleNamespace
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient


class DisclosureText(HTMLParser):
    """Read the normal closed-disclosure presentation, including summaries."""
    def __init__(self, body):
        super().__init__()
        self.details = []
        self.summary = 0
        self.ignored = 0
        self.parts = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.ignored += 1
        if tag == 'details':
            self.details.append('open' in dict(attrs))
        elif tag == 'summary':
            self.summary += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.ignored -= 1
        if tag == 'details':
            self.details.pop()
        elif tag == 'summary':
            self.summary -= 1

    def handle_data(self, data):
        if not self.ignored and (not self.details or all(self.details)
                or (self.summary and all(self.details[:-1]))):
            self.parts.append(data)

    @property
    def text(self):
        return ' '.join(self.parts)


class CustomerTeamPresentationTests(unittest.TestCase):
    def test_owned_exact_picks_zero_missing_and_unknown_origin(self):
        from routes.teams import _draft_capital
        picks = [dict(season=2029, round=1, original_roster_id=rid,
                      current_owner_id=1, original_team=name, current_owner='Your team')
                 for rid, name in ((1, 'Your team'), (2, 'Other franchise'))]
        view = dict(team={'roster_id': 1, 'team_name': 'Your team'}, can_shop=True,
                    picks_by_year={2029: picks}, team_intelligence=SimpleNamespace(
                        future_capital_evidence={'picks': [
                            {'identity': {'year': 2029, 'round': 1, 'original_roster_id': 1},
                             'market': {'normalized_market_price': 0}},
                            {'identity': {'year': 2029, 'round': 1, 'original_roster_id': 2},
                             'market': {}}]}))
        before = deepcopy(view)
        html = _draft_capital(view)
        self.assertIn('Market value: 0', html)
        self.assertIn('Market price not available', html)
        self.assertIn('Your original pick', html)
        self.assertIn('Acquired pick', html)
        self.assertIn('2029 Round 1 · Other franchise', html)
        self.assertIn('asset_id=2029-R1-1', html)
        self.assertIn('asset_id=2029-R1-2', html)
        self.assertNotIn('Range: Unavailable', html)
        self.assertNotIn('Confidence: Unavailable', html)
        self.assertEqual(view, before)
        picks[1]['original_roster_id'] = None
        html = _draft_capital(view)
        self.assertIn('Original franchise unresolved', html)
        self.assertNotIn('asset_id=2029-R1-None', html)

    def test_depth_claim_and_uncertainty_are_short_with_original_details_retained(self):
        from routes.teams import _positional_depth
        facts = dict(starting_points=12.125, best_reserve_points=None, starting_count=1,
                     lineup_basis='optimal projected lineup', required_slots=1,
                     eligible_flex_slots=1, reserve_covered=0, reserve_expected=1,
                     availability='partial', diagnostic={'evidence': {
                         'calculation_supported': False, 'conclusion_state': 'unavailable'},
                         'interpretation': 'Surplus not established: exact missing reserve evidence.'})
        view = dict(overview={'positions': {'RB': facts}}, team={'players': []}, projection_snapshot={})
        before = deepcopy(view)
        html = _positional_depth(view)
        normal = DisclosureText(html).text
        self.assertIn('Backup projections:', normal)
        self.assertIn('0/1', normal)
        self.assertIn('missing evidence does not prove weak backups', normal)
        self.assertNotIn('Surplus not established', normal)
        self.assertIn('Surplus not established: exact missing reserve evidence.', html)
        self.assertIn('<summary>Replacement options and calculations</summary>', html)
        self.assertEqual(view, before)

    def test_existing_normalized_transaction_clock_is_not_lost(self):
        from src.ui.customer_experience import readable_time
        self.assertEqual(readable_time('2026-11-13 12:30 UTC'), 'Nov 13, 2026 · 12:30 UTC')

    def test_empty_home_does_not_turn_missing_rosters_into_weakness(self):
        from routes.home import create_home_router
        app = FastAPI()
        app.include_router(create_home_router(ensure_fresh=AsyncMock(),
            require_data=lambda: {'teams': [], 'league': {}}, page=lambda _, body: HTMLResponse(body)))
        with TestClient(app) as client:
            response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sleeper roster data is not ready', response.text)
        self.assertNotIn('weak', response.text.casefold())
        self.assertNotIn('No supported roster', response.text)


class CustomerHomeTeamHTTPTests(unittest.TestCase):
    def setUp(self):
        from tests.test_my_team_outlook_http import MyTeamOutlookHTTPTests
        self.f = MyTeamOutlookHTTPTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_normal_my_team_keeps_supported_comparison_without_internal_market_labels(self):
        response = self.f.client.get('/teams/1')
        self.assertEqual(response.status_code, 200)
        normal = DisclosureText(response.text).text
        self.assertIn('Your roster at a glance', normal)
        self.assertIn('slots', normal)
        self.assertIn('Market value:', normal)
        self.assertNotIn('Canonical Market', normal)
        self.assertNotIn('Range: Unavailable', normal)
        self.assertNotIn('Confidence: Unavailable', normal)
        self.assertIn('Calculations and sources', normal)
        self.assertIn('Historical FOIS grades are RETAINED / NOT REVALIDATED.', response.text)

    def test_directory_omits_unimplemented_forecasts_but_keeps_prepared_weekly_comparison(self):
        for team in self.f.data['teams']:
            team.update(wins=0, losses=0, ties=0)
        response = self.f.directory()
        self.assertEqual(response.status_code, 200)
        normal = DisclosureText(response.text).text
        self.assertIn('Preseason · official record not started', normal)
        self.assertIn('Week 2', normal)
        self.assertNotIn('Forecast unavailable', normal)
        self.assertNotIn('Playoff Odds', normal)
        self.assertNotIn('Championship Odds', normal)
        self.assertNotIn('Projected finish: Unavailable', normal)
        self.assertNotIn('<div class="rank-badge">Unavailable', response.text)

    def test_home_manager_grades_stay_secondary_and_retained_status_is_exact(self):
        from routes.home import create_home_router
        app = FastAPI()
        app.include_router(create_home_router(ensure_fresh=AsyncMock(), require_data=lambda: self.f.data,
            page=lambda _, body: HTMLResponse(body), generation_provider=lambda: self.id()))
        active = SimpleNamespace(fois_state='retained', runtime=SimpleNamespace(lifecycle={}))
        with patch('routes.home.current_league_context', return_value=active), TestClient(app) as client:
            response = client.get('/')
        self.assertEqual(response.status_code, 200)
        normal = DisclosureText(response.text).text
        self.assertIn('Your team', normal)
        self.assertIn('Manager-grade status', normal)
        self.assertNotIn('Current manager grades are unavailable', normal)
        self.assertIn('RETAINED / NOT REVALIDATED', response.text)
        self.assertIn('Projected lineup comparison', response.text)


class CustomerHomeFailureBrowserTests(unittest.TestCase):
    def test_capacity_deferral_and_failure_preserve_prior_results_without_false_completion(self):
        from datetime import datetime, timezone
        from playwright.sync_api import sync_playwright
        from tools.validation.browser_runtime import launch_chromium
        from tests.test_roster_diagnostic_http import DiagnosticHTTPTests
        f = DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        f.f.seed()
        self.assertEqual(f.f.f.client.get('/teams/1').status_code, 200)
        with sync_playwright() as pw:
            browser = launch_chromium(pw)
            try:
                for code, state in (('trade_capacity_deferred', 'capacity_deferred'), ('unexpected', 'failed')):
                    with self.subTest(state=state):
                        page = f.f.browser_page(browser, 390, 844)
                        calls = []
                        def refuse(route):
                            calls.append(route.request.url)
                            route.fulfill(status=503, content_type='application/json', body=json.dumps(
                                {'detail': {'code': code, 'message': 'source diagnostic', 'retry': 'explicit'}}))
                        page.route('**/api/trades/generate', refuse)
                        page.goto('https://dtos.test/')
                        page.locator('.home-opportunity').wait_for()
                        before = page.locator('.home-opportunity').count()
                        button = page.get_by_role('button', name='Find Trade Ideas', exact=True)
                        button.focus()
                        button.press('Enter')
                        page.wait_for_function("state => document.querySelector('#home-opportunities').dataset.state === state", arg=state)
                        status = page.locator('#home-opportunity-status').inner_text()
                        self.assertEqual(len(calls), 1)
                        self.assertEqual(page.locator('.home-opportunity').count(), before)
                        self.assertIn('Earlier results remain below', status)
                        self.assertIn('this search did not update them', status)
                        self.assertNotIn('source diagnostic', status)
                        self.assertTrue(button.is_enabled())
                        if state == 'capacity_deferred':
                            self.assertIn('waiting for capacity', status)
                            self.assertEqual(page.locator('#home-opportunities').get_attribute('data-presentation'), 'deferred')
                        else:
                            self.assertIn('did not finish', status)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth - innerWidth'), 0)
                        page.close()
            finally:
                browser.close()
