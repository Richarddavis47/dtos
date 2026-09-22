"""Bounded mobile/desktop week-navigation acceptance using the shipped script."""
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from services.player_projection_view import player_projection_view
from src.ui.player_projections import player_projection_panel
from src.ui.design_system import player_summary
from tests import test_batch6_player_projection_view as fixtures


class PlayerProjectionBrowserTests(unittest.TestCase):
    def test_week_change_keyboard_missing_and_compact_card(self):
        from dtos_app import CSS
        data, service, _ = fixtures.PlayerProjectionViewTests().prepared()
        original = service.week_snapshot
        def week_snapshot(week, **kwargs):
            result = original(week, **kwargs)
            if week == 5:
                result = {**result, 'players': {}}
            return result
        service.week_snapshot = week_snapshot
        css = CSS + Path('static/css/matchups.css').read_text(encoding='utf-8')
        script = Path('static/js/player-projections.js').read_text(encoding='utf-8')
        def panel(week):
            return player_projection_panel(player_projection_view(data, '2', service, week), 1)
        card = player_summary(player_id='2', name='Representative Player', position='QB', nfl_team='BUF',
            projection=player_projection_view(data, '2', service, 3))
        html = f'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body><main class="wrap"><a id="compact-card" href="/players/2">{card}</a>{panel(3)}</main></body></html>'
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for width in (375, 390, 1280):
                    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
                        reads = []
                        def transport(route):
                            path = urlparse(route.request.url)
                            if path.path.endswith('player-projections.js'):
                                route.fulfill(content_type='text/javascript', body=script)
                            elif path.path.endswith('.css'):
                                route.fulfill(content_type='text/css', body=css)
                            elif path.path.endswith('/projections'):
                                week = int(parse_qs(path.query)['week'][0])
                                reads.append(week)
                                route.fulfill(content_type='text/html', body=panel(week))
                            elif path.path == '/players/2':
                                route.fulfill(content_type='text/html', body=html)
                            else:
                                route.fulfill(status=404)
                        context.route('**/*', transport)
                        page = context.new_page()
                        page.goto('https://dtos.test/players/2?week=3&front_office=1')
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        self.assertLess(page.locator('#compact-card').bounding_box()['height'], 120)
                        button = page.get_by_role('button', name='Show projection')
                        self.assertGreaterEqual(button.bounding_box()['height'], 44)
                        page.get_by_label('Week', exact=True).select_option('5')
                        button.focus()
                        button.press('Enter')
                        page.wait_for_function("document.querySelector('[data-projection-week=\"5\"]') !== null")
                        self.assertIn('Unavailable', page.locator('#player-weekly-projections').inner_text())
                        self.assertEqual(reads, [5])
                        self.assertEqual(page.locator('#player-projection-week').evaluate('(el) => el === document.activeElement'), True)
                        self.assertEqual(data['week'], 2)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            finally:
                browser.close()
