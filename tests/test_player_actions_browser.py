"""Responsive Chromium ownership/action acceptance; no physical Safari claim."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from src.core.asset_market import AssetMarketCache
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from src.core.historical_memory.store import HistoricalStore
from tests.test_canonical_asset_facts import facts_fixture
from tests.test_market_render_cache import _Cache
from tests.test_player_actions import player_app
from tools.validation.browser_runtime import launch_chromium


class PlayerActionsBrowserTests(unittest.TestCase):
    def test_phone_and_desktop_ownership_and_action_readability(self):
        import dtos_app
        data = facts_fixture()
        with TemporaryDirectory() as folder, patch.object(data_platform, 'warehouse', SnapshotWarehouse()):
            cache = AssetMarketCache()
            try:
                market = cache.get(data, {'data':data}, HistoricalStore(Path(folder)/'history.sqlite3'), 'league-1')
                with patch('routes.market.asset_market_cache', _Cache(market)), TestClient(player_app(data, page=dtos_app.page)) as client:
                    pages = {}
                    for pid in ('free', '10225', '1-QB-0'):
                        pages[f'/players/{pid}'] = client.get(f'/players/{pid}?front_office=1').text
                        pages[f'/market/{pid}'] = client.get(f'/market?front_office=1&selected=player:{pid}').text
                    data['teams'][1]['team_name'] = 'Franchise' * 24
                    pages['/players/long-owner'] = client.get('/players/10225?front_office=1').text
                    pages['/market/long-owner'] = client.get('/market?front_office=1&selected=player:10225').text
                    data['league']['total_rosters'] = 10
                    pages['/players/unknown'] = client.get('/players/free?front_office=1').text
                    blocked = client.get('/trades/trade-for?front_office=1&asset_id=free')
                    self.assertEqual(blocked.status_code, 422)
                    pages['/trades/blocked'] = blocked.text
                styles = {p.name:p.read_text() for p in Path('static/css').glob('*.css')}
                with sync_playwright() as pw:
                    browser = launch_chromium(pw, headless=True)
                    try:
                        for width in (320, 375, 390, 1440):
                            with browser.new_context(viewport={'width':width, 'height':900}) as context:
                                def transport(route):
                                    path = urlsplit(route.request.url).path
                                    if path in pages:
                                        route.fulfill(content_type='text/html', body=pages[path])
                                    elif path.endswith('.css'):
                                        route.fulfill(content_type='text/css', body=styles.get(Path(path).name,''))
                                    else:
                                        route.fulfill(status=404)
                                context.route('**/*', transport)
                                page = context.new_page()
                                for path in pages:
                                    with self.subTest(width=width, path=path):
                                        page.goto('https://dtos.test' + path)
                                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width+1)
                                        if path == '/trades/blocked':
                                            self.assertIn('Player action unavailable', page.locator('body').inner_text())
                                            self.assertEqual(page.locator('#trade-builder').count(), 0)
                                            continue
                                        ownership = page.locator('.player-ownership').first
                                        self.assertTrue(ownership.is_visible())
                                        self.assertEqual(ownership.locator(".player-ownership-label").evaluate("el=>getComputedStyle(el).overflowWrap"), "anywhere")
                                        if path.endswith('free'):
                                            self.assertIn('Free Agent', ownership.inner_text())
                                            self.assertEqual(ownership.locator('a').count(), 0)
                                            self.assertEqual(ownership.locator('.ds-actions').count(), 0)
                                        elif path.endswith('unknown'):
                                            self.assertIn('Ownership unavailable', ownership.inner_text())
                                            self.assertEqual(ownership.locator('a').count(), 0)
                                        else:
                                            if path.endswith('long-owner'):
                                                self.assertIn('Franchise' * 24, ownership.inner_text())
                                            label = 'Shop Asset' if path.endswith('1-QB-0') else 'Trade For'
                                            action = ownership.get_by_role('link', name=label, exact=True)
                                            self.assertTrue(action.is_visible())
                                            box = action.bounding_box()
                                            self.assertLessEqual(box['x']+box['width'], width+1)
                                            action.focus()
                                            self.assertTrue(action.evaluate('(el)=>el===document.activeElement'))
                                        if path.startswith('/players/'):
                                            self.assertNotIn('Current projections: None', page.locator('body').inner_text())
                    finally:
                        browser.close()
            finally:
                cache.wait_for_background()
                cache.clear()


if __name__ == '__main__':
    unittest.main()
