"""Rendered prepared-source checks; Chromium fixtures, not owner-live acceptance."""
from datetime import datetime, timezone
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_roster_diagnostic_http as fixtures
from services.matchup_season import METHOD
from src.core.intelligence.season_calendar import season_calendar
from src.core.player_value_projection.sleeper_actuals import scoring_identity


class SeasonPerformanceBrowserTests(unittest.TestCase):
    def test_team_home_results_disclosure_and_return(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        data = f.f.f.data
        league = data['league']
        calendar = season_calendar(league)
        self.assertEqual(calendar['availability'], 'supported')
        league['settings']['num_teams'] = len(data['teams'])
        data['season_matchups'] = dict(league_id=str(league['league_id']),
            season=str(league['season']), methodology=METHOD,
            scoring_fingerprint=scoring_identity(league.get('scoring_settings') or {}),
            calendar_reference=season_calendar(league)['reference'], semantic_generation='native-fixture',
            observed_at='2026-11-01T12:00:00Z', weeks={'1': dict(availability='available',
                rows=[dict(roster_id=t['roster_id'], points=0) for t in data['teams']])})
        root = Path(os.environ['DTOS_SEASON_EVIDENCE']) if os.environ.get('DTOS_SEASON_EVIDENCE') else None
        if root:
            root.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    page = f.f.browser_page(browser, width, height)
                    try:
                        page.goto('https://dtos.test/teams/1')
                        panel = page.locator('#season-so-far')
                        self.assertIn('0.00 points', panel.inner_text())
                        self.assertIn('Week 1: 0.00', panel.inner_text())
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                        panel.locator('summary').focus()
                        panel.locator('summary').press('Enter')
                        self.assertIn('native-fixture', panel.inner_text())
                        if root:
                            page.screenshot(path=str(root / f'team-expanded-{width}.png'), full_page=True)
                        page.goto('https://dtos.test/')
                        link = page.get_by_role('link', name='Review season results')
                        self.assertEqual(link.count(), 1)
                        if root:
                            page.screenshot(path=str(root / f'home-{width}.png'), full_page=True)
                        link.click()
                        self.assertIn('/teams/1#season-so-far', page.url)
                    finally:
                        page.close()
            finally:
                browser.close()
