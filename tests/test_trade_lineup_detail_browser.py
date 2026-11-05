"""Authenticated disposable one-QB Trade evaluation -> real responsive client."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_trade_decision_http_browser as browser_fixture
from tests import test_multileague_projection_compatibility as league_fixture
from src.core.intelligence.team_strength import prepare_for_data


class TradeLineupDetailBrowserTests(unittest.TestCase):
    def test_generated_card_lineups_are_one_disclosure_from_the_primary_card(self):
        from tests import test_trade_workflow_experience as workflow
        from playwright.sync_api import sync_playwright
        from tools.validation.browser_runtime import launch_chromium
        helper = workflow.TradeWorkflowExperienceTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, _ = helper.page(browser, f)
                try:
                    helper.ready(page)
                    page.select_option('#trade-strategy', 'RETOOL')
                    page.locator('#trade-find').press('Enter')
                    helper.complete(page)
                    card = page.locator('.tw-offer').first
                    detail = card.locator(':scope > .tw-lineup-details')
                    self.assertEqual(detail.count(), 1)
                    count = len(records)
                    detail.locator('summary').press('Enter')
                    self.assertTrue(detail.evaluate('e=>e.open'))
                    self.assertGreater(detail.locator('table').count(), 0)
                    self.assertEqual(len(records), count)
                    self.assertFalse(errors, errors)
                finally:
                    page.close()
            finally:
                browser.close()

    def test_one_qb_slot_audit_at_four_sizes_without_extra_requests(self):
        helper = browser_fixture.DecisionHTTPBrowserTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        source = league_fixture.MultiLeagueProjectionTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        helper.data.clear()
        helper.data.update(deepcopy(source.data))
        helper.data['league']['league_id'] = 'league-1'
        helper.data['market_data'] = {'providers': {'FantasyCalc': {
            pid: {'value': 3000, 'confidence': 90} for pid, p in helper.data['players'].items()
            if p['position'] not in {'K', 'DEF'}}}}
        # Keep supported starter totals and the partner's reserve effect, while
        # a genuine active bench projection gap qualifies only the owner's cover.
        bench = {'id': '1-unknown', 'name': 'Uncovered bench receiver', 'position': 'WR',
                 'fantasy_positions': ['WR'], 'status': 'Active'}
        helper.data['players'][bench['id']] = bench.copy()
        helper.data['teams'][0]['players'].append(bench.copy())
        helper.f.reader.publish_horizon({8: source.feed}, data=helper.data,
                                       league_id='league-1', season=2026, current_week=8)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(helper.f.reader, helper.data)
        original = deepcopy(helper.data)
        records = []
        for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
            with self.subTest(width=width), helper.browser(width, height) as page:
                helper.ready(page)
                page.select_option('#trade-partner', '2')
                helper.select(page, 'sent', '1-10')
                helper.select(page, 'received', '2-0')
                page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                disclosure = page.locator('#trade-result .tw-lineup-details').first
                summary = disclosure.locator('summary').first
                summary.wait_for()
                card = page.locator('#trade-result')
                self.assertIn('10.00 points (known subtotal only', card.inner_text())
                self.assertIn('Uncovered bench receiver: no numerical projection', card.inner_text())
                self.assertIn('week 8 reserve-production change: +10.00', card.inner_text())
                self.assertNotRegex(card.inner_text().lower(), r'\b(?:beta|prerelease|pre-release)\b')
                count = len(helper.requests)
                summary.scroll_into_view_if_needed()
                summary.focus()
                page.keyboard.press('Tab')
                page.keyboard.press('Shift+Tab')
                self.assertEqual(summary.evaluate('e=>e===document.activeElement'), True)
                self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                summary.press('Enter')
                self.assertTrue(disclosure.evaluate('e=>e.open'))
                first_week = disclosure.locator('.tw-lineup-week').first
                for slot in ('QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'DEF'):
                    self.assertGreater(first_week.locator('th[scope=row]').filter(has_text=slot).count(), 0)
                self.assertEqual(first_week.locator('.tw-lineup-phases > section').count(), 2)
                # Disclosure reads already-rendered evidence, not another request.
                self.assertEqual(len(helper.requests), count)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                targets = summary.bounding_box()
                self.assertGreaterEqual(targets['height'], 44)
                if width < 500:
                    summary.scroll_into_view_if_needed()
                    box = summary.bounding_box()
                    touch = page.context.new_cdp_session(page)
                    touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                    touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
                        {'x': box['x'] + box['width'] / 2, 'y': box['y'] + box['height'] / 2}]})
                    touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                    self.assertFalse(disclosure.evaluate('e=>e.open'))
                    summary.press('Enter')
                self.assertIn('not your submitted Sleeper starters', disclosure.inner_text())
                self.assertIn('Reserve known subtotal only: 10 points', disclosure.inner_text())
                self.assertIn('not a second required starting lineup', disclosure.inner_text())
                record = dict(width=width, height=height, keyboard=True, touch=width < 500,
                              no_overflow=True, extra_disclosure_requests=len(helper.requests) - count,
                              summary_height=targets['height'], slots=first_week.inner_text())
                root = os.environ.get('DTOS_LINEUP_DETAIL_EVIDENCE')
                if root:
                    directory = Path(root)
                    directory.mkdir(parents=True, exist_ok=True)
                    first_week.scroll_into_view_if_needed()
                    page.screenshot(path=str(directory / f'lineup-{width}.png'))
                records.append(record)
                # Preserve the offer under existing bounded retained-state rules;
                # do not introduce a persistent copy of the new source view.
                state = helper.state(page)
                self.assertNotIn('lineup_detail_context', json.dumps(state))
                page.reload()
                page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
                self.assertGreater(page.locator('#trade-sent-chips [data-asset-id="1-10"]').count(), 0)
                self.assertGreater(page.locator('#trade-received-chips [data-asset-id="2-0"]').count(), 0)
        self.assertEqual(helper.data, original)
        if os.environ.get('DTOS_LINEUP_DETAIL_EVIDENCE'):
            (Path(os.environ['DTOS_LINEUP_DETAIL_EVIDENCE']) / 'browser.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    unittest.main()
