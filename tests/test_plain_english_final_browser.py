"""Final explanation acceptance through disposable authenticated HTTP and Chromium.

Responsive Chromium is not physical Safari or unfamiliar-human acceptance.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from playwright.sync_api import sync_playwright
from routes.transactions import create_transactions_router
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from tests import test_roster_diagnostic_http as fixtures
from tools.validation.browser_runtime import launch_chromium


FORBIDDEN = ('Long-term scalar unavailable', 'No evidence-backed strength exceeds the v1 baseline',
             'No current evidence-backed weakness exceeds the v1 threshold', 'Consult canonical_evidence.schedule')
DOSSIER_FOLLOWUP_PHRASES = ('Weekly evidence is disclosed at its actual horizon',
                           'contextual v1 posture', 'No supported aggregate justifies a Buy/Sell posture.', 'Canonical Market:')
VIEWPORTS = ((320, 432), (375, 667), (390, 844), (1280, 900))


def capture_pages(folder=None):
    """Same producer/HTTP fixture supports archived baseline and candidate capture."""
    import dtos_app
    f = fixtures.DiagnosticHTTPTests()
    f.setUp()
    measurements = []
    try:
        f.publish(datetime.now(timezone.utc).isoformat())
        data = f.f.f.data
        data['league']['name'] = 'Harbor Dynasty'
        f.f.f.client.app.include_router(create_transactions_router(ensure_fresh=AsyncMock(),
            require_data=lambda:data, refresh_transactions=AsyncMock(), state={}, page=dtos_app.page))
        f.enterContext(patch.object(data_platform, 'warehouse', SnapshotWarehouse()))
        f.f.f.client.get('/teams/1')
        f.f.seed()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in VIEWPORTS:
                    for name, path, selector in (
                        ('dossier', '/players/a?front_office=1&from_team=1', '.ai-context'),
                        ('home', '/', '#home-opportunities'),
                        ('home-unselected', '/', '#home-opportunities'),
                        ('depth', '/teams/1#positional-depth', '#positional-depth'),
                        ('builder', '/trades/create?front_office=1', '#trade-context')):
                        page = f.f.browser_page(browser, width, height)
                        errors, requests, home_strategies = [], [], []
                        page.on('pageerror', lambda e: errors.append(str(e)))
                        page.on('request', lambda r: requests.append(r.url))
                        page.on('response', lambda r: home_strategies.append(r.json().get('strategy'))
                            if '/api/trades/home-opportunities?' in r.url else None)
                        try:
                            if name == 'home':
                                f.f.f.client.cookies.set('dtos_strategy', f.f.cookie)
                            if name == 'home-unselected':
                                page.context.clear_cookies(name='dtos_strategy')
                                f.f.f.client.cookies.delete('dtos_strategy')
                            response = page.goto('https://dtos.test' + path)
                            if response.status != 200:
                                raise AssertionError((name, response.status))
                            page.locator(selector).wait_for()
                            if name.startswith('home'):
                                page.locator('#home-opportunity-cards article').first.wait_for()
                            if name == 'builder':
                                page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
                            page.wait_for_load_state('networkidle')
                            if name == 'dossier':
                                disclosure = page.get_by_text('Valuation, fit and source evidence', exact=True)
                            elif name == 'depth':
                                disclosure = page.locator('#my-team-outlook-evidence > summary')
                            elif name.startswith('home'):
                                disclosure = page.locator('#home-brief-more > summary')
                            else:
                                disclosure = page.locator('#trade-source-context > summary')
                            keyboard, advanced_text = None, ''
                            if disclosure.count():
                                page.keyboard.press('Tab')
                                disclosure.focus()
                                keyboard = dict(focused=disclosure.evaluate('e=>e===document.activeElement'),
                                    outline=disclosure.evaluate('e=>getComputedStyle(e).outlineStyle'))
                                disclosure.press('Enter')
                                keyboard['opened'] = disclosure.evaluate('e=>e.parentElement.open')
                                advanced_text = disclosure.evaluate('e=>e.parentElement.innerText')
                                disclosure.press('Enter')
                                keyboard['closed'] = not disclosure.evaluate('e=>e.parentElement.open')
                            page.locator(selector).scroll_into_view_if_needed()
                            row = page.locator(selector).evaluate('''e=>({y:e.getBoundingClientRect().top,
                                width:e.getBoundingClientRect().width, overflow:document.documentElement.scrollWidth-innerWidth,
                                text:document.body.innerText})''')
                            if name == 'depth':
                                notes = page.locator('#depth-evidence-notes')
                                row['shared_depth_notes'] = notes.all_inner_texts()
                            row.update(name=name, advanced_text=advanced_text, home_strategy=home_strategies[-1] if home_strategies else None, viewport=dict(width=width,height=height),
                                path=path, keyboard=keyboard, errors=errors,
                                automatic_discovery_calls=sum('/api/trades/generate' in url for url in requests),
                                environment='Responsive Chromium; disposable authenticated producer/HTTP fixture')
                            if folder:
                                root = Path(folder)
                                root.mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(root / f'{name}-{width}.png'), full_page=True)
                                (root / f'{name}-{width}.json').write_text(json.dumps(row, indent=2))
                            if name == 'dossier':
                                page.get_by_role('link', name='← Back to My Team roster', exact=True).click()
                                row['return_path'] = page.url
                            measurements.append(row)
                        finally:
                            page.close()
            finally:
                browser.close()
    finally:
        f.doCleanups()
    return measurements


class FinalPlainEnglishBrowserTests(unittest.TestCase):
    def test_actual_four_surface_phone_keyboard_and_return_paths(self):
        output = os.environ.get('DTOS_FINAL_WORDING_EVIDENCE')
        if not output and os.environ.get('DTOS_PLAIN_ENGLISH_EVIDENCE'):
            output = str(Path(os.environ['DTOS_PLAIN_ENGLISH_EVIDENCE']) / 'final-v192')
        rows = capture_pages(output)
        self.assertEqual(len(rows), 20)
        for row in rows:
            with self.subTest(surface=row['name'],width=row['viewport']['width']):
                self.assertLessEqual(row['overflow'], 0)
                self.assertEqual(row['errors'], [])
                self.assertEqual(row['automatic_discovery_calls'], 0)
                for phrase in FORBIDDEN + (DOSSIER_FOLLOWUP_PHRASES if row['name'] == 'dossier' else ()):
                    self.assertNotIn(phrase, row['text'])
                    self.assertNotIn(phrase, row['advanced_text'])
                if row['keyboard']:
                    self.assertTrue(row['keyboard']['focused'])
                    self.assertNotEqual(row['keyboard']['outline'], 'none')
                    self.assertTrue(row['keyboard']['opened'])
                    self.assertTrue(row['keyboard']['closed'])
                if row['name'] == 'home':
                    self.assertEqual(row['home_strategy'], 'REBUILD')
                    self.assertIn('Rebuild fit:', row['text'])
                    self.assertNotIn('DTOS cannot determine whether to contend, retool or rebuild', row['text'])
                if row['name'] == 'home-unselected':
                    self.assertEqual(row['home_strategy'], '')
                    self.assertIn('DTOS cannot determine whether to contend, retool or rebuild', row['text'])
                    self.assertIn('Choose your goal', row['text'])
                if row['name'] == 'depth':
                    self.assertEqual(len(row['shared_depth_notes']), 1)
                    self.assertEqual(row['text'].count('This comparison is provisional:'), 1)
                    self.assertIn('QB · RB · WR · TE', row['shared_depth_notes'][0])
                if row['name'] == 'builder':
                    self.assertIn('Harbor Dynasty', row['text'])
                    self.assertNotIn('canonical Market totals', row['text'])
                if row['name'] == 'dossier':
                    self.assertIn('/teams/1#full-roster', row['return_path'])
