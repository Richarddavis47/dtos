"""Phone ranking density and focus over real authenticated preference commands.

No production accounts or successful screenshot/DOM archives. Responsive Chromium
and emulated touch are separate from physical iPhone/Safari acceptance.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from src.core.accounts.personal_store import load_personal
from tests import test_personal_rankings_browser as fixtures
from tools.validation.browser_runtime import launch_chromium


VIEWPORTS = ((320, 432), (375, 667), (390, 844), (1280, 900))


class RankingsAccessibilityBrowserTests(unittest.TestCase):
    def start(self, browser, width=390, height=844, *, touch=False, shell=False):
        def render(title, body):
            import dtos_app
            with patch.object(dtos_app, 'account_store', f.store), \
                 patch.dict(dtos_app.STATE, {'data': f.data, 'last_sync': 'Fixture', 'last_error': None}):
                return dtos_app.page(title, body)
        f = fixtures.PersonalEditorFixture(page_renderer=render if shell else None)
        self.addCleanup(f.close)
        page = f.browser_page(browser, width, height, touch=touch)
        page.goto('https://dtos.test/account/my-dtos')
        page.locator('#personal-results-count').get_by_text('42 matches / 42 assets', exact=False).wait_for()
        page.get_by_role('button', name='Create Custom Rankings', exact=True).click()
        page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed')==='true' && !document.querySelector('#personal-custom').disabled")
        return f, page

    @staticmethod
    def row(page, asset):
        return page.locator('.personal-row[data-asset-id="' + asset + '"]')

    def edit(self, page, asset):
        row = self.row(page, asset)
        if not row.locator('details').evaluate('e=>e.open'):
            summary = row.locator('summary')
            summary.focus()
            summary.press('Enter')
        return row

    @staticmethod
    def saved(page):
        page.wait_for_function("document.querySelector('#personal-status').textContent.startsWith('Saved.') && !document.querySelector('#personal-custom').disabled")

    def focused_asset(self, page, asset):
        focused = page.locator(':focus')
        self.assertEqual(focused.evaluate("e=>e.closest('.personal-row')?.dataset.assetId"), asset)
        self.assertTrue(focused.evaluate("e=>!e.disabled && e.matches(':focus-visible') && getComputedStyle(e).outlineStyle==='solid' && e.getBoundingClientRect().height>0"))
        bounds = focused.bounding_box()
        self.assertGreaterEqual(bounds['y'], 0)
        self.assertLessEqual(bounds['y'] + bounds['height'], page.viewport_size['height'])
        self.assertTrue(focused.evaluate('''e=>{const r=e.getBoundingClientRect();
            const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
            return hit===e||e.contains(hit);}'''))

    def move_to(self, page, asset, position):
        row = self.edit(page, asset)
        row.get_by_role('spinbutton').fill(str(position))
        row.get_by_role('button', name='Move ' + row.locator('strong').inner_text().split('. ', 1)[-1]
                        + ' to entered overall position', exact=True).press('Enter')
        self.saved(page)
        self.assertEqual(self.row(page, asset).get_attribute('data-overall-rank'), str(position))

    def test_first_last_repeated_and_page_boundary_focus_at_all_viewports(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in VIEWPORTS:
                    with self.subTest(width=width):
                        f, page = self.start(browser, width, height, shell=True)
                        self.edit(page, 'player:2').get_by_role('button', name='Move Player 2 up one overall position', exact=True).press('Enter')
                        self.saved(page)
                        self.assertEqual(self.row(page, 'player:2').get_attribute('data-overall-rank'), '1')
                        self.focused_asset(page, 'player:2')
                        self.assertTrue(self.row(page, 'player:2').get_by_role('button', name='Move Player 2 up one overall position', exact=True).is_disabled())
                        self.assertIn('Player 2 moved to overall position 1 of 42', page.locator('#personal-status').inner_text())
                        # The enabled fallback supports another move immediately.
                        page.keyboard.press('Enter')
                        self.saved(page)
                        self.assertEqual(self.row(page, 'player:2').get_attribute('data-overall-rank'), '2')
                        self.focused_asset(page, 'player:2')
                        self.move_to(page, 'player:2', 41)
                        self.row(page, 'player:2').get_by_role('button', name='Move Player 2 down one overall position', exact=True).press('Enter')
                        self.saved(page)
                        self.assertEqual(self.row(page, 'player:2').get_attribute('data-overall-rank'), '42')
                        self.assertTrue(self.row(page, 'player:2').get_by_role('button', name='Move Player 2 down one overall position', exact=True).is_disabled())
                        self.focused_asset(page, 'player:2')
                        page.keyboard.press('Enter')
                        self.saved(page)
                        self.assertEqual(self.row(page, 'player:2').get_attribute('data-overall-rank'), '41')
                        self.focused_asset(page, 'player:2')
                        # Global 26→25 crosses the 25-row page without changing IDs.
                        self.move_to(page, 'player:2', 26)
                        self.row(page, 'player:2').get_by_role('button', name='Move Player 2 up one overall position', exact=True).press('Enter')
                        self.saved(page)
                        self.assertEqual(page.locator('#personal-page').inner_text(), 'Page 1 of 2')
                        self.assertEqual(self.row(page, 'player:2').get_attribute('data-overall-rank'), '25')
                        self.focused_asset(page, 'player:2')
                        self.row(page, 'player:2').get_by_role('button', name='Move Player 2 down one overall position', exact=True).press('Enter')
                        self.saved(page)
                        self.assertEqual(page.locator('#personal-page').inner_text(), 'Page 2 of 2')
                        self.focused_asset(page, 'player:2')
                        self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'][25], 'player:2')
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                        page.close()
            finally:
                browser.close()

    def test_filtered_global_moves_and_preference_scroll_focus_values_survive_disclosure(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                f, page = self.start(browser, 375, 667)
                page.locator('#personal-position').select_option('QB')
                row = self.edit(page, 'player:5')
                row.get_by_role('button', name='Move Player 5 up one overall position', exact=True).press('Enter')
                self.saved(page)
                self.focused_asset(page, 'player:5')
                self.assertEqual(self.row(page, 'player:5').get_attribute('data-overall-rank'), '4')
                self.assertIn('10 matches / 42 assets · Ranks are overall', page.locator('#personal-results-count').inner_text())
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'][3], 'player:5')
                row = self.row(page, 'player:5')
                target = row.get_by_label('Target acquisition: Player 5', exact=True)
                target.scroll_into_view_if_needed()
                target.focus()
                before = row.bounding_box()['y']
                target.press('Space')
                self.saved(page)
                self.focused_asset(page, 'player:5')
                # Preserve the asset's viewport anchor, compensating for the
                # live announcement changing height above the scrolled list.
                self.assertLessEqual(abs(row.bounding_box()['y'] - before), 3)
                row.get_by_label('Protect outgoing: Player 5', exact=True).check()
                self.saved(page)
                row.get_by_label('Start personal tier at Player 5', exact=True).check()
                self.saved(page)
                prior_values = self.row(page, 'player:5').locator('.personal-values').inner_text()
                row.locator('summary').click()
                self.assertFalse(row.locator('details').evaluate('e=>e.open'))
                self.assertIn('Target · Protect · Tier start', row.inner_text())
                self.assertEqual(row.locator('.personal-values').inner_text(), prior_values)
                row.locator('summary').click()
                self.assertTrue(row.get_by_label('Target acquisition: Player 5', exact=True).is_checked())
                self.assertTrue(row.get_by_label('Protect outgoing: Player 5', exact=True).is_checked())
                self.assertTrue(row.get_by_label('Start personal tier at Player 5', exact=True).is_checked())
                self.assertEqual(row.locator('.personal-values').inner_text(), prior_values)
                page.locator('#personal-search').fill('Player 5')
                row = self.edit(page, 'player:5')
                row.get_by_role('button', name='Move Player 5 down one overall position', exact=True).press('Enter')
                self.saved(page)
                self.assertEqual(row.get_attribute('data-overall-rank'), '5')
                self.focused_asset(page, 'player:5')
                saved = load_personal(f.store, f.account_id, '100', 1)
                page.get_by_role('button', name='Neutral DTOS', exact=True).click()
                self.saved(page)
                page.get_by_role('button', name='Custom DTOS', exact=True).click()
                self.saved(page)
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'], saved['order'])
                page.reload()
                page.locator('#personal-results-count').get_by_text('42 matches', exact=False).wait_for()
                row = self.edit(page, 'player:5')
                self.assertTrue(row.get_by_label('Target acquisition: Player 5', exact=True).is_checked())
                self.assertTrue(row.get_by_label('Start personal tier at Player 5', exact=True).is_checked())
                row.get_by_label('Target acquisition: Player 5', exact=True).uncheck()
                self.saved(page)
                row.get_by_label('Prefer to avoid acquiring: Player 5', exact=True).check()
                self.saved(page)
                row.locator('summary').click()
                row.locator('summary').click()
                self.assertTrue(row.get_by_label('Prefer to avoid acquiring: Player 5', exact=True).is_checked())
                self.assertFalse(row.get_by_label('Target acquisition: Player 5', exact=True).is_checked())
            finally:
                browser.close()

    def test_collapsed_density_top_bottom_pagination_and_warnings_at_all_viewports(self):
        measurements = []
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in VIEWPORTS:
                    with self.subTest(width=width):
                        f, page = self.start(browser, width, height)
                        page.evaluate('scrollTo(0,0)')
                        self.assertEqual(page.locator('.personal-row').count(), 25)
                        self.assertEqual(page.locator('.personal-row details[open]').count(), 0)
                        first = self.row(page, 'player:1')
                        self.assertIn('Market 990', first.inner_text())
                        self.assertIn('Personal 990', first.inner_text())
                        geometry = page.evaluate('''() => {
                            const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top+scrollY,bottom:r.bottom+scrollY,height:r.height}};
                            const rows=[...document.querySelectorAll('.personal-row')];
                            return {first_row:box('.personal-row'),first_title:box('.personal-row strong'),
                                pagination:box('.personal-pagination'),search:box('#personal-search'),mode:box('.personal-mode'),
                                first_three_heights:rows.slice(0,3).map(r=>r.getBoundingClientRect().height),
                                rows_in_first_1000:rows.filter(r=>r.getBoundingClientRect().bottom<=rows[0].getBoundingClientRect().top+1000).length,
                                overflow:document.documentElement.scrollWidth-innerWidth};}''')
                        self.assertLess(geometry['pagination']['bottom'], geometry['first_row']['top'])
                        self.assertLess(geometry['first_title']['bottom'], height)
                        self.assertGreaterEqual(geometry['rows_in_first_1000'], 8)
                        self.assertLessEqual(geometry['overflow'], 0)
                        self.assertGreaterEqual(first.locator('summary').bounding_box()['height'], 44)
                        self.assertGreaterEqual(first.locator('.personal-drag').bounding_box()['height'], 44)
                        measurements.append({'width': width, 'height': height, 'geometry': geometry,
                            'kind': 'responsive Chromium; real authenticated API; disposable prepared Market fixture'})
                        page.locator('#personal-next').click()
                        self.assertEqual(page.locator('.personal-row').count(), 17)
                        self.assertEqual(page.locator('#personal-page-bottom').inner_text(), 'Page 2 of 2')
                        self.assertEqual(page.locator('.personal-row').first.get_attribute('data-overall-rank'), '26')
                        page.locator('#personal-previous-bottom').click()
                        self.assertEqual(page.locator('.personal-row').count(), 25)
                        self.assertEqual(page.locator('#personal-page').inner_text(), 'Page 1 of 2')
                        self.assertIsNone(load_personal(f.store, f.account_id, '100', 2))
                        # Unavailable new identities stay qualified outside disclosure.
                        f.market.rows.append({'asset_id': 'player:41', 'asset_type': 'player', 'position': 'WR',
                            'display_name': 'New Player 41', 'values': {'market_value': 5}})
                        page.locator('#personal-settings > summary').click()
                        page.get_by_role('button', name='Reload rankings', exact=True).click()
                        page.get_by_text('43 eligible ranked assets', exact=False).wait_for()
                        page.locator('#personal-search').fill('New Player 41')
                        item = page.locator('.personal-row')
                        self.assertIn('Unranked New Player 41', item.inner_text())
                        self.assertIn('Personal Unavailable', item.inner_text())
                        self.assertIn('Not in your saved Custom order', item.inner_text())
                        self.assertFalse(item.locator('details').evaluate('e=>e.open'))
                        self.assertTrue(item.locator('.personal-drag').is_disabled())
                        page.close()
            finally:
                browser.close()
        if os.getenv('DTOS_RANKINGS_UX_EVIDENCE'):
            root = Path(os.environ['DTOS_RANKINGS_UX_EVIDENCE'])
            root.mkdir(parents=True, exist_ok=True)
            (root / 'phone-measurements.json').write_text(json.dumps(measurements, indent=2) + '\n')

    def test_late_read_and_late_write_do_not_replace_fresher_state(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                f, page = self.start(browser)
                page.add_init_script('''(() => {
                    const original=window.fetch; let firstRead=true;
                    window.fetch=(url, options={}) => {
                        const result=original(url,options);
                        if(url==='/api/my-dtos' && !options.method && firstRead){firstRead=false;return result.then(response=>new Promise(resolve=>window.releaseOldRead=()=>resolve(response)));}
                        if(url==='/api/my-dtos' && options.method==='POST' && window.holdWrite){window.holdWrite=false;return result.then(response=>new Promise(resolve=>window.releaseOldWrite=()=>resolve(response)));}
                        return result;
                    };
                })();''')
                page.reload()
                page.wait_for_function('typeof window.releaseOldRead === "function"')
                f.market.rows.append({'asset_id': 'player:41', 'asset_type': 'player', 'position': 'WR',
                                     'display_name': 'New Player 41', 'values': {'market_value': 5}})
                page.locator('#personal-settings > summary').click()
                page.get_by_role('button', name='Reload rankings', exact=True).click()
                page.locator('#personal-results-count').get_by_text('43 matches', exact=False).wait_for()
                page.evaluate('releaseOldRead()')
                page.wait_for_function("document.querySelector('#personal-results-count').textContent.startsWith('43 matches')")
                # Hold a committed preference response, then simulate BFCache return.
                row = self.edit(page, 'player:2')
                page.evaluate('window.holdWrite=true')
                row.get_by_role('button', name='Move Player 2 up one overall position', exact=True).click()
                page.wait_for_function('typeof window.releaseOldWrite === "function"')
                current = f.client.get('/api/my-dtos').json()
                response = f.client.post('/api/my-dtos', json={'command': 'reorder', 'asset_id': 'player:3',
                    'to_position': 1, 'expected_revision': current['revision'], 'market_generation': current['generation'],
                    'context': current['context']}, headers={'x-csrf-token': f.csrf})
                self.assertEqual(response.status_code, 200, response.text)
                page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));")
                page.wait_for_function("document.querySelector('.personal-row').dataset.assetId==='player:3'")
                page.evaluate('releaseOldWrite()')
                page.wait_for_function("!document.querySelector('#personal-custom').disabled")
                self.assertEqual(page.locator('.personal-row').first.get_attribute('data-asset-id'), 'player:3')
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['revision'], response.json()['revision'])
                # A legitimate stale-CAS failure preserves that latest state.
                stale = f.client.post('/api/my-dtos', json={'command': 'reorder', 'asset_id': 'player:4',
                    'to_position': 1, 'expected_revision': current['revision'], 'market_generation': current['generation'],
                    'context': current['context']}, headers={'x-csrf-token': f.csrf})
                self.assertEqual(stale.status_code, 409)
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'][0], 'player:3')
            finally:
                browser.close()

    def test_actual_application_shell_title_navigation_and_phone_controls(self):
        measurements = []
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in VIEWPORTS:
                    with self.subTest(width=width):
                        _, page = self.start(browser, width, height, shell=True)
                        page.evaluate('scrollTo(0,0)')
                        self.assertEqual(page.get_by_role('heading', level=1, name='My DTOS', exact=True).count(), 1)
                        self.assertTrue(page.get_by_label('Account and league context', exact=True).is_visible())
                        self.assertTrue(page.locator('.manager-nav').is_visible())
                        measurements.append(page.evaluate('''() => {
                            const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top+scrollY,bottom:r.bottom+scrollY,height:r.height}};
                            return {width:innerWidth,height:innerHeight,editor:box('#my-dtos'),
                                first_row:box('.personal-row'),pagination:box('.personal-pagination'),nav:box('.manager-nav'),
                                overflow:document.documentElement.scrollWidth-innerWidth,
                                kind:'actual application shell; authenticated disposable fixture'};}'''))
                        self.assertLess(measurements[-1]['first_row']['top'], 700)
                        self.assertLessEqual(measurements[-1]['overflow'], 0)
                        for selector in ('#personal-search', '#personal-next', '.personal-row summary'):
                            control = page.locator(selector).first
                            control.scroll_into_view_if_needed()
                            self.assertTrue(control.evaluate('''e=>{const r=e.getBoundingClientRect();
                                const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
                                return hit===e||e.contains(hit);}'''))
                        page.close()
            finally:
                browser.close()
        if os.getenv('DTOS_RANKINGS_UX_EVIDENCE'):
            root = Path(os.environ['DTOS_RANKINGS_UX_EVIDENCE'])
            root.mkdir(parents=True, exist_ok=True)
            (root / 'shell-measurements.json').write_text(json.dumps(measurements, indent=2) + '\n')

    def test_late_malformed_write_cannot_rollback_fresher_render(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                f, page = self.start(browser)
                page.evaluate('''() => {
                    const original=fetch;let held=false;
                    window.fetch=(url,options={})=>{
                        const result=original(url,options);
                        if(url==='/api/my-dtos' && options.method==='POST' && !held){
                            held=true;return result.then(()=>new Promise(resolve=>window.releaseMalformed=()=>resolve(new Response('{',{status:200}))));
                        }
                        return result;
                    };
                }''')
                self.edit(page, 'player:2').get_by_role('button', name='Move Player 2 up one overall position', exact=True).click()
                page.wait_for_function('typeof window.releaseMalformed === "function"')
                current = f.client.get('/api/my-dtos').json()
                changed = f.client.post('/api/my-dtos', json={'command': 'reorder', 'asset_id': 'player:3',
                    'to_position': 1, 'expected_revision': current['revision'], 'market_generation': current['generation'],
                    'context': current['context']}, headers={'x-csrf-token': f.csrf})
                self.assertEqual(changed.status_code, 200)
                page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));")
                page.wait_for_function("document.querySelector('.personal-row').dataset.assetId==='player:3'")
                # Settle the stale JSON rejection before inspecting the newer
                # render. A fresh GET here would conceal an erroneous rollback.
                page.evaluate('async () => { releaseMalformed(); await new Promise(resolve => setTimeout(resolve, 0)); }')
                self.assertEqual(page.locator('.personal-row').first.get_attribute('data-asset-id'), 'player:3')
                self.assertTrue(page.locator('#personal-error').is_hidden())
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['order'][0], 'player:3')
            finally:
                browser.close()

    def test_touch_tap_cancel_and_pen_drag_keep_exact_filtered_identity(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                f, page = self.start(browser, touch=True)
                page.locator('#personal-position').select_option('QB')
                first = self.row(page, 'player:1')
                source = self.row(page, 'player:5').locator('.personal-drag')
                first.scroll_into_view_if_needed()
                point = source.bounding_box()
                session = page.context.new_cdp_session(page)
                x, y = point['x'] + point['width'] / 2, point['y'] + point['height'] / 2
                revision = load_personal(f.store, f.account_id, '100', 1)['revision']
                session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
                session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                self.assertTrue(self.row(page, 'player:5').locator('details').evaluate('e=>e.open'))
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['revision'], revision)
                self.row(page, 'player:5').locator('summary').click()
                point = source.bounding_box()
                x, y = point['x'] + point['width'] / 2, point['y'] + point['height'] / 2
                session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
                session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y - 30}]})
                session.send('Input.dispatchTouchEvent', {'type': 'touchCancel', 'touchPoints': []})
                self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['revision'], revision)
                self.assertEqual(page.locator('.personal-drop-target').count(), 0)
                # A pen uses the captured pointer path; global rank 5 goes to 1,
                # rather than to filtered QB slot 2 or a label-derived identity.
                point = source.bounding_box()
                target = first.bounding_box()
                x, y = point['x'] + point['width'] / 2, point['y'] + point['height'] / 2
                session.send('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y,
                    'button': 'left', 'buttons': 1, 'clickCount': 1, 'pointerType': 'pen'})
                session.send('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': target['y'] + 20,
                    'button': 'left', 'buttons': 1, 'pointerType': 'pen'})
                session.send('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': target['y'] + 20,
                    'button': 'left', 'buttons': 0, 'clickCount': 1, 'pointerType': 'pen'})
                self.saved(page)
                saved = load_personal(f.store, f.account_id, '100', 1)
                self.assertEqual(saved['order'][0], 'player:5')
                self.assertEqual(saved['order'][1:5], ['player:1', 'player:2', 'player:3', 'player:4'])
                self.assertEqual(len(saved['order']), len(set(saved['order'])))
            finally:
                browser.close()


class RankingsPreparedEditingHTTPTests(unittest.TestCase):
    def test_real_edits_keep_market_values_and_do_no_heavy_work(self):
        f = fixtures.PersonalEditorFixture()
        self.addCleanup(f.close)
        before = copy.deepcopy(f.market.rows)
        targets = ('httpx.HTTPTransport.handle_request', 'httpx.AsyncHTTPTransport.handle_async_request',
                   'services.trade_intelligence.generate_trade_workflow', 'src.core.fois.service.FOISService.generate',
                   'src.core.trade_intelligence.lineup.optimal_legal_lineup', 'services.history.history_records',
                   'src.core.asset_market.engine.AssetMarketCache.get', 'src.core.asset_market.engine.AssetMarketCache.reconcile')
        with ExitStack() as stack:
            spies = {name: stack.enter_context(patch(name, side_effect=AssertionError('Unexpected heavy work: ' + name))) for name in targets}
            state = f.client.get('/api/my-dtos').json()
            for command, extra in [('initialize', {}), ('reorder', {'asset_id': 'player:2', 'to_position': 1}),
                ('tiers', {'asset_id': 'player:2', 'tier_start': True}),
                ('preferences', {'asset_id': 'pick:2028:1:1', 'preferences': {'target': True, 'protect': True}}),
                ('mode', {'mode': 'neutral'}), ('mode', {'mode': 'custom'}),
                ('restart', {'confirmation': 'RESTART RANKINGS'})]:
                response = f.client.post('/api/my-dtos', json={'command': command, 'expected_revision': state['revision'],
                    'market_generation': state['generation'], 'context': state['context'], **extra}, headers={'x-csrf-token': f.csrf})
                self.assertEqual(response.status_code, 200, response.text)
                state = response.json()
                self.assertTrue(all(count == 0 for count in state['heavy_work'].values()))
            self.assertTrue(all(spy.call_count == 0 for spy in spies.values()))
        self.assertEqual(f.market.rows, before)
        self.assertEqual([r['personal_value'] for r in state['rows']], [r['market_value'] for r in state['rows']])
        self.assertEqual(load_personal(f.store, f.account_id, '100', 1)['preferences']['pick:2028:1:1'], {'target': True, 'protect': True})
