"""Full technical evidence stays selectable and viewport-bounded in Chromium."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from app_metadata import VERSION
from routes.market import create_market_router
from routes.transactions import create_transactions_router
from src.core.asset_market import AssetMarketCache
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from src.core.historical_memory.store import HistoricalStore
from src.ui.intelligence_presentation import technical_details
from tests.test_canonical_asset_facts import facts_fixture
from tests.test_market_render_cache import _Cache
from tools.validation.browser_runtime import launch_chromium


LONG_BRAIN = VERSION + ':' + 'a' * 64 + ':' + 'b' * 20
LONG_HASH = '0123456789abcdef' * 16
WIDTHS = (320, 375, 390, 1280, 1440)


class TechnicalDetailsBrowserTests(unittest.TestCase):
    def browse(self, pages, inspect):
        styles = {p.name: p.read_text() for p in Path('static/css').glob('*.css')}
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width in WIDTHS:
                    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
                        def transport(route):
                            from urllib.parse import urlsplit
                            url = urlsplit(route.request.url)
                            key = url.path + ('?' + url.query if url.query else '')
                            if key in pages:
                                route.fulfill(content_type='text/html', body=pages[key])
                            elif url.path.endswith('.css'):
                                route.fulfill(content_type='text/css', body=styles.get(Path(url.path).name, ''))
                            else:
                                route.fulfill(status=404)
                        context.route('**/*', transport)
                        page = context.new_page()
                        for path in pages:
                            with self.subTest(width=width, route=path):
                                page.goto('https://dtos.test' + path)
                                inspect(page, width)
            finally:
                browser.close()

    def assert_bounded(self, page, width):
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
        self.assertLessEqual(page.evaluate('document.body.scrollWidth'), width + 1)

    def assert_selectable(self, code):
        expected = code.text_content()
        selected = code.evaluate('''el => {
            const range=document.createRange(); range.selectNodeContents(el);
            const selection=getSelection(); selection.removeAllRanges(); selection.addRange(range);
            return selection.toString();
        }''')
        self.assertEqual(selected, expected)
        self.assertNotEqual(code.evaluate('el=>getComputedStyle(el).userSelect'), 'none')

    def test_real_market_and_player_disclosures_closed_and_open(self):
        import dtos_app
        data = facts_fixture()
        async def fresh():
            pass
        with tempfile.TemporaryDirectory() as folder:
            store = HistoricalStore(Path(folder) / 'history.sqlite3')
            cache = AssetMarketCache()
            try:
                market = cache.get(data, {'data': data}, store, 'league-1')
                original = market.detail
                def detail(*args, **kwargs):
                    row = original(*args, **kwargs)
                    # Exercise a production-shaped unbroken diagnostic value;
                    # pricing, ownership and canonical fact payloads are untouched.
                    row['recommendation']['brain_snapshot_id'] = LONG_BRAIN
                    return row
                market.detail = detail
                app = FastAPI()
                app.include_router(create_market_router(require_data=lambda: data, state={'data': data},
                    league_id='league-1', page=lambda title, body: dtos_app.page(title, body)))
                app.include_router(create_transactions_router(ensure_fresh=fresh, require_data=lambda: data,
                    refresh_transactions=fresh, state={}, page=lambda title, body: dtos_app.page(title, body)))
                with patch('routes.market.asset_market_cache', _Cache(market)), \
                        patch.object(data_platform, 'warehouse', SnapshotWarehouse()), TestClient(app) as client:
                    paths = ('/market?selected=player:10225', '/market?selected=player:4984', '/players/10225')
                    pages = {}
                    for path in paths:
                        response = client.get(path)
                        self.assertEqual(response.status_code, 200)
                        pages[path] = response.text
                def inspect(page, width):
                    details = page.locator('.technical-details')
                    self.assertGreater(details.count(), 0)
                    self.assertEqual(details.evaluate_all('rows=>rows.every(el=>!el.open)'), True)
                    self.assert_bounded(page, width)
                    for disclosure in details.all():
                        disclosure.locator('summary').first.click()
                        self.assertTrue(disclosure.evaluate('el=>el.open'))
                        self.assert_bounded(page, width)
                    page.locator('.market-fact details').evaluate_all('rows=>rows.forEach(el=>el.open=true)')
                    self.assert_bounded(page, width)
                    for code in page.locator('.technical-details code, .market-fact code').all():
                        self.assert_selectable(code)
                        self.assertLessEqual(code.evaluate('el=>el.getBoundingClientRect().right'), width + 1)
                    if page.locator('#selected-asset').count():
                        brain = page.locator('#selected-asset .technical-details code').nth(1)
                        self.assertEqual(brain.text_content(), LONG_BRAIN)
                        # Wide evidence tables retain local scroll, including at 320px.
                        table_wrap = page.locator('.technical-details > div').first
                        self.assertEqual(table_wrap.evaluate('el=>getComputedStyle(el).overflowX'), 'auto')
                        table_wrap.evaluate('el=>el.scrollLeft=el.scrollWidth')
                        self.assert_bounded(page, width)
                    print(f'Technical Details responsive Chromium: viewport={width}, page={page.evaluate("document.documentElement.scrollWidth")}, closed/open PASS')
                self.browse(pages, inspect)
            finally:
                cache.wait_for_background()
                cache.clear()

    def test_shared_definition_list_long_hash_and_short_values(self):
        import dtos_app
        rows = (('Brain snapshot', LONG_BRAIN), ('Source generation', 'f' * 64),
                ('Source identity / fingerprint', LONG_HASH), ('Model', '5.1'), ('Status', 'Available'))
        # Same helper/class used by dossier career evidence, GM profiles and pick identity.
        html = dtos_app.page('Technical evidence', '<section class="card">'
            + technical_details(rows) + '</section>')
        if not isinstance(html, str):
            html = html.body.decode()
        def inspect(page, width):
            self.assert_bounded(page, width)
            details = page.locator('.technical-details')
            details.locator('summary').click()
            self.assert_bounded(page, width)
            self.assertEqual(page.locator('dt').all_text_contents(), [label for label, _ in rows])
            self.assertEqual(page.locator('dd code').all_text_contents(), [value for _, value in rows])
            for code in page.locator('dd code').all():
                code.scroll_into_view_if_needed()
                self.assert_selectable(code)
                bounds = code.bounding_box()
                self.assertGreaterEqual(bounds['x'], 0)
                self.assertLessEqual(bounds['x'] + bounds['width'], width + 1)
            details.locator('summary').click()
            self.assert_bounded(page, width)
        self.browse({'/technical': html}, inspect)
