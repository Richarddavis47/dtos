"""Canonical Market + authenticated HTTP + released editor/Trade client.

Responsive Chromium and disposable accounts, not live-account/Safari evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.core.asset_market import AssetMarketCache
from src.core.historical_memory.store import HistoricalStore
from tests.test_asset_market import _brain_asset
from tests import test_personal_trade_browser as trade_browser
from tools.validation.browser_runtime import launch_chromium


class CanonicalPersonalTradeBrowserTests(trade_browser.PersonalTradeBrowserTests):
    def fixture(self):
        fixture = super().fixture()
        editor = fixture.editor
        rows = editor.market.rows
        editor.data['market_data'].pop('generation')
        editor.data['pick_ledger'] = [
            {**pick, 'season': pick['year']} for team in editor.data['teams']
            for pick in team['picks_owned']]
        editor.data['valuation_intelligence'] = {
            'schema_version': '1.0', 'generated_at': '2026-10-24T00:00:00Z',
            'semantic_generation': 'canonical-browser-A',
            'assets': {row['asset_id']: _brain_asset(row['asset_id'], row['values']['market_value'], None, None)
                       for row in rows},
        }
        store = HistoricalStore(Path(editor.temp.name) / 'canonical-history.sqlite3')
        editor.market = AssetMarketCache().get(editor.data, {'data': editor.data}, store, 'league-1')
        return fixture

    def test_pending_retry_ready_saved_reload_and_error_recovery_at_all_widths(self):
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in self.viewports:
                    with self.subTest(width=width):
                        fixture = self.fixture()
                        try:
                            market = fixture.editor.market
                            fixture.editor.market = None
                            page, records, errors = self.page(browser, fixture, width, height)
                            page.goto('http://testserver/account/my-dtos')
                            retry = page.get_by_role('button', name='Retry rankings', exact=True)
                            retry.wait_for(state='visible')
                            self.assertIn('Neutral Trade', page.locator('#personal-error').inner_text())
                            self.assertEqual(page.get_by_role('link', name='Check Market', exact=True).get_attribute('href'), '/market')
                            out = os.getenv('DTOS_PERSONAL_AVAILABILITY_EVIDENCE')
                            if out:
                                Path(out).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(out) / f'pending-{width}.png'), full_page=True)
                            fixture.editor.market = market
                            retry.focus()
                            page.keyboard.press('Enter')
                            page.get_by_role('button', name='Create Custom Rankings', exact=True).wait_for()
                            self.assertTrue(page.locator('#personal-recovery').is_hidden())
                            self.assertEqual(page.evaluate('document.activeElement.id'), 'personal-initialize')
                            self.edit_rankings_in_browser(page)
                            self.choose_package(page)
                            self.assertEqual(page.locator('#trade-valuation-mode option[value="custom"]').is_disabled(), False)
                            page.locator('#trade-valuation-mode').select_option('neutral')
                            page.goto('http://testserver/account/my-dtos')
                            page.wait_for_function("document.querySelector('.personal-row')?.dataset.assetId==='player:a'")
                            self.assertIn('Personal 500', page.locator('.personal-row').first.inner_text())
                            fixture.editor.market = None
                            page.locator('#personal-settings > summary').click()
                            page.get_by_role('button', name='Reload rankings', exact=True).click()
                            retry.wait_for(state='visible')
                            self.assertTrue(page.locator('#personal-custom').is_disabled())
                            self.assertTrue(page.locator('.personal-row .personal-drag').first.is_disabled())
                            fixture.editor.market = market
                            retry.click()
                            page.wait_for_function("!document.querySelector('#personal-custom').disabled")
                            self.assertIn('Personal 500', page.locator('.personal-row').first.inner_text())
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                            self.assertFalse(errors, errors)
                            measurements.append({'width': width, 'height': height, 'overflow': 0,
                                'canonical_market_reader': True, 'provider_timestamp_fields_required': False,
                                'pending_retry_ready': True, 'saved_order_preserved': True,
                                'custom_then_neutral_trade_navigation': True, 'keyboard_retry': True,
                                'environment': 'Responsive Chromium with disposable authenticated HTTP accounts'})
                            if out:
                                page.screenshot(path=str(Path(out) / f'ready-{width}.png'), full_page=True)
                            page.close()
                        finally:
                            fixture.doCleanups()
            finally:
                browser.close()
        if os.getenv('DTOS_PERSONAL_AVAILABILITY_EVIDENCE'):
            (Path(os.environ['DTOS_PERSONAL_AVAILABILITY_EVIDENCE']) / 'measurements.json').write_text(json.dumps(measurements, indent=2))

    def test_late_pending_response_cannot_replace_newer_ready_state(self):
        fixture = self.fixture()
        self.addCleanup(fixture.doCleanups)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, errors = self.page(browser, fixture, 390, 844)
                # A deterministic transport gate: the first failed read arrives
                # after the retry succeeds, even if AbortController is ignored.
                page.add_init_script("""(() => {
                  const realFetch = window.fetch.bind(window); let first = true;
                  window.fetch = (url, options) => {
                    if (url === '/api/my-dtos' && (!options.method || options.method === 'GET') && first) {
                      first = false;
                      return new Promise(resolve => { window.releaseOldPending = () => resolve(new Response(JSON.stringify({message:'Old pending generation'}), {status:503,headers:{'Content-Type':'application/json'}})); });
                    }
                    return realFetch(url, options);
                  };
                })();""")
                page.goto('http://testserver/account/my-dtos')
                page.locator('#personal-settings > summary').click()
                page.get_by_role('button', name='Reload rankings', exact=True).click()
                page.get_by_role('button', name='Create Custom Rankings', exact=True).wait_for()
                page.evaluate('window.releaseOldPending()')
                page.wait_for_function("document.querySelector('#my-dtos').getAttribute('aria-busy')==='false'")
                self.assertTrue(page.locator('#personal-error').is_hidden())
                self.assertTrue(page.locator('#personal-recovery').is_hidden())
                self.assertGreater(page.locator('.personal-row').count(), 0)
                self.assertFalse(errors, errors)
                page.close()
            finally:
                browser.close()

    def test_canonical_rankings_enable_all_authenticated_trade_workflows(self):
        fixture = self.fixture()
        self.addCleanup(fixture.doCleanups)
        fixture.editor.initialize()
        for operation, extra in (
            ('generate', {'workflow': 'shop', 'asset_id': 'a', 'partner_roster_id': 0,
                          'shop_preference': 'draft_capital'}),
            ('generate', {'workflow': 'trade_for', 'asset_id': '2028-R1-4', 'partner_roster_id': 0}),
            ('generate', {'workflow': 'recommended', 'partner_roster_id': 0}),
            ('assist', {'instruction': 'make this trade work'}),
            ('balance', {}), ('calculate', {}), ('evaluate', {})):
            with self.subTest(operation=operation, workflow=extra.get('workflow')):
                result = fixture.trade('custom', endpoint=operation, **extra)
                self.assertEqual(result.status_code, 200, result.text)
                content = result.json()
                rows = content.get('results')
                if operation in {'generate', 'assist'}:
                    self.assertGreater(content.get('count', len(rows or [])), 0, result.text[:1000])
                if operation == 'evaluate':
                    neutral = fixture.trade('neutral').json()['evaluation']
                    self.assertEqual(content['evaluation']['market_evidence'], neutral['market_evidence'])
                    self.assertEqual(content['evaluation']['lineup_impact'], neutral['lineup_impact'])
