"""Bounded disclosure proof; fixtures are not production acceptance evidence."""
import unittest

from playwright.sync_api import sync_playwright

from services.asset_explanations import market_explanation, pick_explanation
from src.ui.explanations import explanation_panel


class AssetExplanationBrowserTests(unittest.TestCase):
    def test_mobile_desktop_keyboard_and_collapsed_evidence(self):
        from dtos_app import CSS
        views = [
            market_explanation({'asset': {'asset_id': 'player:p', 'values': {'market_value': None}}},
                               {'direction': 'not_comparable'}, league_id='A'),
            pick_explanation({'league_id': 'A', 'year': 2027, 'round': 1,
                              'original_roster_id': 1, 'current_owner_id': 4,
                              'projected_range': 'UNKNOWN', 'projected_range_confidence': 'LOW'},
                             {'normalized_market_price': None}, league_id='A'),
        ]
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for width in (375, 390, 1280):
                    for view in views:
                        with self.subTest(width=width, subject=view.subject):
                            page = browser.new_page(viewport={'width': width, 'height': 900})
                            try:
                                page.set_content(f'<style>{CSS}</style><main class="wrap">'
                                                 f'{explanation_panel(view)}</main>')
                                details = page.locator('details')
                                summary = page.locator('summary')
                                self.assertFalse(details.evaluate('(el) => el.open'))
                                self.assertGreaterEqual(summary.bounding_box()['height'], 44)
                                summary.focus()
                                summary.press('Enter')
                                self.assertTrue(details.evaluate('(el) => el.open'))
                                self.assertIn('Unavailable', details.inner_text())
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                summary.press('Space')
                                self.assertFalse(details.evaluate('(el) => el.open'))
                            finally:
                                page.close()
            finally:
                browser.close()
