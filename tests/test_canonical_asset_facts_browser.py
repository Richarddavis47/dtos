"""Responsive Chromium contract; not physical iPhone or Safari acceptance."""
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from routes.transactions import create_transactions_router
from tests.test_canonical_asset_facts import facts_fixture
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from tools.validation.browser_runtime import launch_chromium


class CanonicalAssetFactsBrowserTests(unittest.TestCase):
    def test_responsive_chromium_375_and_390_value_reason_and_disclosure(self):
        import dtos_app
        data = facts_fixture()
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_transactions_router(ensure_fresh=fresh, require_data=lambda: data,
            refresh_transactions=fresh, state={}, page=lambda title, body: dtos_app.page(title, body)))
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), TestClient(app) as client:
            pages = {pid: client.get('/players/' + pid + '?front_office=1').text for pid in ('4984', '10225', 'missing')}
        styles = {p.name: p.read_text() for p in Path('static/css').glob('*.css')}
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width in (375, 390):
                    with browser.new_context(viewport={'width': width, 'height': 844}) as context:
                        def transport(route):
                            from urllib.parse import urlsplit
                            path = urlsplit(route.request.url).path
                            if path.startswith('/players/'):
                                route.fulfill(content_type='text/html', body=pages[path.split('/')[-1]])
                            elif path.endswith('.css'):
                                route.fulfill(content_type='text/css', body=styles.get(Path(path).name, ''))
                            else:
                                route.fulfill(status=404)
                        context.route('**/*', transport)
                        page = context.new_page()
                        for pid in ('4984', '10225', 'missing'):
                            with self.subTest(width=width, player=pid):
                                page.goto('https://dtos.test/players/' + pid)
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                market = page.locator('.ai-values .ai-value').nth(2)
                                self.assertTrue(market.is_visible())
                                if pid == 'missing':
                                    self.assertIn('Unavailable', market.inner_text())
                                    self.assertIn('No supported Market evidence', market.inner_text())
                                else:
                                    self.assertNotIn('Unavailable', market.locator('b').first.inner_text())
                                self.assertFalse(market.locator('.market-fact details').evaluate('(el) => el.open'))
                                market.get_by_text('Market evidence', exact=True).click()
                                self.assertIn('Source generation:', market.inner_text())
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                                headlines = page.locator('.market-fact').evaluate_all('(rows) => rows.map(r => r.dataset.marketGeneration)')
                                self.assertGreaterEqual(len(headlines), 2)
                                self.assertEqual(len(set(headlines)), 1)
                                self.assertNotIn('Current projections: None', page.locator('body').inner_text())
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
