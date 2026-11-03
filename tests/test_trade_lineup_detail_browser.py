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
        self.assertEqual(helper.data, original)
        if os.environ.get('DTOS_LINEUP_DETAIL_EVIDENCE'):
            (Path(os.environ['DTOS_LINEUP_DETAIL_EVIDENCE']) / 'browser.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    unittest.main()
