"""Actual isolated authenticated rendered HTTP with real retained-source failures."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tests import test_source_evidence_presentation as sources
from tests import test_league_gm_diagnostics as fixtures
from tests.test_league_gm_integrity import without_consideration
from src.core.intelligence import roster_diagnostics
from tools.validation.browser_runtime import launch_chromium


class LeagueGMIntegrityBrowserTests(unittest.TestCase):
    def test_two_league_source_failures_and_consideration_are_readable_and_recover(self):
        captures = json.loads(Path('tests/fixtures/dynamic_league_settings.json').read_text())['leagues']
        measurements = []
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            cache = fixtures.SleeperSeasonCache(Path(folder))
            service = fixtures.LeagueGMObservations(cache)
            browser = launch_chromium(pw, headless=True)
            try:
                for index, capture in enumerate(captures):
                    f = sources.high_cardinality(200, capture)
                    try:
                        owner, data = f.f.f, f.data
                        league = data['league']['league_id']
                        data['transactions'] = []
                        data.pop('season_transactions', None)
                        player = fixtures.completed('player', adds={'a': 2}, drops={'a': 1})
                        reversed_player = {**deepcopy(player), 'roster_ids': [2, 1]}
                        faab = {**without_consideration('faab'), 'waiver_budget': [{'sender': 1, 'receiver': 2, 'amount': 12}]}
                        trades = [without_consideration(), faab] + ([player, reversed_player] if index == 0 else [])
                        expected = 3 if index == 0 else 2
                        def publish(year, rows):
                            facts = {'league': {'league_id': 'past-' + league + str(year), 'season': str(year), 'status': 'complete'},
                                     'rosters': [{'roster_id': t['roster_id'], 'owner_id': t.get('owner_id')} for t in data['teams']],
                                     'transactions': {str(w): rows if w == 1 else [] for w in range(19)}}
                            return cache.write(cache.normalize(league, year, facts))
                        publish(2024, trades)
                        broken = publish(2025, [fixtures.completed('corrupt')])
                        broken.write_bytes(broken.read_bytes()[:-8])
                        broken_hash = sha256(broken.read_bytes()).hexdigest()
                        with patch('src.core.gm_behavioral_intelligence.diagnostics.league_gm_observations', service), patch.object(roster_diagnostics, '_now', return_value=f.observed):
                            for width, height in ((320, 432), (320, 844), (375, 667), (390, 682), (390, 844), (1280, 900)):
                                page = owner.browser_page(browser, width, height)
                                errors = []
                                page.on('pageerror', lambda error: errors.append(str(error)))
                                try:
                                    for path in ('/league', '/teams/1', '/teams/2'):
                                        start = perf_counter()
                                        response = page.goto('https://dtos.test' + path)
                                        self.assertEqual(response.status, 200)
                                        section = page.locator('#league-observations' if path == '/league' else '[data-gm-franchise]')
                                        if path == '/league':
                                            self.assertIn('Consideration unavailable', section.inner_text())
                                        else:
                                            self.assertIn('incomplete', section.inner_text())
                                        self.assertIn('retained season source', section.inner_text())
                                        self.assertNotIn('acquiring 0 supported exact picks', section.inner_text())
                                        if path == '/league':
                                            self.assertIn(f'{expected} completed trades observed', section.inner_text())
                                            row = section.locator('.gm-row').first
                                            self.assertIsNone(row.get_attribute('open'))
                                            control = row.locator('summary').first
                                            closed = row.bounding_box()['height']
                                            control.scroll_into_view_if_needed()
                                            self.assertTrue(control.evaluate('(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'))
                                            control.focus()
                                            page.keyboard.press('Enter')
                                            self.assertIsNotNone(row.get_attribute('open'))
                                            summary_height = row.bounding_box()['height']
                                            row.locator('details summary').first.click()
                                            self.assertIn('retained source unavailable', row.inner_text())
                                            self.assertIn('Unavailable', row.inner_text())
                                            page.keyboard.press('Tab')
                                            self.assertGreater(float(page.locator(':focus').evaluate('e=>getComputedStyle(e).outlineWidth').replace('px', '')), 0)
                                            measurements.append({'league': league, 'width': width, 'height': height,
                                                'closed_row_height': closed, 'expanded_summary_height': summary_height,
                                                'fully_expanded_height': row.bounding_box()['height'],
                                                'route_ms': round((perf_counter() - start) * 1000, 2), 'completed_events': expected})
                                        if path == '/teams/2':
                                            self.assertEqual(page.locator('a[aria-label^="Shop "]').count(), 0)
                                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                        self.assertEqual(errors, [])
                                finally:
                                    page.close()
                            self.assertEqual(sha256(broken.read_bytes()).hexdigest(), broken_hash)
                            publish(2025, [fixtures.completed('recovered', adds={'a': 2}, drops={'a': 1})])
                            restored = owner.browser_page(browser, 390, 682)
                            try:
                                self.assertEqual(restored.goto('https://dtos.test/league').status, 200)
                                report = restored.locator('#league-observations')
                                self.assertIn(f'{expected + 1} completed trades observed', report.inner_text())
                                self.assertNotIn('retained source unavailable', report.inner_text())
                            finally:
                                restored.close()
                    finally:
                        f.doCleanups()
            finally:
                browser.close()
        output = os.environ.get('DTOS_GM_INTEGRITY_BROWSER_EVIDENCE')
        if output:
            Path(output).write_text(json.dumps(measurements, indent=2))
