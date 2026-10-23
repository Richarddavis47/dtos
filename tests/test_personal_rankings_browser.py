"""Disposable authenticated store → HTTP → rendered Chromium editor controls.

Responsive Chromium is not physical iPhone/Safari or unfamiliar-human evidence.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.personal_rankings import create_personal_rankings_router
from src.core.accounts import AccountService, AccountStore
from src.core.accounts.personal_store import load_personal
from src.platform.account_context import AccountContextMiddleware
from tools.validation.browser_runtime import launch_chromium


class PreparedMarketFixture:
    semantic_generation = 'fixture-canonical-market'

    def __init__(self, data):
        self.data = data
        self.rows = [{'asset_id': f'player:{index}', 'asset_type': 'player',
                      'position': ('QB', 'RB', 'WR', 'TE')[(index - 1) % 4],
                      'display_name': f'Player {index}', 'values': {'market_value': 1000 - index * 10}}
                     for index in range(1, 41)]
        self.rows.extend({'asset_id': f'pick:2028:1:{origin}', 'asset_type': 'pick',
                          'position': 'PICK', 'display_name': f'2028 Round 1 (Original franchise {origin})',
                          'values': {'market_value': 100 - origin * 10}}
                         for origin in (1, 2))

    def identity(self):
        return {'league_id': '100', 'market_generation': self.semantic_generation}

    def directory(self, *, offset, limit, **kwargs):
        return {'league_id': '100', 'market_generation': self.semantic_generation,
                'total': len(self.rows), 'assets': self.rows[offset:offset + limit]}


class PersonalEditorFixture:
    def __init__(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.folder.name) / 'accounts.sqlite3')
        self.service = AccountService(self.store)
        self.account_id, _ = self.service.create_account('manager', 'Manager', 'fixture-only password')
        self.store.link_sleeper(self.account_id, sleeper_user_id='fixture-user', username='manager', display_name='Manager')
        self.store.upsert_membership(self.account_id, {'league_id': '100', 'season': '2026', 'name': 'Fixture'},
                                     'fixture-user', 1, 'Your franchise', 'active')
        self.store.activate(self.account_id, '100')
        self.token, self.csrf = self.service.new_session(self.account_id)
        self.data = {'league': {'league_id': '100'}, 'market_data': {'generation': 'fixture-source'},
                     'teams': [{'roster_id': 1, 'players': [{'id': str(i)} for i in range(1, 21)],
                                'picks_owned': [{'season': 2028, 'round': 1, 'original_roster_id': 1, 'current_owner_id': 1}]},
                               {'roster_id': 2, 'players': [{'id': str(i)} for i in range(21, 41)],
                                'picks_owned': [{'season': 2028, 'round': 1, 'original_roster_id': 2, 'current_owner_id': 2}]}]}
        self.market = PreparedMarketFixture(self.data)
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=self.service, required=True)
        def page(title, body):
            return HTMLResponse('<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + title + '</title><style>body{margin:0;padding:12px;background:#141617;color:#f4f7f5;font:16px system-ui}a{color:#9beac2}button,input,select{background:#252b28;color:#f4f7f5;border:1px solid #77887e;border-radius:5px;padding:8px}a.btn{display:inline-flex;align-items:center;padding:8px;box-sizing:border-box;text-decoration:none}h2{font-size:1.5rem}.muted{color:#c2cdc7}button:disabled{opacity:.6}p{line-height:1.5}</style></head><body>' + body + '</body></html>')
        app.include_router(create_personal_rankings_router(service=self.service, require_data=lambda: self.data,
                           market_model=lambda: self.market, page=page))
        self.client = TestClient(app, base_url='https://dtos.test')
        self.client.cookies.set('dtos_session', self.token)

    def close(self):
        self.client.close()
        self.folder.cleanup()

    def browser_page(self, browser, width, height, *, touch=False):
        page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=touch)
        def transport(route):
            request = route.request
            parsed = urlsplit(request.url)
            if parsed.netloc != 'dtos.test':
                route.abort()
                return
            response = self.client.request(request.method, parsed.path + ('?' + parsed.query if parsed.query else ''),
                content=request.post_data, headers={key: value for key, value in request.headers.items()
                                                   if key in ('content-type', 'x-csrf-token', 'origin')})
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
        page.route('**/*', transport)
        return page


class PersonalRankingsEditorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = PersonalEditorFixture()
        self.addCleanup(self.f.close)

    def test_read_is_private_complete_and_does_not_create_preferences(self):
        response = self.f.client.get('/api/my-dtos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['cache-control'])
        result = response.json()
        self.assertEqual(len(result['rows']), 42)
        self.assertFalse(result['initialized'])
        self.assertEqual(result['heavy_work'], {'provider_calls': 0, 'discovery_calls': 0,
                         'solver_calls': 0, 'fois_calls': 0, 'history_calls': 0})
        self.assertIsNone(load_personal(self.f.store, self.f.account_id, '100', 1))

    def test_settled_reads_and_edits_do_not_start_heavy_work_or_grow_durable_data(self):
        targets = ('httpx.HTTPTransport.handle_request', 'httpx.AsyncHTTPTransport.handle_async_request',
                   'services.trade_intelligence.generate_trade_workflow',
                   'src.core.fois.service.FOISService.generate',
                   'src.core.trade_intelligence.lineup.optimal_legal_lineup',
                   'services.history.history_records',
                   'src.core.asset_market.engine.AssetMarketCache.get',
                   'src.core.asset_market.engine.AssetMarketCache.reconcile')
        with ExitStack() as stack:
            spies = {name: stack.enter_context(patch(name, side_effect=AssertionError('Unexpected heavy work: ' + name)))
                     for name in targets}
            initial = self.f.client.get('/api/my-dtos').json()
            response = self.f.client.post('/api/my-dtos', json={'command': 'initialize', 'expected_revision': 0,
                        'market_generation': initial['generation'], 'context': initial['context']},
                        headers={'x-csrf-token': self.f.csrf})
            self.assertEqual(response.status_code, 200, response.text)
            def logical_hash():
                with self.f.store.connect() as connection:
                    return hashlib.sha256('\n'.join(connection.iterdump()).encode()).hexdigest()
            before = logical_hash()
            for _ in range(10):
                self.assertEqual(self.f.client.get('/api/my-dtos').status_code, 200)
                self.assertEqual(self.f.client.get('/account/my-dtos').status_code, 200)
            self.assertEqual(logical_hash(), before)
            self.assertEqual({name: spy.call_count for name, spy in spies.items()}, {name: 0 for name in targets})
        out = os.getenv('DTOS_PERSONAL_BROWSER_EVIDENCE')
        if out:
            destination = Path(out)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'prepared-only-controls.json').write_text(json.dumps({
                'http_read_pairs': 10, 'heavy_entry_point_calls': {name: 0 for name in targets},
                'logical_database_sha256_before': before, 'logical_database_sha256_after': logical_hash(),
                'scope': 'Disposable authenticated router and canonical-service integration; prepared Market transport fixture'}, indent=2))

    def test_actual_http_commands_csrf_conflict_and_exact_picks(self):
        current = self.f.client.get('/api/my-dtos').json()
        def command(name, **values):
            return self.f.client.post('/api/my-dtos', json={'command': name, 'expected_revision': current['revision'],
                'market_generation': current['generation'], 'context': current['context'], **values},
                headers={'x-csrf-token': self.f.csrf})
        denied = self.f.client.post('/api/my-dtos', json={'command': 'initialize'})
        self.assertEqual(denied.status_code, 403)
        created = command('initialize')
        self.assertEqual(created.status_code, 200, created.text)
        stale = command('reorder', asset_id='player:2', to_position=1)
        self.assertEqual(stale.status_code, 409, stale.text)
        current = created.json()
        protected = command('preferences', asset_id='pick:2028:1:1', preferences={'protect': True})
        self.assertEqual(protected.status_code, 200, protected.text)
        current = protected.json()
        own = next(row for row in current['rows'] if row['asset_id'] == 'pick:2028:1:1')
        other = next(row for row in current['rows'] if row['asset_id'] == 'pick:2028:1:2')
        self.assertTrue(own['preferences']['protect'])
        self.assertFalse(other['preferences'].get('protect', False))
        foreign = self.f.client.post('/api/my-dtos', json={'command': 'mode'},
                   headers={'x-csrf-token': self.f.csrf, 'origin': 'https://foreign.invalid'})
        self.assertEqual(foreign.status_code, 403)

    def test_revoked_session_and_unsupported_commands_fail_without_writes(self):
        current = self.f.client.get('/api/my-dtos').json()
        response = self.f.client.post('/api/my-dtos', json={'command': 'unsupported', 'expected_revision': 0,
                 'market_generation': current['generation'], 'context': current['context']},
                 headers={'x-csrf-token': self.f.csrf})
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(load_personal(self.f.store, self.f.account_id, '100', 1))
        self.f.store.revoke_session(self.f.token)
        self.assertEqual(self.f.client.get('/api/my-dtos').status_code, 401)


class PersonalRankingsEditorBrowserTests(unittest.TestCase):
    def test_exact_pick_filter_move_and_saved_protection_are_independent_of_other_first(self):
        f = PersonalEditorFixture()
        self.addCleanup(f.close)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = f.browser_page(browser, 375, 667)
                page.goto('https://dtos.test/account/my-dtos')
                page.get_by_role('button', name='Create Custom Rankings', exact=True).click()
                page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed')==='true'")
                page.locator('#personal-position').select_option('PICK')
                self.assertEqual(page.locator('.personal-row').count(), 2)
                own = page.locator('[data-asset-id="pick:2028:1:1"]')
                self.assertEqual(own.get_attribute('data-overall-rank'), '41')
                own.get_by_label('Overall position for 2028 Round 1 (Original franchise 1)', exact=True).fill('3')
                own.get_by_role('button', name='Move 2028 Round 1 (Original franchise 1) to entered overall position', exact=True).click()
                page.wait_for_function("document.querySelector('[data-asset-id=\"pick:2028:1:1\"]').dataset.overallRank==='3'")
                own.get_by_label('Protect outgoing: 2028 Round 1 (Original franchise 1)', exact=True).check()
                page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.')")
                other = page.locator('[data-asset-id="pick:2028:1:2"]')
                self.assertTrue(other.get_by_label('Protect outgoing: 2028 Round 1 (Original franchise 2)', exact=True).is_disabled())
                saved = load_personal(f.store, f.account_id, '100', 1)
                self.assertEqual(saved['order'][2], 'pick:2028:1:1')
                self.assertTrue(saved['preferences']['pick:2028:1:1']['protect'])
                self.assertNotIn('pick:2028:1:2', saved['preferences'])
                page.close()
            finally:
                browser.close()

    def test_new_assets_and_source_failure_are_visible_without_rewriting_saved_order(self):
        f = PersonalEditorFixture()
        self.addCleanup(f.close)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = f.browser_page(browser, 320, 432)
                page.goto('https://dtos.test/account/my-dtos')
                page.get_by_role('button', name='Create Custom Rankings', exact=True).click()
                page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed')==='true'")
                baseline = load_personal(f.store, f.account_id, '100', 1)
                f.market.rows.append({'asset_id': 'player:41', 'asset_type': 'player', 'position': 'WR',
                                     'display_name': 'New Player 41', 'values': {'market_value': 5}})
                page.get_by_role('button', name='Reload rankings', exact=True).click()
                page.get_by_text('43 eligible ranked assets', exact=False).wait_for()
                page.locator('#personal-search').fill('New Player 41')
                self.assertIn('New eligible asset', page.locator('.personal-row').inner_text())
                self.assertIn('Personal Unavailable', page.locator('.personal-row').inner_text())
                self.assertTrue(page.locator('.personal-row .personal-drag').is_disabled())
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'], baseline['order'])
                f.market = None
                page.get_by_role('button', name='Reload rankings', exact=True).click()
                page.locator('#personal-error').wait_for(state='visible')
                self.assertIn('pending', page.locator('#personal-error').inner_text())
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['revision'], baseline['revision'])
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                page.close()
            finally:
                browser.close()

    def test_mouse_drag_and_emulated_touch_drag_update_saved_overall_order(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for touch in (False, True):
                    with self.subTest(emulated_touch=touch):
                        f = PersonalEditorFixture()
                        try:
                            page = f.browser_page(browser, 390 if touch else 1280, 844 if touch else 900, touch=touch)
                            page.goto('https://dtos.test/account/my-dtos')
                            page.get_by_role('button', name='Create Custom Rankings', exact=True).click()
                            page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed')==='true'")
                            first = page.locator('[data-asset-id="player:1"]')
                            page.evaluate("scrollTo(0,document.querySelector('[data-asset-id=\"player:1\"]').getBoundingClientRect().top+scrollY-80)")
                            handle = page.locator('[data-asset-id="player:2"] .personal-drag')
                            if touch:
                                source = handle.bounding_box()
                                target = first.bounding_box()
                                self.assertLess(source['y'] + source['height'] / 2, 844)
                                session = page.context.new_cdp_session(page)
                                x = source['x'] + source['width'] / 2
                                y = source['y'] + source['height'] / 2
                                destination = target['y'] + 70
                                session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
                                for step in range(1, 7):
                                    session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y + (destination - y) * step / 6}]})
                                session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                                session.detach()
                            else:
                                handle.drag_to(first)
                            page.wait_for_function("document.querySelector('.personal-row').dataset.assetId==='player:2'")
                            saved = load_personal(f.store, f.account_id, '100', 1)
                            self.assertEqual(saved['order'][:2], ['player:2', 'player:1'])
                            self.assertEqual(saved['revision'], 2)
                            page.close()
                        finally:
                            f.close()
            finally:
                browser.close()

    def test_full_editor_keyboard_reorder_filter_flags_restart_and_phone_geometry(self):
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    with self.subTest(width=width):
                        f = PersonalEditorFixture()
                        try:
                            page = f.browser_page(browser, width, height)
                            errors = []
                            page.on('pageerror', lambda exc: errors.append(str(exc)))
                            page.goto('https://dtos.test/account/my-dtos')
                            page.get_by_text('42 eligible ranked assets', exact=False).wait_for()
                            self.assertEqual(page.locator('.personal-row').count(), 25)
                            self.assertIsNone(load_personal(f.store, f.account_id, '100', 1))
                            initial_geometry = page.evaluate("""() => { const box = selector => {const r = document.querySelector(selector).getBoundingClientRect();return {top:r.top+scrollY,bottom:r.bottom+scrollY,height:r.height};};return {first_row:box('.personal-row'),first_title:box('.personal-row strong'),search:box('#personal-search'),mode:box('.personal-mode'),font_size:getComputedStyle(document.querySelector('#my-dtos')).fontSize};}""")
                            page.get_by_role('button', name='Create Custom Rankings', exact=True).click()
                            page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed') === 'true'")
                            page.keyboard.press('Tab')
                            up = page.get_by_role('button', name='Move Player 2 up one overall position', exact=True)
                            up.focus()
                            self.assertTrue(up.evaluate("e=>e===document.activeElement && e.matches(':focus-visible') && getComputedStyle(e).outlineStyle==='solid'"))
                            up.press('Enter')
                            page.wait_for_function("document.querySelector('.personal-row').dataset.assetId==='player:2'")
                            self.assertEqual(page.locator('[data-asset-id="player:2"] .personal-values').inner_text(), 'Market 980\nPersonal 990')
                            page.locator('#personal-position').select_option('QB')
                            self.assertEqual(page.locator('.personal-row').first.get_attribute('data-overall-rank'), '2')
                            self.assertIn('Player 1', page.locator('.personal-row').first.inner_text())
                            page.get_by_role('button', name='Move Player 5 up one overall position', exact=True).click()
                            page.wait_for_function("document.querySelector('[data-asset-id=\"player:5\"]').dataset.overallRank==='4'")
                            self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'][3:5], ['player:5', 'player:4'])
                            page.locator('#personal-position').select_option('')
                            page.locator('#personal-search').fill('Player 2')
                            self.assertGreater(page.locator('.personal-row').count(), 0)
                            page.locator('#personal-search').fill('')
                            target = page.get_by_label('Target acquisition: Player 2', exact=True)
                            target.check()
                            page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.')")
                            page.get_by_label('Start personal tier at Player 2', exact=True).check()
                            page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.')")
                            page.get_by_role('button', name='Neutral DTOS', exact=True).click()
                            page.wait_for_function("document.querySelector('#personal-neutral').getAttribute('aria-pressed') === 'true'")
                            self.assertEqual(page.locator('.personal-row').first.get_attribute('data-asset-id'), 'player:1')
                            page.get_by_role('button', name='Custom DTOS', exact=True).click()
                            page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed') === 'true'")
                            self.assertEqual(page.locator('.personal-row').first.get_attribute('data-asset-id'), 'player:2')
                            page.get_by_role('button', name='Restart Rankings', exact=True).click()
                            self.assertTrue(page.locator('#personal-restart-dialog').is_visible())
                            page.get_by_role('button', name='Keep my rankings', exact=True).click()
                            self.assertFalse(page.locator('#personal-restart-dialog').is_visible())
                            page.get_by_role('button', name='Restart Rankings', exact=True).click()
                            page.get_by_role('button', name='Replace with latest Market rankings', exact=True).click()
                            page.wait_for_function("document.querySelector('.personal-row').dataset.assetId==='player:1'")
                            self.assertTrue(page.get_by_label('Target acquisition: Player 2', exact=True).is_checked())
                            self.assertFalse(page.get_by_label('Start personal tier at Player 2', exact=True).is_checked())
                            self.assertFalse(errors, errors)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                            page.evaluate('scrollTo(0,0)')
                            custom_geometry = page.evaluate("""() => { const box = selector => {const r = document.querySelector(selector).getBoundingClientRect();return {top:r.top+scrollY,bottom:r.bottom+scrollY,height:r.height};};return {first_row:box('.personal-row'),first_title:box('.personal-row strong'),search:box('#personal-search'),mode:box('.personal-mode'),font_size:getComputedStyle(document.querySelector('#my-dtos')).fontSize};}""")
                            if width == 390:
                                self.assertLess(custom_geometry['first_title']['bottom'], height)
                            measurements.append({'width': width, 'height': height, 'rendered_rows': page.locator('.personal-row').count(),
                                                 'overflow': page.evaluate('document.documentElement.scrollWidth-innerWidth'),
                                                 'initial_neutral': initial_geometry, 'saved_custom': custom_geometry,
                                                 'errors': errors, 'kind': 'responsive Chromium; isolated authenticated fixture'})
                            out = os.getenv('DTOS_PERSONAL_BROWSER_EVIDENCE')
                            if out:
                                target_dir = Path(out)
                                target_dir.mkdir(parents=True, exist_ok=True)
                                page.evaluate('scrollTo(0,0)')
                                page.screenshot(path=str(target_dir / f'my-dtos-{width}.png'), full_page=True)
                                page.screenshot(path=str(target_dir / f'my-dtos-{width}-viewport.png'))
                            page.close()
                        finally:
                            f.close()
            finally:
                browser.close()
        if os.getenv('DTOS_PERSONAL_BROWSER_EVIDENCE'):
            (Path(os.environ['DTOS_PERSONAL_BROWSER_EVIDENCE']) / 'measurements.json').write_text(json.dumps(measurements, indent=2))
