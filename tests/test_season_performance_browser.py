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
                        record_link = page.locator('.thq-header').get_by_role('link', name='Season results:')
                        self.assertEqual(record_link.count(), 1)
                        self.assertEqual(record_link.get_attribute('href'), '#season-so-far')
                        record_link.click()
                        self.assertTrue(page.url.endswith('#season-so-far'))
                        panel = page.locator('#season-so-far')
                        if not panel.evaluate('e=>e.open'):
                            panel.locator(':scope > summary').press('Enter')
                        self.assertTrue(panel.evaluate('e=>e.open'))
                        self.assertIn('0.00 points', panel.inner_text())
                        self.assertIn('Week 1: 0.00', panel.inner_text())
                        race = panel.get_by_text('Playoff race', exact=True)
                        race.press('Enter')
                        self.assertIn('Playoff position unavailable.', race.locator('..').inner_text())
                        self.assertEqual(race.locator('..').get_by_role('link', name='Review standings').get_attribute('href'),
                                         '/league#standings-evidence')
                        peer = panel.get_by_text('How often did we outscore the rest of the league?', exact=True)
                        peer.press('Enter')
                        detail = peer.locator('..')
                        self.assertIn('Wins: 0 · Losses: 0 · Ties: 1.', detail.inner_text())
                        self.assertIn('separate from your official record', detail.inner_text())
                        self.assertIn('1/1 completed regular-season weeks used.', detail.inner_text())
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                        panel.get_by_text('Weeks, coverage and sources', exact=True).focus()
                        panel.get_by_text('Weeks, coverage and sources', exact=True).press('Enter')
                        self.assertIn('native-fixture', panel.inner_text())
                        if root:
                            page.screenshot(path=str(root / f'team-expanded-{width}.png'), full_page=True)
                        page.goto('https://dtos.test/')
                        page.locator('.home-week details > summary').click()
                        link = page.get_by_role('link', name='Review season results')
                        self.assertEqual(link.count(), 1)
                        self.assertEqual(page.get_by_text('How often did we outscore', exact=False).count(), 0)
                        if root:
                            page.screenshot(path=str(root / f'home-{width}.png'), full_page=True)
                        link.click()
                        self.assertIn('/teams/1#season-so-far', page.url)
                    finally:
                        page.close()
            finally:
                browser.close()

    def test_missing_conflicting_and_retained_scores_on_real_routes(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        data = f.f.f.data
        league = data['league']
        league['settings']['num_teams'] = len(data['teams'])
        prepared = dict(league_id=str(league['league_id']), season=str(league['season']),
                        methodology=METHOD, calendar_reference=season_calendar(league)['reference'],
                        scoring_fingerprint=scoring_identity(league.get('scoring_settings') or {}),
                        semantic_generation='partial-native', observed_at='2026-11-01T12:00:00Z')
        data['season_matchups'] = prepared
        cases = [
            (dict(availability='available', rows=[]), '0/1', 'Unknown'),
            (dict(availability='available', rows=[dict(roster_id=1, points=3),
                                                  dict(roster_id=1, points=4)]), '0/1', 'Unknown'),
            (dict(availability='unavailable', retained_rows=[dict(roster_id=1, points=-2)]),
             '1/1', '-2.00'),
        ]
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = f.f.browser_page(browser, 390, 844)
                try:
                    for index, (row, coverage, points) in enumerate(cases):
                        # Mirror normal atomic publication, including the native source generation.
                        f.f.f.data = {**data, 'season_matchups': {**prepared,
                            'weeks': {'1': row}, 'semantic_generation': f'partial-native-{index}'}}
                        page.goto('https://dtos.test/teams/1')
                        panel = page.locator('#season-so-far')
                        if not panel.evaluate('e=>e.open'):
                            panel.locator(':scope > summary').press('Enter')
                        self.assertTrue(panel.evaluate('e=>e.open'))
                        if points == 'Unknown':
                            self.assertNotIn('0.00 points', panel.inner_text())
                        else:
                            self.assertIn(points, panel.inner_text())
                            self.assertIn('retained results', panel.inner_text())
                        self.assertIn('League comparison withheld', panel.inner_text())
                        panel.get_by_text('Weeks, coverage and sources', exact=True).click()
                        self.assertIn('partial-native', panel.inner_text())
                        page.goto('https://dtos.test/')
                        page.locator('.home-week details > summary').click()
                        lead = page.get_by_role('heading', name='Season so far').locator('..')
                        if points == 'Unknown':
                            self.assertNotIn('0.00 points', lead.inner_text())
                        else:
                            self.assertIn(points, lead.inner_text())
                            self.assertIn(coverage, lead.inner_text())
                            self.assertIn('retained results', lead.inner_text())
                finally:
                    page.close()
            finally:
                browser.close()

    def test_sleeper_rollover_prepares_completed_scores_on_both_pages(self):
        import asyncio
        from services.matchup_season import prepare_season_matchups, season_week_view

        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        stamp = datetime.now(timezone.utc).isoformat()
        f.publish(stamp)
        data = f.f.f.data
        league = {**data['league'], 'status': 'in_season', 'sport': 'nfl',
                  'settings': {**data['league']['settings'], 'start_week': 1, 'playoff_type': 0,
            'leg': 10, 'last_scored_leg': 10, 'playoff_week_start': 14,
            'playoff_teams': 6, 'playoff_round_type': 1, 'num_teams': len(data['teams'])}}
        nfl_state = {'season': league['season'], 'week': 11, 'season_type': 'regular'}
        source_scores = [181.48, 147.70, 188.16, 171.18, 212.78,
                         132.32, 171.58, 202.80, 176.02, 169.44]
        requests = []

        def rows(score):
            return [dict(roster_id=1, matchup_id=1, points=score),
                    dict(roster_id=2, matchup_id=1, points=0)]

        async def fetch(path):
            week = int(path.rsplit('/', 1)[-1])
            requests.append(week)
            return rows(source_scores[week - 1]) if week <= 10 else []

        # Replay build 2262's preparation call with only the league clock.
        legacy = asyncio.run(prepare_season_matchups(
            league, 11, rows(999), fetch, observed_at=stamp))
        self.assertEqual(list(legacy['weeks']), ['11'])
        self.assertEqual(requests, [])

        prepared = asyncio.run(prepare_season_matchups(
            league, 11, rows(999), fetch, observed_at=stamp, previous=legacy,
            nfl_state=nfl_state))
        self.assertEqual({week for week in requests if week <= 10}, set(range(1, 11)))
        self.assertEqual(len(requests), len(set(requests)))
        self.assertLessEqual(len(requests), 18)
        published = {**data, 'league': league, 'nfl_state': nfl_state, 'week': 11,
                     'season_matchups': prepared}
        matchup = season_week_view(published, 10, None)
        self.assertEqual(matchup['period'], 'historical')
        self.assertEqual(matchup['groups']['1'][0]['actual'], 169.44)
        f.f.f.data = published
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = f.f.browser_page(browser, 390, 844)
                page.goto('https://dtos.test/')
                page.locator('.home-week details > summary').click()
                home = page.get_by_role('heading', name='Season so far').locator('..')
                self.assertIn('175.35', home.inner_text())
                self.assertIn('10/10', home.inner_text())
                page.goto('https://dtos.test/teams/1')
                panel = page.locator('#season-so-far')
                if not panel.evaluate('e=>e.open'):
                    panel.locator(':scope > summary').press('Enter')
                for value in ('175.35', 'Week 8: 202.80', 'Week 9: 176.02', 'Week 10: 169.44'):
                    self.assertIn(value, panel.inner_text())
                self.assertNotIn('999.00', panel.inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                # Foreign NFL clock cannot establish the in-season rollover.
                f.f.f.data = {**published, 'nfl_state': {**nfl_state, 'season': '2025'},
                              'season_matchups': {**prepared, 'semantic_generation': 'foreign-clock'}}
                page.goto('https://dtos.test/')
                page.locator('.home-week details > summary').click()
                self.assertIn('Compatible season team results are not prepared.', home.inner_text())
                page.goto('https://dtos.test/teams/1')
                self.assertNotIn('175.35', panel.inner_text())
            finally:
                browser.close()
