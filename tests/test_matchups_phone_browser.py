"""Actual rendered product routes with pointer/keyboard and week-return proof."""
import unittest
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright

from routes.home import create_home_router
from routes.matchups import create_matchups_router
from routes.transactions import create_transactions_router
from tests.test_matchups_phone import phone_fixture
from tools.validation.browser_fixture_images import image_bytes
from tools.validation.browser_runtime import launch_chromium


class MatchupsPhoneBrowserTests(unittest.TestCase):
    def test_actual_overview_detail_dossier_and_standings_journeys(self):
        import dtos_app
        f = phone_fixture(self)
        data = f.data
        for t in data['teams']:
            t['team_name'] = 'A long franchise identity with full readable text ' + str(t['roster_id'])
            t['official_standing_rank'] = t['roster_id']
            pid = 'bench' + str(t['roster_id'])
            t['players'].append({'id':pid,'name':'Opponent bench identity','position':'WR','roster_slot':'Bench'})
            data['players'][pid] = {'full_name':'Opponent bench identity '+str(t['roster_id']), 'position':'WR', 'team':'BUF'}
        async def fresh():
            pass
        app=FastAPI()
        common=dict(ensure_fresh=fresh, require_data=lambda:data,page=dtos_app.page)
        app.include_router(create_matchups_router(**common))
        app.include_router(create_home_router(**common))
        app.include_router(create_transactions_router(**common,refresh_transactions=fresh,state={}))
        app.mount('/static', StaticFiles(directory='static'), name='static')
        context = SimpleNamespace(projection=f.reader, data=data, state={'data':data,'last_sync':'controlled fixture'})
        account = SimpleNamespace(membership=SimpleNamespace(league_id='league-1',roster_id=1))
        with patch('routes.matchups.current_league_context',return_value=context), patch('routes.transactions.current_league_context',return_value=context), patch('routes.matchups.current_account',return_value=account), patch('src.ui.badges.current_account',return_value=account), patch.object(dtos_app,'current_league_context',return_value=context), patch('services.sleeper.sleeper_get',side_effect=AssertionError('No provider calls on page reads')), sync_playwright() as p:
            client=TestClient(app)
            browser=launch_chromium(p,headless=True)
            try:
                for width,height in ((320,483),(320,844),(375,432),(375,812),(390,677),(390,844),(1280,757)):
                    with browser.new_context(viewport={'width':width,'height':height}) as bc:
                        def transport(route):
                            url=urlsplit(route.request.url)
                            if url.hostname=='sleepercdn.com':
                                route.fulfill(status=200,content_type='image/png',body=image_bytes('matchups'))
                            elif url.hostname=='dtos.test':
                                response=client.get(url.path+('?' + url.query if url.query else ''))
                                route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','text/html'),body=response.content)
                            else:
                                route.abort()
                        bc.route('**/*',transport)
                        page=bc.new_page()
                        page.goto('https://dtos.test/matchups')
                        self.assertIn('Week 2',page.locator('.matchup-heading').inner_text())
                        first=page.locator('.matchup-card-link').first
                        self.assertIn('/matchups/2?week=2',first.get_attribute('href'))
                        self.hit(page,first)
                        first.focus()
                        self.assertNotEqual(first.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                        first.press('Enter')
                        self.assertTrue(page.url.endswith('/matchups/2?week=2'))
                        for section in ('lineup','bench','reserve','taxi'):
                            self.assertTrue(page.locator('[data-roster-section="'+section+'"]').is_visible())
                        bench=page.get_by_role('link',name='Open Opponent bench identity 2 player dossier',exact=True)
                        self.hit(page,bench)
                        bench.click()
                        self.assertTrue(page.url.endswith('/players/bench2?week=2&matchup=2'))
                        back=page.get_by_role('link',name='Back to Week 2 matchup')
                        self.hit(page,back)
                        back.click()
                        self.assertTrue(page.url.endswith('/matchups/2?week=2'))
                        self.no_overflow(page,width)
                        page.get_by_role('link',name='All Week 2 matchups',exact=True).click()
                        page.get_by_role('link',name='Next week',exact=True).click()
                        self.assertTrue(page.url.endswith('/matchups?week=3'))
                        page.get_by_label('Week',exact=True).select_option('1')
                        page.get_by_role('button',name='Go to week',exact=True).click()
                        self.assertTrue(page.url.endswith('/matchups?week=1'))
                        page.locator('.matchup-card-link').first.click()
                        self.assertTrue(page.url.endswith('/matchups/2?week=1'))
                        page.go_back()
                        self.assertTrue(page.url.endswith('/matchups?week=1'))
                        for path in ('/','/league'):
                            page.goto('https://dtos.test'+path)
                            self.no_overflow(page,width)
                            table=page.locator('.compact-standings')
                            self.assertEqual(table.count(),1)
                            self.assertIn('123.45',table.inner_text())
                            self.assertIn('110.67',table.inner_text())
                            self.assertEqual(table.locator('.standings-you').count(),1)
                            details=page.get_by_text('Standings and playoff evidence',exact=True)
                            details.focus()
                            details.press('Enter')
                            self.assertTrue(details.evaluate('e=>e.parentElement.open'))
                            self.no_overflow(page,width)
            finally:
                browser.close()

    def hit(self,page,element):
        element.scroll_into_view_if_needed()
        box=element.bounding_box()
        self.assertGreaterEqual(box['height'],44)
        point={'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}
        self.assertTrue(element.evaluate('(e,p)=>e===document.elementFromPoint(p.x,p.y)||e.contains(document.elementFromPoint(p.x,p.y))',point))

    def no_overflow(self,page,width):
        for label in ('Lineup and projection evidence','Source and coverage'):
            disclosure=page.get_by_text(label,exact=True)
            if disclosure.count() and not disclosure.evaluate('e=>e.parentElement.open'):
                disclosure.focus()
                disclosure.press('Enter')
                self.assertTrue(disclosure.evaluate('e=>e.parentElement.open'))
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
