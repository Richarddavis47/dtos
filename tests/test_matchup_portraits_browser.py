"""Actual rendered matchup portrait states and adjacent-text geometry."""
import unittest
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.matchups import create_matchups_router
from src.ui import player_summary
from tests.test_matchups_phone import phone_fixture
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_runtime import launch_chromium


class MatchupPortraitBrowserTests(unittest.TestCase):
    def test_loaded_loading_failed_and_fallback_geometry(self):
        import dtos_app
        f = phone_fixture(self)
        data = f.data
        names = ('A very long fully readable player identity', 'Failed portrait identity',
                 'Loading portrait identity', 'Fallback only identity', 'Loaded opponent identity')
        for i, (pid, metadata) in enumerate(data['players'].items()):
            metadata.update(full_name=names[i % len(names)], status='Questionable · long availability explanation', team='BUF')
        # No canonical metadata means the production renderer omits the image URL.
        del data['players']['e']
        data['season_matchups']['weeks']['2']['rows'][0]['starters'].append('0')
        data['roster_positions'] = ['QB', 'SUPER_FLEX']
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda:data, page=dtos_app.page))
        app.mount('/static', StaticFiles(directory='static'), name='static')
        context = SimpleNamespace(projection=f.reader, data=data)
        account = SimpleNamespace(membership=SimpleNamespace(league_id='league-1', roster_id=1))
        with patch('routes.matchups.current_league_context', return_value=context), patch('routes.matchups.current_account', return_value=account), patch('src.ui.badges.current_account', return_value=account), sync_playwright() as p:
            client = TestClient(app)
            browser = launch_chromium(p, headless=True)
            try:
                for width, height in ((320,483), (320,844), (375,432), (375,812), (390,677), (390,844), (1280,757)):
                    with self.subTest(width=width, height=height), browser.new_context(viewport={'width':width, 'height':height}) as bc:
                        pending = []
                        hold_loading = [True]
                        def transport(route):
                            url = urlsplit(route.request.url)
                            if url.hostname == 'sleepercdn.com':
                                if url.path.endswith('/b.jpg'):
                                    route.abort('failed')
                                elif url.path.endswith('/c.jpg') and hold_loading[0]:
                                    pending.append(route)
                                else:
                                    route.fulfill(status=200, content_type='image/png', body=image_bytes('portrait'))
                            elif url.hostname == 'dtos.test':
                                response = client.get(url.path + ('?' + url.query if url.query else ''))
                                route.fulfill(status=response.status_code, content_type=response.headers.get('content-type','text/html'), body=response.content)
                            else:
                                route.abort()
                        bc.route('**/*', transport)
                        page = bc.new_page()
                        page.goto('https://dtos.test/matchups/2?week=2', wait_until='domcontentloaded')
                        page.locator('.matchup-player img[src$="/a.jpg"]').scroll_into_view_if_needed()
                        page.wait_for_function('s=>document.querySelector(s).naturalWidth > 0', arg='.matchup-player img[src$="/a.jpg"]')
                        failed = page.locator('.matchup-player img[src$="/b.jpg"]')
                        failed.locator('..').scroll_into_view_if_needed()
                        page.wait_for_function('s=>document.querySelector(s).hidden', arg='.matchup-player img[src$="/b.jpg"]')
                        loading = page.locator('.matchup-player img[src$="/c.jpg"]')
                        loading.scroll_into_view_if_needed()
                        self.assertFalse(loading.evaluate('e=>e.complete'))
                        self.assertGreater(len(pending), 0)
                        self.assertGreater(page.locator('.matchup-player .player-portrait:not(:has(img))').count(), 0)
                        self.geometry(page)
                        hold_loading[0] = False
                        for route in pending:
                            route.fulfill(status=200, content_type='image/png', body=image_bytes('portrait'))
                        page.wait_for_function('s=>document.querySelector(s).naturalWidth > 0', arg='.matchup-player img[src$="/c.jpg"]')
                        self.geometry(page)
                        for section in ('lineup','bench','reserve','taxi'):
                            self.assertTrue(page.locator('[data-roster-section="'+section+'"]').is_visible())
                        self.assertIn('Projection unavailable', page.locator('.matchup-roster').all_inner_texts()[0])
                        self.assertGreater(page.locator('.matchup-player-points small').filter(has_text='Actual').count(), 0)
                        self.assertGreater(page.locator('.matchup-player [data-dtos-availability="available"]').count(), 0)
                        self.assertIn(names[0], page.locator('.matchup-player').all_inner_texts()[0])
                        self.assertTrue(page.locator('.matchup-player .player-summary-copy').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth)'))
                        link = page.locator('.matchup-player-link').first
                        link.scroll_into_view_if_needed()
                        link.focus()
                        self.assertNotEqual(link.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                        self.assertTrue(link.evaluate('e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'))
                        href = link.get_attribute('href')
                        # Observe native keyboard navigation without requiring another dossier engine.
                        bc.route('**/players/**', lambda r:r.fulfill(status=200, body='Canonical dossier navigation'))
                        link.press('Enter')
                        self.assertTrue(page.url.endswith(href))
                        page.go_back(wait_until='domcontentloaded')
                        self.geometry(page)
                        # Existing shared portrait contract on non-matchup pages stays 52px.
                        page.evaluate('(html)=>{let d=document.createElement("div");d.id="shared-portrait-control";d.innerHTML=html;document.body.append(d)}', player_summary(player_id='',name='Shared player',position='WR',nfl_team='BUF'))
                        for selector in ('.player-portrait', '.player-headshot-fallback'):
                            box = page.locator('#shared-portrait-control '+selector).bounding_box()
                            self.assertEqual((box['width'],box['height']), (52,52))
            finally:
                browser.close()

    def geometry(self, page):
        evidence = page.locator('.matchup-player .player-portrait').evaluate_all('''nodes=>nodes.map(e=>{
            const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom}};
            const wrapper=rect(e), fallback=rect(e.querySelector('.player-headshot-fallback'));
            const image=e.querySelector('img');
            const copy=e.parentElement.querySelector('.player-summary-copy');
            const text=[copy,...copy.querySelectorAll('b,span'),...e.closest('.matchup-player').querySelectorAll('.matchup-player-points small,.matchup-player-points b')].map(rect);
            return {wrapper,fallback,image:image&&!image.hidden?rect(image):null,text,fit:image?getComputedStyle(image).objectFit:null};
        })''')
        self.assertGreater(len(evidence), 1)
        for item in evidence:
            wrapper = item['wrapper']
            self.assertEqual((wrapper['w'],wrapper['h']), (28,28))
            for graphic in (item['fallback'], item['image']):
                if graphic is None:
                    continue
                self.assertEqual((graphic['w'],graphic['h']), (28,28))
                self.assertGreaterEqual(graphic['x'],wrapper['x'])
                self.assertGreaterEqual(graphic['y'],wrapper['y'])
                self.assertLessEqual(graphic['right'],wrapper['right'])
                self.assertLessEqual(graphic['bottom'],wrapper['bottom'])
                for text in item['text']:
                    intersects = min(graphic['right'],text['right'])-max(graphic['x'],text['x']) > .1 and min(graphic['bottom'],text['bottom'])-max(graphic['y'],text['y']) > .1
                    self.assertFalse(intersects, item)
            if item['fit']:
                self.assertEqual(item['fit'], 'cover')
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), page.viewport_size['width'])
