"""Actual route/rendering acceptance at short and realistic portrait heights."""
from urllib.parse import urlsplit
from dataclasses import replace
from unittest.mock import AsyncMock, patch
import unittest

from fastapi.testclient import TestClient
from fastapi import FastAPI
from playwright.sync_api import sync_playwright

from routes.trades import create_trades_router
from routes.historical_assets import create_historical_assets_router
from tests import test_trade_workspace_batch1 as boundary
from tests import test_product_browser_journey as journey
from tests import test_historical_asset_graph as history
from tests import test_market_render_cache as market
from tests import test_fois_presentation as fois
from routes.fois import create_fois_router
from routes.market import create_market_router
from tools.validation.browser_runtime import launch_chromium


class JourneyPlacementBrowserTests(journey.ProductBrowserJourneyTests):
    viewports = tuple({'width': width, 'height': height}
                      for width in (320, 375, 390, 1280)
                      for height in ((483, 844) if width < 760 else (900,)))

    def audit_page(self, page, path, viewport):
        if path == '/trades/recommended':
            discover = page.locator('#trade-find')
            self.assertLess(discover.bounding_box()['y'], viewport['height'] * 1.5)
            self.assertLess(discover.bounding_box()['y'], page.locator('#trade-board').bounding_box()['y'])
            self.assertIn('eligible teams', page.locator('#trade-builder').inner_text())
        if path == '/trades/calculator':
            jump = page.get_by_role('link', name='Market totals & Balance')
            self.assertLess(jump.bounding_box()['y'], viewport['height'] * 1.5)
            jump.click()
            self.assertGreaterEqual(page.locator('#trade-balance').bounding_box()['y'], -1)
            self.assertLess(page.locator('#trade-balance').bounding_box()['y'], viewport['height'] - 100)
        if path == '/teams/1':
            access = page.get_by_role('link', name='View full roster')
            self.assertLess(access.bounding_box()['y'], viewport['height'] * 1.5)
            access.click()
            roster = page.get_by_text('Full Roster · position rooms and current lineup designation', exact=True)
            roster.click()
            self.assertTrue(page.locator('.thq-roster').is_visible())


