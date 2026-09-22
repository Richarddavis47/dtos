"""Bounded candidate-only season navigation and touch/keyboard proof."""
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright

from services.matchup_season import season_week_view
from src.ui.matchup_season import render_season_week, render_desk
from services.matchup_desk import matchup_desk
from tests.test_batch6_matchup_season import fixture


class SeasonBrowserTests(unittest.TestCase):
    def test_desk_modes_disclosure_and_optional_banter(self):
        from dtos_app import CSS
        data, service, _ = fixture()
        data['season_matchups']['weeks']['2']['rows'][0]['points'] = 12
        css = Path('static/css/matchups.css').read_text(encoding='utf-8')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for width in (390, 1280):
                    page = browser.new_page(viewport={'width': width, 'height': 900})
                    for week, mode in ((3, 'pregame'), (2, 'live'), (1, 'postgame')):
                        view = season_week_view(data, week, service)
                        body = render_season_week(view, matchup_id='1') + render_desk(matchup_desk(data, view, '1'))
                        page.set_content(f'<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}\n{css}</style></head><body><main class="wrap">{body}</main></body></html>')
                        root = page.locator(f'[data-desk-mode="{mode}"]')
                        summary = root.locator('summary').first
                        self.assertGreaterEqual(summary.bounding_box()['height'], 44)
                        summary.focus()
                        summary.press('Enter')
                        self.assertTrue(root.locator('details').first.evaluate('(e) => e.open'))
                        if mode == 'pregame':
                            banter = root.get_by_text('Optional banter', exact=True)
                            banter.focus()
                            banter.press('Enter')
                            self.assertTrue(banter.evaluate('(e) => e.parentElement.open'))
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    page.close()
            finally:
                browser.close()

    def test_selected_week_navigation_and_identity_links(self):
        from dtos_app import CSS
        data, service, _ = fixture()
        data['teams'][0]['team_name'] = 'A deliberately long franchise name that must wrap safely'
        body = render_season_week(season_week_view(data, 3, service), matchup_id='1')
        css = Path('static/css/matchups.css').read_text(encoding='utf-8')
        html = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<style>{CSS}\n{css}</style></head><body><main class="wrap"><h1>Week 3</h1>{body}</main></body></html>')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for width in (375, 390, 1280):
                    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
                        def transport(route):
                            if route.request.url == 'https://dtos.test/matchups/1?week=3':
                                route.fulfill(status=200, content_type='text/html', body=html)
                            elif route.request.url.startswith('https://dtos.test/static/'):
                                route.fulfill(status=200, content_type='text/css', body=css)
                            else:
                                route.fulfill(status=200, content_type='text/html', body='<h1>Destination</h1>')
                        context.route('**/*', transport)
                        page = context.new_page()
                        url = 'https://dtos.test/matchups/1?week=3'
                        page.goto(url)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        for link in (page.get_by_role('link', name='Open Player 1 player dossier', exact=True),
                                     page.get_by_role('link', name='Next week', exact=True)):
                            self.assertGreaterEqual(link.bounding_box()['height'], 44)
                        player = page.get_by_role('link', name='Open Player 1 player dossier', exact=True)
                        player.focus()
                        player.press('Enter')
                        self.assertEqual(page.url, 'https://dtos.test/players/1')
                        page.goto(url)
                        page.get_by_label('Week', exact=True).select_option('4')
                        page.get_by_role('button', name='Go to week', exact=True).click()
                        self.assertEqual(page.url, 'https://dtos.test/matchups?week=4')
                        page.goto(url)
                        page.get_by_role('link', name=data['teams'][0]['team_name'], exact=True).click()
                        self.assertEqual(page.url, 'https://dtos.test/teams/1')
                        page.goto(url)
                        page.get_by_role('link', name='All Week 3 matchups', exact=True).click()
                        self.assertEqual(page.url, 'https://dtos.test/matchups?week=3')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
