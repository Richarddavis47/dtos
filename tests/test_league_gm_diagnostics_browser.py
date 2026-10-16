"""Codex-operated isolated authenticated Chromium; not Scout/physical Safari."""
import json
import os
import re
from pathlib import Path
from time import perf_counter
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_source_evidence_presentation as source_fixtures
from tests.test_league_gm_diagnostics import completed, LeagueGMObservations, SleeperSeasonCache
from src.core.intelligence import roster_diagnostics


class LeagueGMDiagnosticBrowserTests(unittest.TestCase):
    def test_actual_two_league_routes_disclosures_and_trade_scripts(self):
        captures = json.loads(Path('tests/fixtures/dynamic_league_settings.json').read_text())['leagues']
        results = []
        import tempfile
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            service = LeagueGMObservations(SleeperSeasonCache(Path(folder)))
            browser = launch_chromium(pw, headless=True)
            try:
                for league_index, capture in enumerate(captures):
                    f = source_fixtures.high_cardinality(200, capture)
                    try:
                        owner = f.f.f
                        data = f.data
                        owner.payload['workspace_context'] = owner.f.client.get('/api/trades/workspace?front_office=1').json()['workspace_context']
                        trade_count = 5 if league_index == 0 else 2
                        data['transactions'] = [completed(str(i), adds={'a': 2}, drops={'a': 1}) for i in range(trade_count)]
                        with patch('src.core.gm_behavioral_intelligence.diagnostics.league_gm_observations', service), patch.object(roster_diagnostics, '_now', return_value=f.observed):
                            for width, height in ((320, 432), (320, 844), (375, 667), (390, 682), (390, 844), (1280, 900)):
                                page = owner.browser_page(browser, width, height)
                                errors = []
                                page.on('pageerror', lambda error: errors.append(str(error)))
                                try:
                                    for path in ('/league', '/teams/2', '/trades/create'):
                                        started = perf_counter()
                                        response = page.goto('https://dtos.test' + path)
                                        self.assertEqual(response.status, 200)
                                        if path == '/league':
                                            section = page.locator('#league-observations')
                                            self.assertIn(f'{trade_count} completed trades observed', section.inner_text())
                                            self.assertIn('History is partial', section.inner_text())
                                            self.assertNotIn('Aggressive', section.inner_text())
                                            row = section.locator('.gm-row').first
                                            control = row.locator('summary').first
                                            self.assertIsNone(row.get_attribute('open'))
                                            control.scroll_into_view_if_needed()
                                            self.assertTrue(control.evaluate('(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'))
                                            control.focus()
                                            page.keyboard.press('Enter')
                                            self.assertIsNotNone(row.get_attribute('open'))
                                            self.assertIn('does not attribute these decisions to the current manager', row.inner_text())
                                            initial_summary = row.bounding_box()['height']
                                            evidence = row.locator('details').first
                                            evidence.locator('summary').click()
                                            self.assertEqual(evidence.locator('a[href^="/trades/history/"]').count(), trade_count)
                                            self.assertIn('Original consideration observed', evidence.inner_text())
                                            page.keyboard.press('Tab')
                                            self.assertGreater(float(page.locator(':focus').evaluate('e=>getComputedStyle(e).outlineWidth').replace('px', '')), 0)
                                            results.append(dict(league=capture['league_id'], width=width, height=height,
                                                route=path, route_ms=round((perf_counter()-started)*1000, 2),
                                                franchise_summary_height=initial_summary,
                                                source_trade_count=trade_count,
                                                expanded_franchise_height=row.bounding_box()['height']))
                                        elif path == '/teams/2':
                                            row = page.locator('[data-gm-franchise="2"]')
                                            self.assertIn(f'{trade_count} observed trades', row.inner_text())
                                            self.assertIn('current manager', row.inner_text())
                                        else:
                                            page.locator('#trade-sent-board input[type=search]').wait_for()
                                            evaluation = owner.evaluate()
                                            self.assertEqual(evaluation.status_code, 200, evaluation.text)
                                            self.assertIn('league_partner_context', evaluation.json()['evaluation']['dimensions'])
                                            # Execute the released renderer through normal Evaluate controls.
                                            page.locator('#trade-partner').select_option('2')
                                            for board, name in (('#trade-sent-board', 'My assets'), ('#trade-received-board', 'Their assets')):
                                                if width < 760:
                                                    page.get_by_role('button', name=name, exact=True).click()
                                                page.locator(board + ' button[data-asset-id]').first.click()
                                            page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                                            partner_control = page.locator('#trade-result summary').filter(has_text=re.compile('Why this partner|Previous partner context'))
                                            partner_control.wait_for()
                                            partner_control.click()
                                            self.assertIn('franchise', partner_control.locator('..').inner_text().lower())
                                            self.assertIn('franchise', page.locator('main').inner_text().lower())
                                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                        self.assertEqual(errors, [])
                                finally:
                                    page.close()
                    finally:
                        f.doCleanups()
            finally:
                browser.close()
        output = os.environ.get('DTOS_LEAGUE_GM_BROWSER_EVIDENCE')
        if output:
            Path(output).write_text(json.dumps(results, indent=2))