class EvaluateLandingBrowserTests(unittest.TestCase):
    def test_actual_evaluation_verdict_landing_and_shop_scope(self):
        import dtos_app
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.data['teams'][0]['team_name'] = 'Chase Bank'
        fixture.data['teams'][1]['team_name'] = 'Runaway McBride'
        fixture.data['teams'][0]['players'][0]['name'] = 'Bo Nix'
        fixture.data['teams'][1]['players'][0]['name'] = 'Joe Burrow'
        fixture.data['players']['1-QB-0']['full_name'] = 'Bo Nix'
        fixture.data['players']['2-QB-0']['full_name'] = 'Joe Burrow'
        fixture.client.app.router.routes.clear()
        fixture.client.app.include_router(create_trades_router(
            ensure_fresh=AsyncMock(), require_data=lambda: fixture.data, page=dtos_app.page,
        ))
        self.addCleanup(fixture.client.close)
        with patch.object(dtos_app, 'account_store', fixture.store), sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width in (320, 375, 390, 1280):
                    for height in ((432, 677, 844) if width < 760 else (900,)):
                        with self.subTest(width=width, height=height):
                            page = browser.new_page(viewport={'width': width, 'height': height})

                            def transport(route):
                                request = route.request
                                url = urlsplit(request.url)
                                if url.netloc != 'dtos.test':
                                    return route.abort()
                                response = fixture.client.request(request.method, url.path + ('?' + url.query if url.query else ''),
                                    content=request.post_data, headers={k: v for k, v in request.headers.items()
                                                                      if k in ('content-type', 'x-csrf-token')})
                                route.fulfill(status=response.status_code,
                                              content_type=response.headers.get('content-type', 'text/html'), body=response.content)

                            page.route('**/*', transport)
                            page.goto('https://dtos.test/trades/create')
                            page.select_option('#trade-partner', '2')
                            page.locator('#trade-sent-board button[data-asset-id="1-QB-0"]').click()
                            if width < 760:
                                page.click('[data-side=received]')
                            page.locator('#trade-received-board button[data-asset-id="2-QB-0"]').click()
                            page.click('#trade-view')
                            page.click('#trade-run')
                            page.locator('#trade-result .dtos-explanation').wait_for()
                            page.wait_for_function('!document.querySelector("#trade-run").disabled')
                            verdict = page.locator('#trade-result .dtos-explanation > p').first
                            box = verdict.bounding_box()
                            nav = page.locator('.manager-nav').bounding_box()
                            self.assertGreaterEqual(box['y'], 0)
                            self.assertLessEqual(box['y'] + box['height'], nav['y'] if width < 760 else height)
                            self.assertEqual(page.evaluate('document.activeElement.id'), 'trade-result')
                            self.assertNotIn('Why DTOS recommends this', page.locator('#trade-result').inner_text())
                            self.assertIn('DTOS trade assessment', page.locator('#trade-result').inner_text())
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            # Explicit new Shop entry must replace the old partner
                            # while retaining exact protections under existing intent rules.
                            page.goto('https://dtos.test/trades/shop?asset_id=1-QB-0')
                            page.locator('#trade-target').wait_for()
                            self.assertEqual(page.locator('#trade-partner').input_value(), '')
                            self.assertEqual(page.locator('#trade-partner option:checked').inner_text(), 'All eligible teams')
                            self.assertIn('All eligible teams', page.locator('#trade-context').inner_text())
                            self.assertIn('optional', page.locator('#shop-partner-help').inner_text())
                            self.assertIn('Bo Nix', page.locator('#trade-target').inner_text())
                            if width == 390 and height == 677:
                                # Deterministic source-limited assessment, not a claim
                                # that every current live search returns this state.
                                from services.trade_search_policy import SearchFunnel
                                assessed = fixture._post().json()
                                assessed['evaluation']['recommendation'] = None
                                assessed['evaluation']['generated_trade_eligible'] = False
                                assessed['evaluation']['recommendation_trace']['rule_reasons'] = ['SUPPORTED_TEAM_IMPACT_UNAVAILABLE']
                                assessed['evaluation']['market_evidence']['availability'] = 'unavailable'
                                funnel = SearchFunnel(180)
                                funnel.assessed(assessed)
                                response = {'workflow': 'recommended', 'results': [], 'count': 0,
                                            'has_more': False, 'near_misses': funnel.near_misses,
                                            'quiet_state': 'Required team impact unavailable.'}
                                with patch('routes.trades.generate_trade_workflow', return_value=response):
                                    page.goto('https://dtos.test/trades/recommended')
                                    page.locator('#trade-find').click()
                                    page.wait_for_function('!document.querySelector("#trade-find").disabled')
                                near = page.get_by_text('Evaluated near misses', exact=True)
                                near.click()
                                self.assertIn('cannot supply or upload', page.locator('#trade-result').inner_text())
                                self.assertEqual(page.get_by_role('link', name='Review current Market evidence').first.get_attribute('href'), '/market')
                                self.assertNotIn('Provide the missing named evidence', page.locator('#trade-result').inner_text())
                            page.close()
            finally:
                browser.close()


