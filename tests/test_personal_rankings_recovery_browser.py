"""Named compatibility blockers and deliberate recovery through real private APIs.

Disposable authenticated stores, prepared Market transport and responsive
Chromium are author controls, not live-account, Safari or human acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
import unittest

from playwright.sync_api import sync_playwright

from src.core.accounts.personal_store import load_personal
from tests import test_personal_rankings_browser as editor_fixtures
from tests import test_personal_trade_browser as trade_fixtures
from tools.validation.browser_runtime import launch_chromium


VIEWPORTS = ((320, 432), (375, 667), (390, 844), (1280, 900))


class PersonalRankingsRecoveryBrowserTests(unittest.TestCase):
    def test_priced_inactive_asset_survives_read_retry_and_keeps_playing_qualification(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in VIEWPORTS:
                    with self.subTest(width=width):
                        fixture = self.fixture()
                        before = self.saved(fixture)
                        fixture.market.rows[1]['status'] = 'Inactive'
                        page = fixture.browser_page(browser, width, height)
                        page.goto('https://dtos.test/account/my-dtos')
                        self.loaded(page)
                        row = page.locator('[data-asset-id="player:2"]')
                        self.assertIn('not confirmation', row.inner_text())
                        self.assertNotIn('Personal values need review', row.inner_text())
                        self.assertTrue(fixture.client.get('/api/my-dtos').json()['personal_available'])
                        settings = page.locator('#personal-settings > summary')
                        self.keyboard_focus(settings)
                        settings.press('Enter')
                        self.assertTrue(page.locator('#personal-settings').evaluate('e=>e.open'))
                        retry = page.get_by_role('button', name='Reload rankings', exact=True)
                        self.keyboard_focus(retry)
                        with page.expect_response(lambda r: '/api/my-dtos' in r.url and r.request.method == 'GET'):
                            retry.press('Enter')
                        self.loaded(page)
                        self.assertIn('not confirmation', row.inner_text())
                        self.assertEqual(self.saved(fixture), before)
                        self.evidence('priced-inactive', page, fixture.client.get('/api/my-dtos').json(), width, height,
                                      {'saved_order_tiers_preferences_and_revision_unchanged': True})
                        page.close()
            finally:
                browser.close()

    def command(self, fixture, command, **fields):
        state = fixture.client.get('/api/my-dtos').json()
        response = fixture.client.post('/api/my-dtos', json={
            'command': command, 'expected_revision': state['revision'],
            'market_generation': state['generation'], 'context': state['context'], **fields},
            headers={'x-csrf-token': fixture.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def fixture(self):
        fixture = editor_fixtures.PersonalEditorFixture()
        self.addCleanup(fixture.close)
        self.command(fixture, 'initialize')
        self.command(fixture, 'reorder', asset_id='player:3', to_position=1)
        self.command(fixture, 'tiers', asset_id='player:3', tier_start=True)
        self.command(fixture, 'tiers', asset_id='player:2', tier_start=True)
        self.command(fixture, 'preferences', asset_id='player:2', preferences={'protect': True})
        self.command(fixture, 'preferences', asset_id='player:3', preferences={'target': True})
        return fixture

    @staticmethod
    def saved(fixture):
        return load_personal(fixture.store, fixture.account_id, '100', 1)

    @staticmethod
    def loaded(page):
        page.wait_for_function("document.querySelector('#my-dtos').getAttribute('aria-busy')==='false' && !document.querySelector('#personal-custom').disabled")

    def keyboard_focus(self, locator):
        locator.focus()
        locator.page.keyboard.press('Tab')
        locator.page.keyboard.press('Shift+Tab')
        self.assertTrue(locator.evaluate("e=>e===document.activeElement && e.matches(':focus-visible') && getComputedStyle(e).outlineStyle==='solid' && parseFloat(getComputedStyle(e).outlineWidth)>0"))

    def evidence(self, name, page, state, width, height, extra=None):
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
        destination = os.getenv('DTOS_PERSONAL_RECOVERY_EVIDENCE')
        if not destination:
            return
        out = Path(destination)
        out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out / f'{name}-{width}.png'), full_page=True)
        # Deliberately omit account/session/CSRF identity and raw API documents.
        result = {key: state.get(key) for key in (
            'initialized', 'revision', 'mode', 'personal_available', 'eligible_asset_count',
            'saved_asset_count', 'compatibility_issues', 'limitations', 'heavy_work')}
        result.update({'width': width, 'height': height, 'overflow': 0,
            'collected_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'environment': 'Author-run responsive Chromium; authenticated disposable account and prepared transport',
            'browser_version': page.context.browser.version,
            'source_hashes': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
                'services/personal_rankings.py', 'routes/personal_rankings.py',
                'static/js/personal_rankings.js', 'static/css/personal_rankings.css')},
            'geometry': page.evaluate('''() => Object.fromEntries(
                ['personal-warnings','personal-compatibility-summary','personal-remove-dialog','personal-remove-confirm']
                .map(id => {const e=document.getElementById(id),r=e.getBoundingClientRect();
                    return [id,{top:r.top+scrollY,left:r.left,width:r.width,height:r.height,
                        visible:Boolean(e.getClientRects().length)}]}))'''),
            **(extra or {})})
        (out / f'{name}-{width}.json').write_text(json.dumps(result, indent=2))

    def test_named_blocker_keyboard_pointer_recovery_preserves_saved_work_all_widths(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in VIEWPORTS:
                    with self.subTest(width=width):
                        fixture = self.fixture()
                        before = self.saved(fixture)
                        fixture.market.rows[1]['values']['market_value'] = None
                        page = fixture.browser_page(browser, width, height)
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto('https://dtos.test/account/my-dtos')
                        self.loaded(page)
                        state = fixture.client.get('/api/my-dtos').json()
                        self.assertFalse(state['personal_available'])
                        self.assertEqual(state['compatibility_issues'][0]['asset_id'], 'player:2')
                        self.assertEqual(state['compatibility_issues'][0]['code'], 'market_price_missing')
                        blocked = next(row for row in state['rows'] if row['asset_id'] == 'player:2')
                        self.assertTrue(blocked['owned'])
                        self.assertTrue(blocked['preferences']['protect'])
                        summary = page.locator('#personal-compatibility-summary')
                        self.assertIn('Player 2', summary.inner_text())
                        self.keyboard_focus(summary)
                        page.keyboard.press('Enter')
                        self.assertTrue(page.locator('#personal-compatibility').evaluate('e=>e.open'))
                        issue = page.locator('#personal-compatibility-issues > li').first
                        self.assertIn('Missing pricing is not a zero value', issue.inner_text())
                        exact = issue.locator('summary')
                        exact.focus()
                        page.keyboard.press('Enter')
                        self.assertIn('player:2', issue.inner_text())
                        remove = issue.get_by_role('button', name='Review removing Player 2 from Custom ordering', exact=True)
                        self.keyboard_focus(remove)
                        page.keyboard.press('Enter')
                        self.assertTrue(page.locator('#personal-remove-dialog').is_visible())
                        self.assertEqual(page.evaluate('document.activeElement.id'), 'personal-remove-cancel')
                        self.assertIn('Target/Avoid/Protect choices stay saved', page.locator('#personal-remove-dialog').inner_text())
                        self.assertEqual(self.saved(fixture), before)
                        page.keyboard.press('Escape')
                        page.wait_for_function("!document.querySelector('#personal-remove-dialog').open")
                        self.assertEqual(page.evaluate('document.activeElement.dataset.removeAsset'), 'player:2')
                        self.assertEqual(self.saved(fixture), before)
                        self.evidence('blocked-review', page, state, width, height,
                                      {'keyboard_disclosure': True, 'escape_returns_exact_trigger': True})
                        # Pointer opens the same dialog; confirmation is keyboard-operable.
                        remove.click()
                        confirm = page.locator('#personal-remove-confirm')
                        self.keyboard_focus(confirm)
                        confirm_box = confirm.bounding_box()
                        self.assertGreaterEqual(confirm_box['x'], 0)
                        self.assertLessEqual(confirm_box['x'] + confirm_box['width'], width)
                        self.assertGreaterEqual(confirm_box['y'], 0)
                        self.assertLessEqual(confirm_box['y'] + confirm_box['height'], height)
                        self.assertTrue(confirm.evaluate('''e=>{const r=e.getBoundingClientRect();
                            const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
                            return hit===e||e.contains(hit)}'''))
                        self.evidence('removal-confirmation', page, state, width, height,
                                      {'confirm_visible_and_pointer_reachable': True})
                        page.keyboard.press('Enter')
                        page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.')")
                        self.loaded(page)
                        after = self.saved(fixture)
                        self.assertEqual(after['revision'], before['revision'] + 1)
                        self.assertEqual(after['order'], [key for key in before['order'] if key != 'player:2'])
                        self.assertEqual(after['tiers'], ['player:3'])
                        self.assertEqual(after['preferences'], before['preferences'])
                        self.assertEqual(after['baseline']['generation'], before['baseline']['generation'])
                        self.assertEqual(after['baseline']['ids'], [key for key in before['baseline']['ids'] if key != 'player:2'])
                        state = fixture.client.get('/api/my-dtos').json()
                        self.assertTrue(state['personal_available'])
                        self.assertEqual(state['compatibility_issues'], [])
                        self.assertTrue(page.locator('#personal-compatibility').is_hidden())
                        self.assertEqual(page.evaluate('document.activeElement.id'), 'personal-status')
                        self.assertFalse(errors, errors)
                        self.evidence('recovered', page, state, width, height,
                                      {'other_order_tiers_flags_preserved': True, 'explicit_revision_increment': 1})
                        page.get_by_role('button', name='Neutral DTOS', exact=True).click()
                        page.wait_for_function("document.querySelector('#personal-neutral').getAttribute('aria-pressed')==='true'")
                        page.get_by_role('button', name='Custom DTOS', exact=True).click()
                        page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed')==='true'")
                        self.assertEqual(self.saved(fixture)['order'], after['order'])
                        self.assertEqual(self.saved(fixture)['preferences'], after['preferences'])
                        page.reload()
                        self.loaded(page)
                        self.assertEqual(self.saved(fixture)['order'], after['order'])
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                        page.close()
            finally:
                browser.close()

    def test_new_unranked_asset_does_not_expand_saved_reorder_bounds(self):
        fixture = self.fixture()
        before = self.saved(fixture)
        self.assertEqual(len(before['order']), 42)
        fixture.market.rows.append({
            'asset_id': 'player:41', 'asset_type': 'player', 'position': 'WR',
            'display_name': 'New Player 41', 'values': {'market_value': 5}})
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                page = fixture.browser_page(browser, 390, 844)
                writes = []
                page.on('request', lambda request: writes.append(json.loads(request.post_data))
                        if request.method == 'POST' and request.url.endswith('/api/my-dtos') else None)
                page.goto('https://dtos.test/account/my-dtos')
                self.loaded(page)
                page.locator('#personal-next').click()
                last = page.locator('[data-asset-id="pick:2028:1:2"]')
                last.locator('summary').click()
                down = last.get_by_role('button', name='Move 2028 Round 1 (Original franchise 2) down one overall position', exact=True)
                self.assertTrue(down.is_disabled())
                position = last.get_by_role('spinbutton')
                self.assertEqual(position.get_attribute('max'), '42')
                self.assertEqual(last.get_attribute('data-overall-rank'), '42')
                position.fill('43')
                last.get_by_role('button', name='Move 2028 Round 1 (Original franchise 2) to entered overall position', exact=True).click()
                self.assertIn('saved ranking position', page.locator('#personal-error').inner_text())
                self.assertEqual(writes, [])
                self.assertEqual(self.saved(fixture), before)
                position.fill('41')
                last.get_by_role('button', name='Move 2028 Round 1 (Original franchise 2) to entered overall position', exact=True).click()
                page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.')")
                self.loaded(page)
                self.assertIn('position 41 of 42', page.locator('#personal-status').inner_text())
                changed = self.saved(fixture)
                self.assertEqual(changed['revision'], before['revision'] + 1)
                self.assertEqual(changed['order'][40], 'pick:2028:1:2')
                self.assertNotIn('player:41', changed['order'])
                write_count = len(writes)
                new = page.locator('[data-asset-id="player:41"]')
                self.assertTrue(new.locator('.personal-drag').is_disabled())
                last.locator('.personal-drag').drag_to(new)
                self.assertEqual(len(writes), write_count)
                self.assertEqual(self.saved(fixture), changed)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                page.close()
            finally:
                browser.close()

    def test_retry_multiple_blockers_and_stale_confirmation_preserve_actual_store(self):
        fixture = self.fixture()
        before = self.saved(fixture)
        fixture.market.rows[1]['values']['market_value'] = None
        fixture.market.rows[3]['status'] = 'Retired'
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                page = fixture.browser_page(browser, 375, 667)
                page.goto('https://dtos.test/account/my-dtos')
                self.loaded(page)
                summary = page.locator('#personal-compatibility-summary')
                summary.click()
                self.assertEqual(page.locator('#personal-compatibility-issues > li').count(), 2)
                self.assertEqual(self.saved(fixture), before)
                fixture.market.rows[1]['values']['market_value'] = 980
                page.locator('#personal-compatibility-retry').focus()
                page.keyboard.press('Enter')
                self.loaded(page)
                self.assertEqual(page.locator('#personal-compatibility-issues > li').count(), 1)
                self.assertIn('Player 4', summary.inner_text())
                self.assertEqual(self.saved(fixture), before)
                remove = page.get_by_role('button', name='Review removing Player 4 from Custom ordering', exact=True)
                remove.click()
                # Another tab successfully edits an unaffected asset before confirmation.
                self.command(fixture, 'reorder', asset_id='player:5', to_position=2)
                concurrent = self.saved(fixture)
                page.locator('#personal-remove-confirm').click()
                page.locator('#personal-error').wait_for(state='visible')
                self.assertIn('another tab', page.locator('#personal-error').inner_text())
                self.assertEqual(self.saved(fixture), concurrent)
                self.assertIn('player:4', concurrent['order'])
                self.evidence('stale-confirmation', page, fixture.client.get('/api/my-dtos').json(), 375, 667,
                              {'stale_write_rejected': True, 'concurrent_order_preserved': True})
                # A genuine preparation outage keeps Neutral recovery available.
                reader = fixture.market
                fixture.market = None
                # Retry stays visible from the prior stale-write failure. Its
                # visibility is not evidence that this new read has completed.
                with page.expect_response(lambda response: response.url.endswith('/api/my-dtos')
                                          and response.request.method == 'GET') as pending:
                    page.locator('#personal-retry').click()
                self.assertEqual(pending.value.status, 503)
                page.wait_for_function("document.querySelector('#my-dtos').getAttribute('aria-busy')==='false' && document.querySelector('#personal-error').textContent.includes('Neutral Trade')")
                self.assertIn('Neutral Trade', page.locator('#personal-error').inner_text())
                self.assertTrue(page.locator('#personal-custom').is_disabled())
                self.assertEqual(self.saved(fixture), concurrent)
                fixture.market = reader
                fixture.market.rows[3]['status'] = 'Active'
                page.locator('#personal-retry').focus()
                page.keyboard.press('Enter')
                self.loaded(page)
                self.assertTrue(fixture.client.get('/api/my-dtos').json()['personal_available'])
                self.assertEqual(self.saved(fixture), concurrent)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                page.close()
            finally:
                browser.close()

    def test_custom_trade_recovery_and_neutral_return_use_real_editor_http(self):
        helper = trade_fixtures.PersonalTradeBrowserTests()
        fixture = helper.fixture()
        self.addCleanup(fixture.doCleanups)
        fixture.editor.initialize()
        # A surplus asset outside this explicit trade is no longer priced.
        next(row for row in fixture.editor.market.rows if row['asset_id'] == 'player:b')['values']['market_value'] = None
        fixture.editor.market.generation += '-missing'
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                page, records, errors = helper.page(browser, fixture, 390, 844)
                page.goto('http://testserver/trades/create')
                page.locator('#trade-valuation-mode').wait_for()
                # Missing cohort inputs no longer disable provably exact slots.
                # Deliberate removal below still restores complete availability.
                state = fixture.editor.state()
                self.assertTrue(state['personal_partial_available'])
                self.assertFalse(state['personal_available'])
                self.assertFalse(page.locator('#trade-valuation-mode option[value="custom"]').is_disabled())
                self.assertEqual(page.locator('#trade-valuation-mode').input_value(), 'custom')
                page.locator('#trade-valuation-mode').select_option('neutral')
                page.goto('http://testserver/account/my-dtos')
                self.loaded(page)
                page.locator('#personal-compatibility-summary').click()
                page.locator('[data-remove-asset="player:b"]').click()
                page.locator('#personal-remove-confirm').click()
                page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.')")
                page.goto('http://testserver/trades/create')
                page.locator('#trade-valuation-mode').wait_for()
                self.assertFalse(page.locator('#trade-valuation-mode option[value="custom"]').is_disabled())
                # Complete recovery does not silently replace an existing
                # Neutral session choice made while reviewing missing evidence.
                page.locator('#trade-valuation-mode').select_option('custom')
                page.locator('#trade-partner').select_option('2')
                page.locator('#trade-sent-board button[data-asset-id="a"]').click()
                if page.locator('[data-side="received"]').is_visible():
                    page.locator('[data-side="received"]').click()
                page.locator('#trade-received-board button[data-asset-id="2028-R1-4"]').click()
                detail = page.locator('.tw-strategy-detail')
                if detail.locator('summary').count() and not detail.evaluate('e=>e.open'):
                    detail.locator('summary').click()
                self.assertTrue(page.locator('#trade-strategy').is_visible())
                page.locator('#trade-strategy').select_option('REBUILD')
                page.locator('#trade-run').click()
                page.get_by_text('Custom DTOS · your personal assessment', exact=True).wait_for()
                custom = [item['response']['evaluation'] for item in records if item['endpoint'].endswith('/evaluate')][-1]
                page.locator('#trade-valuation-mode').select_option('neutral')
                page.locator('#trade-run').click()
                page.wait_for_function("document.querySelector('#trade-result').dataset.assessment==='true'")
                neutral = [item['response']['evaluation'] for item in records if item['endpoint'].endswith('/evaluate')][-1]
                self.assertEqual(custom['market_evidence'], neutral['market_evidence'])
                self.assertEqual(custom['lineup_impact'], neutral['lineup_impact'])
                self.assertEqual(helper.draft(page)['currentProposal']['sent'], ['a'])
                self.assertEqual(helper.draft(page)['currentProposal']['received'], ['2028-R1-4'])
                page.go_back()
                page.locator('#my-dtos').wait_for()
                self.loaded(page)
                self.assertTrue(fixture.editor.state()['personal_available'])
                self.assertFalse(errors, errors)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                page.close()
            finally:
                browser.close()
