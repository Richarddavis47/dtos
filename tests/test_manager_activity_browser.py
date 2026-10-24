"""Authenticated released-client evidence for manager/activity qualifications."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests.test_source_evidence_presentation import high_cardinality
from tests.test_manager_activity_integrity import manager_products, waiver
from tests.manager_evidence_fixtures import publish
from src.core.gm_behavioral_intelligence.diagnostics import LeagueGMObservations
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.intelligence import roster_diagnostics


class ManagerActivityBrowserTests(unittest.TestCase):
    def test_two_leagues_current_manager_waivers_trade_disclosures_and_keyboard(self):
        captures = json.loads(Path('tests/fixtures/dynamic_league_settings.json').read_text())['leagues']
        evidence = []
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for capture in captures:
                    f = high_cardinality(32, capture)
                    try:
                        data, owner = f.data, f.f.f
                        service = LeagueGMObservations(SleeperSeasonCache(Path(folder)/capture['league_id']))
                        data['teams'][1]['owner_id'] = 'now-b'
                        data['transactions'] = [waiver('claim', 'complete'), waiver('failed-a', 'failed'),
                            waiver('failed-b', 'failed'), waiver('pending', 'pending'),
                            waiver('cancelled', 'cancelled'), waiver('unknown', None)]
                        with patch('src.core.gm_behavioral_intelligence.diagnostics.league_gm_observations', service), \
                             patch.object(roster_diagnostics, '_now', return_value=f.observed):
                            manager_products(data, outgoing_kind='pick')
                            publish(data)
                            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                                with self.subTest(league=capture['league_id'], width=width):
                                    page = owner.browser_page(browser, width, height)
                                    errors = []
                                    page.on('pageerror', lambda e: errors.append(str(e)))
                                    try:
                                        response = page.goto('https://dtos.test/league')
                                        self.assertEqual(response.status, 200)
                                        section = page.locator('#league-observations')
                                        self.assertIn('1 completed waiver claims', section.inner_text())
                                        self.assertIn('2 failed', section.inner_text())
                                        self.assertIn('unknown-status waiver attempts', section.inner_text())
                                        row = section.locator('.gm-row').first
                                        summary = row.locator('summary').first
                                        summary.scroll_into_view_if_needed()
                                        page.keyboard.press('Tab')
                                        summary.focus()
                                        page.keyboard.press('Enter')
                                        self.assertIsNotNone(row.get_attribute('open'))
                                        self.assertGreater(float(summary.evaluate('e=>getComputedStyle(e).outlineWidth').replace('px','')), 0)
                                        self.assertTrue(summary.evaluate('(e)=>{let r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'))
                                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                        league_text = section.inner_text()
                                        page.goto('https://dtos.test/trades/create?front_office=1')
                                        page.locator('#trade-partner option[value="2"]').wait_for(state='attached')
                                        page.select_option('#trade-partner', '2')
                                        page.locator('#trade-strategy').locator('xpath=ancestor::details').evaluate_all('rows=>rows.forEach(e=>e.open=true)')
                                        page.select_option('#trade-strategy', 'REBUILD')
                                        for which, identity in (('sent', 'a'), ('received', '2028-R1-4')):
                                            control = page.locator(f'[data-side={which}]')
                                            if control.is_visible():
                                                control.click()
                                            page.locator(f'#trade-{which}-board button[data-asset-id="{identity}"]').click()
                                        page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                                        result = page.locator('#trade-result')
                                        detail = result.locator('details').filter(has=page.locator('summary', has_text='Why this partner?')).last
                                        detail.wait_for(state='attached')
                                        control = detail.locator('summary').first
                                        control.scroll_into_view_if_needed()
                                        control.focus()
                                        page.keyboard.press('Enter')
                                        self.assertIsNotNone(detail.get_attribute('open'))
                                        text = detail.inner_text()
                                        self.assertIn('Their principal cost:', text)
                                        self.assertIn('12 supported current-manager trade observations', text)
                                        self.assertIn('not establish', text)
                                        self.assertLess(text.index('Their principal cost:'), text.index('12 supported current-manager'))
                                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                        self.assertEqual(errors, [])
                                        measurement = {'league':capture['league_id'], 'width':width, 'height':height,
                                            'overflow':page.evaluate('document.documentElement.scrollWidth')-width,
                                            'league_text':league_text, 'partner_text':text, 'keyboard_disclosures':True, 'errors':errors}
                                        evidence.append(measurement)
                                        output = os.environ.get('DTOS_MANAGER_EVIDENCE')
                                        if output:
                                            target = Path(output)
                                            target.mkdir(parents=True, exist_ok=True)
                                            page.screenshot(path=str(target/f'partner-{capture["league_id"]}-{width}.png'))
                                    finally:
                                        page.close()
                    finally:
                        f.doCleanups()
            finally:
                browser.close()
        output = os.environ.get('DTOS_MANAGER_EVIDENCE')
        if output:
            (Path(output)/'browser-results.json').write_text(json.dumps(evidence,indent=2))