class DetailRouteBrowserTests(unittest.TestCase):
    def test_actual_acquired_pick_and_sparse_market_destinations(self):
        import dtos_app
        fixture = history.HistoricalAssetGraphTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture._append('trade', 'acquired-fourth', 2026, {
            'transaction_id': 'acquired-fourth', 'type': 'trade', 'status': 'complete',
            'roster_ids': [2, 3], 'adds': {}, 'drops': {}, 'draft_picks': [{
                'season': 2027, 'round': 4, 'roster_id': 3,
                'previous_owner_id': 3, 'owner_id': 2,
            }], 'source_league_id': 'L26',
        })
        fixture.current_data['teams'] = [
            {'roster_id': 2, 'team_name': 'Current long human franchise name'},
            {'roster_id': 3, 'team_name': 'Original long human franchise name'},
        ]
        profile_fixture = fois.FOISPresentationTests()
        profile_fixture.setUp()
        self.addCleanup(profile_fixture.tearDown)
        profile = profile_fixture._persist_profiles('ROOT', 1)[0]
        profile_fixture.repository.save(replace(profile, management_momentum='Stable'), 'legacy-one-season')
        app = FastAPI()
        app.include_router(create_fois_router(service=profile_fixture.service,
            require_data=lambda: fixture.current_data, page=dtos_app.page))
        app.include_router(create_historical_assets_router(
            league_id=fixture.league_id, require_data=lambda: fixture.current_data, page=dtos_app.page,
        ))
        sparse = market._Market('sparse-journey')
        sparse.assets = [{'asset_id': 'DTOS-P-6149', 'display_name': 'Darius Slayton',
                          'asset_type': 'player', 'position': 'WR', 'values': {}, 'owner': None}]
        app.include_router(create_market_router(
            require_data=lambda: fixture.current_data, state={'data': fixture.current_data},
            league_id=fixture.league_id, page=dtos_app.page,
        ))
        with patch('routes.historical_assets.historical_store', fixture.store), patch(
            'routes.market.asset_market_cache', market._Cache(sparse)
        ), TestClient(app) as client, sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width in (320, 375, 390, 1280):
                    for height in ((483, 844) if width < 760 else (900,)):
                        with self.subTest(width=width, height=height):
                            page = browser.new_page(viewport={'width': width, 'height': height})

                            def transport(route):
                                url = urlsplit(route.request.url)
                                if url.netloc != 'dtos.test':
                                    return route.abort()
                                response = client.get(url.path + ('?' + url.query if url.query else ''))
                                route.fulfill(status=response.status_code,
                                              content_type=response.headers.get('content-type', 'text/html'), body=response.content)

                            page.route('**/*', transport)
                            page.goto('https://dtos.test/picks/PICK-2027-R4-ORIG3')
                            cards = page.locator('.pick-dossier .summary-grid .metric')
                            owner = cards.filter(has_text='Current Owner')
                            self.assertIn('Current long human franchise name', owner.inner_text())
                            for card in cards.all():
                                value = card.locator('b').bounding_box()
                                label = card.locator('span').bounding_box()
                                self.assertLessEqual(value['x'] + value['width'], card.bounding_box()['x'] + card.bounding_box()['width'] + 1)
                                self.assertLessEqual(value['y'] + value['height'], label['y'] + 1)
                            region = page.get_by_role('region', name='Pick ownership history')
                            region.focus()
                            if width < 760:
                                self.assertGreater(region.evaluate('el=>el.scrollWidth'), region.evaluate('el=>el.clientWidth'))
                                page.keyboard.press('ArrowRight')
                                page.wait_for_function('document.querySelector(".pick-dossier .ds-table-wrap").scrollLeft > 0')
                            technical = page.locator('.pick-dossier > details.technical-details')
                            technical.locator('summary').click()
                            self.assertEqual(technical.locator('code').filter(has_text='ROOT:franchise:2').inner_text(), 'ROOT:franchise:2')
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            page.goto('https://dtos.test/market')
                            page.get_by_role('link').filter(has_text='View asset').click()
                            self.assertTrue(page.locator('#selected-asset').is_visible())
                            self.assertIn('Asset details unavailable', page.locator('#selected-asset').inner_text())
                            self.assertEqual(page.get_by_role('link', name='Browse current Market').get_attribute('href'), '/market')
                            self.assertNotIn('Trade For', page.locator('#selected-asset').inner_text())
                            page.goto('https://dtos.test/fois/gms/gm-0?league_id=ROOT')
                            summary = page.get_by_role('heading', name='Executive Summary', exact=True).locator('..')
                            self.assertIn('Management momentum: Unavailable', summary.inner_text())
                            self.assertIn('comparable historical momentum assessment', summary.inner_text())
                            self.assertNotIn('Management momentum: Stable', summary.inner_text())
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            page.close()
            finally:
                browser.close()
