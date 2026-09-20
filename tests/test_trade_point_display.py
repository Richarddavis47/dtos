"""Browser-executed presentation proof; canonical numeric evidence is untouched."""
import re
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright


class TradePointDisplayTests(unittest.TestCase):
    def test_shared_point_display_preserves_missing_zero_and_raw_precision(self):
        source = Path('static/js/trade_workspace.js').read_text(encoding='utf-8')
        function = re.search(r'  function displayPoints\(value\) \{.*?\n  \}', source, re.S).group()
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            page = browser.new_page()
            result = page.evaluate('''() => {
                FUNCTION
                const values = [8.50899999999997, -44.8355999999999, 0, null,
                                undefined, NaN, Infinity, '1.2', false, -0.0001, 18.2534];
                const before = values.slice();
                return {display: values.map(displayPoints),
                        unchanged: values.every((value, i) => Object.is(value, before[i]))};
            }'''.replace('FUNCTION', function))
            browser.close()
            self.assertEqual(result['display'], ['8.51', '-44.84', '0.00', 'Unavailable',
                'Unavailable', 'Unavailable', 'Unavailable', 'Unavailable', 'Unavailable', '0.00', '18.25'])
            self.assertTrue(result['unchanged'])

    def test_all_trade_point_surfaces_use_the_shared_formatter(self):
        source = Path('static/js/trade_workspace.js').read_text(encoding='utf-8')
        for field in ('impact.delta', 'horizon.delta', 'horizon.supported_week_delta_subtotal', 'c.delta'):
            self.assertIn(f'displayPoints({field})', source)
        self.assertNotIn('String(impact.delta)', source)
        self.assertNotIn('${c.delta}', source)
