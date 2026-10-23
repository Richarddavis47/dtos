"""Saved full rankings → authenticated real Trade HTTP → rendered Chromium.

Only prepared source transports and the page shell are disposable fixtures.
Trade evaluation, Calculator, Balance, previews and client state are real paths.
Responsive Chromium and CDP controls do not establish physical Safari acceptance.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from src.ui.theme import DESIGN_SYSTEM_CSS
from tests import test_personal_rankings as personal
from tools.validation.browser_runtime import launch_chromium


class PersonalTradeBrowserTests(unittest.TestCase):
    viewports = ((320, 432), (375, 667), (390, 844), (1280, 900))

    def fixture(self):
        fixture = personal.PersonalRankingsTradeHTTPTests(
            'test_calculator_keeps_canonical_and_personal_costs_distinct')
        fixture.setUp()
        return fixture

    def page(self, browser, fixture, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.set_default_timeout(8000)
        records, errors = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def transport(route):
            request = route.request
            parsed = urlsplit(request.url)
            if parsed.netloc == 'sleepercdn.com':
                route.fulfill(content_type='image/png', body=base64.b64decode(
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2ioAAAAASUVORK5CYII='))
                return
            if parsed.netloc != 'testserver':
                route.abort()
                return
            response = fixture.editor.client.request(request.method,
                parsed.path + ('?' + parsed.query if parsed.query else ''), content=request.post_data,
                headers={key: value for key, value in request.headers.items()
                         if key in ('content-type', 'x-csrf-token', 'origin', 'accept')})
            body = response.content
            if response.headers.get('content-type', '').startswith('text/html'):
                body = ('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
                        '<style>' + DESIGN_SYSTEM_CSS + '</style></head><body>' + body.decode() + '</body></html>').encode()
            if parsed.path.startswith('/api/trades/') and request.method == 'POST':
                payload = json.loads(request.post_data or '{}')
                records.append({'endpoint': parsed.path, 'status': response.status_code,
                                'payload': payload, 'response': response.json()})
            route.fulfill(status=response.status_code,
                          headers={key: value for key, value in response.headers.items()
                                   if key.lower() not in {'content-length', 'content-encoding'}}, body=body)
        page.route('**/*', transport)
        return page, records, errors

    def edit_rankings_in_browser(self, page):
        page.goto('http://testserver/account/my-dtos')
        page.get_by_role('button', name='Create Custom Rankings', exact=True).click()
        page.wait_for_function("document.querySelector('#personal-custom').getAttribute('aria-pressed')==='true'")
        row = page.locator('[data-asset-id="player:a"]')
        row.locator('summary').click()
        row.get_by_role('spinbutton').fill('1')
        row.get_by_role('button', name='Move a to entered overall position', exact=True).click()
        page.wait_for_function("document.querySelector('.personal-row').dataset.assetId==='player:a'")
        self.assertIn('Personal 500', page.locator('.personal-row').first.inner_text())

    def choose_package(self, page, workflow='create'):
        page.goto('http://testserver/trades/' + workflow)
        page.locator('#trade-valuation-mode').wait_for()
        self.assertEqual(page.locator('#trade-valuation-mode').input_value(), 'custom')
        page.locator('#trade-partner').select_option('2')
        page.locator('#trade-sent-board button[data-asset-id="a"]').click()
        if page.locator('[data-side="received"]').is_visible():
            page.locator('[data-side="received"]').click()
        page.locator('#trade-received-board button[data-asset-id="2028-R1-4"]').click()
        detail = page.locator('.tw-strategy-detail')
        if not detail.evaluate('e=>e.open'):
            detail.locator('summary').click()
        page.locator('#trade-strategy').select_option('REBUILD')

    @staticmethod
    def draft(page):
        return page.evaluate("JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'))))")

    def save_evidence(self, kind, width, height, page, records, errors):
        self.assertFalse(errors, errors)
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
        output = os.getenv('DTOS_PERSONAL_BROWSER_EVIDENCE')
        if not output:
            return
        destination = Path(output) / 'trade'
        destination.mkdir(parents=True, exist_ok=True)
        # Sanitized disposable facts only. Never persist CSRF/session headers.
        summary = []
        for record in records:
            response = record['response']
            evaluation = response.get('evaluation') or {}
            summary.append({'endpoint': record['endpoint'], 'status': record['status'],
                'mode': record['payload'].get('valuation_mode'),
                'sent': record['payload'].get('assets_sent'), 'received': record['payload'].get('assets_received'),
                'recommendation': evaluation.get('recommendation'),
                'neutral_recommendation': (evaluation.get('neutral_assessment') or {}).get('recommendation'),
                'personal_values': evaluation.get('personal_value_evidence'),
                'neutral_values': evaluation.get('market_evidence'),
                'balance_count': response.get('count'),
                'proposal': response.get('proposal')})
        # These raw responses contain only this disposable fixture's facts and
        # server evidence. Request headers/cookies and editor CSRF are excluded.
        (destination / f'{kind}-{width}-api.json').write_text(json.dumps(records, indent=2, default=str))
        (destination / f'{kind}-{width}.json').write_text(json.dumps({'environment': 'Responsive Chromium; authenticated disposable account; real evaluator',
            'width': width, 'height': height, 'overflow': page.evaluate('document.documentElement.scrollWidth-innerWidth'),
            'errors': errors, 'requests': summary, 'final_draft': self.draft(page)['currentProposal']}, indent=2, default=str))
        page.locator('#trade-result').scroll_into_view_if_needed()
        page.screenshot(path=str(destination / f'{kind}-{width}.png'))

    def test_editor_custom_builder_and_neutral_evaluation_share_exact_market_and_lineup(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in self.viewports:
                    with self.subTest(width=width):
                        fixture = self.fixture()
                        try:
                            page, records, errors = self.page(browser, fixture, width, height)
                            self.edit_rankings_in_browser(page)
                            self.choose_package(page)
                            page.locator('#trade-run').click()
                            page.get_by_text('Custom DTOS · your personal assessment', exact=True).wait_for()
                            custom = next(record['response']['evaluation'] for record in records
                                          if record['endpoint'].endswith('/evaluate'))
                            self.assertEqual(custom['recommendation'], 'NOT WORTH IT')
                            self.assertEqual(custom['neutral_assessment']['recommendation'], 'WORTH PURSUING')
                            self.assertEqual(custom['dimensions']['strategic_fit']['active']['future_capital']['assessment']['valuation_basis'], 'personal_rank_slot_value')
                            self.assertIn('Your personal values from Custom Rankings', page.locator('#trade-result').inner_text())
                            self.assertIn('Neutral DTOS: WORTH PURSUING', page.locator('#trade-result').inner_text())
                            self.assertIn('Your personal values from Custom Rankings · You send 500 / You receive 250', page.locator('#trade-result').inner_text())
                            self.assertEqual(self.draft(page)['currentProposal']['sent'], ['a'])
                            self.assertEqual(self.draft(page)['currentProposal']['received'], ['2028-R1-4'])
                            page.locator('#trade-valuation-mode').select_option('neutral')
                            page.locator('#trade-run').click()
                            page.wait_for_function("document.querySelector('#trade-result').dataset.assessment==='true'")
                            neutral = [record['response']['evaluation'] for record in records
                                       if record['endpoint'].endswith('/evaluate')][-1]
                            self.assertEqual(neutral['recommendation'], 'WORTH PURSUING')
                            self.assertNotIn('personal_value_evidence', neutral)
                            for key in ('market_evidence', 'lineup_impact', 'multi_horizon_impact'):
                                self.assertEqual(custom[key], neutral[key], key)
                            self.assertEqual(self.draft(page)['currentProposal']['sent'], ['a'])
                            self.assertEqual(self.draft(page)['currentProposal']['received'], ['2028-R1-4'])
                            self.save_evidence('builder', width, height, page, records, errors)
                            page.close()
                        finally:
                            fixture.doCleanups()
            finally:
                browser.close()

    def test_neutral_evaluation_survives_optional_rankings_warming_after_focus(self):
        fixture = self.fixture()
        self.addCleanup(fixture.doCleanups)
        fixture.editor.market = None
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, errors = self.page(browser, fixture, 390, 844)
                page.goto('http://testserver/trades/create')
                page.locator('#trade-valuation-mode').wait_for()
                self.assertEqual(page.locator('#trade-valuation-mode').input_value(), 'neutral')
                page.locator('#trade-partner').select_option('2')
                page.locator('#trade-sent-board button[data-asset-id="a"]').click()
                if page.locator('[data-side="received"]').is_visible():
                    page.locator('[data-side="received"]').click()
                page.locator('#trade-received-board button[data-asset-id="2028-R1-4"]').click()
                page.locator('#trade-strategy').select_option('REBUILD')
                with page.expect_response(lambda response: response.url.endswith('/api/my-dtos')) as pending:
                    page.evaluate("window.dispatchEvent(new Event('focus'))")
                self.assertEqual(pending.value.status, 503)
                self.assertEqual(page.get_by_role('button', name='Reload current facts', exact=True).count(), 0)
                page.locator('#trade-run').click()
                page.wait_for_function("document.querySelector('#trade-result').dataset.assessment==='true'")
                evaluated = [record for record in records if record['endpoint'].endswith('/evaluate')]
                self.assertEqual(len(evaluated), 1)
                self.assertEqual(evaluated[0]['status'], 200)
                self.assertEqual(evaluated[0]['response']['evaluation']['recommendation'], 'WORTH PURSUING')
                self.assertEqual(evaluated[0]['payload']['valuation_mode'], 'neutral')
                self.assertEqual(self.draft(page)['currentProposal']['sent'], ['a'])
                self.assertEqual(self.draft(page)['currentProposal']['received'], ['2028-R1-4'])
                self.save_evidence('neutral-warming', 390, 844, page, records, errors)
                page.close()
            finally:
                browser.close()

    def test_custom_warming_and_neutral_revoked_session_still_fail_closed_on_focus(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for mode, expected_status in (('custom', 503), ('neutral', 401)):
                    with self.subTest(mode=mode, status=expected_status):
                        fixture = self.fixture()
                        try:
                            page, records, errors = self.page(browser, fixture, 390, 844)
                            self.edit_rankings_in_browser(page)
                            self.choose_package(page)
                            if mode == 'neutral':
                                page.locator('#trade-valuation-mode').select_option('neutral')
                                fixture.editor.store.revoke_session(fixture.editor.tokens['account-a'][0])
                            else:
                                fixture.editor.market = None
                            original = self.draft(page)['currentProposal']
                            with page.expect_response(lambda response: response.url.endswith('/api/my-dtos')) as pending:
                                page.evaluate("window.dispatchEvent(new Event('focus'))")
                            self.assertEqual(pending.value.status, expected_status)
                            page.get_by_role('button', name='Reload current facts', exact=True).wait_for()
                            page.locator('#trade-run').click()
                            self.assertEqual([record for record in records if record['endpoint'].endswith('/evaluate')], [])
                            self.assertEqual(self.draft(page)['currentProposal'], original)
                            self.assertIn('reload current facts', page.locator('#trade-result').inner_text())
                            self.save_evidence(mode + '-focus-blocked', 390, 844, page, records, errors)
                            page.close()
                        finally:
                            fixture.doCleanups()
            finally:
                browser.close()

    def test_custom_calculator_balance_preview_keep_adopt_and_neutral_totals(self):
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in self.viewports:
                    with self.subTest(width=width):
                        fixture = self.fixture()
                        try:
                            page, records, errors = self.page(browser, fixture, width, height)
                            self.edit_rankings_in_browser(page)
                            self.choose_package(page, 'calculator')
                            personal_panel = page.locator('.tw-personal-comparison')
                            self.assertIn('You send: 500 · You receive: 250', personal_panel.inner_text())
                            market = page.locator('#trade-balance')
                            self.assertIn('Side A · You send: 250', market.inner_text())
                            self.assertIn('Side B · You receive: 250', market.inner_text())
                            original = self.draft(page)['currentProposal']
                            page.locator('#trade-balance-offer').click()
                            page.get_by_role('button', name='Preview adjustment', exact=True).first.wait_for()
                            balance = next(record['response'] for record in records if record['endpoint'].endswith('/balance'))
                            self.assertGreater(balance['count'], 0)
                            self.assertEqual(balance['original_market']['sent']['total'], 500)
                            self.assertEqual(balance['neutral_original_market']['sent']['total'], 250)
                            self.assertEqual(balance['neutral_original_market']['unit'], 'canonical_acquisition_market_price')
                            for row in balance['results']:
                                for side in ('original', 'suggested'):
                                    self.assertEqual(row['balance_adjustment'][side]['unit'], 'personal_rank_slot_value')
                                    self.assertEqual(row['balance_adjustment'][side]['valuation_basis'], 'personal_rank_slot_value')
                            expected = balance['results'][0]['proposal']
                            page.get_by_role('button', name='Preview adjustment', exact=True).first.click()
                            page.get_by_role('button', name='Keep original', exact=True).click()
                            self.assertEqual(self.draft(page)['currentProposal'], original)
                            page.get_by_role('button', name='Preview adjustment', exact=True).first.click()
                            page.get_by_role('button', name='Adopt alternative', exact=True).click()
                            adopted = self.draft(page)['currentProposal']
                            self.assertEqual(adopted['sent'], expected['assets_sent'])
                            self.assertEqual(adopted['received'], expected['assets_received'])
                            page.locator('#trade-valuation-mode').select_option('neutral')
                            self.assertEqual(page.locator('.tw-personal-comparison').count(), 0)
                            self.assertEqual(self.draft(page)['currentProposal'], adopted)
                            self.assertIn('Canonical Market comparison', market.inner_text())
                            self.save_evidence('calculator', width, height, page, records, errors)
                            page.close()
                        finally:
                            fixture.doCleanups()
            finally:
                browser.close()
