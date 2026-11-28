"""Exact-offer price checks over the published Burrow replay fixture."""
import copy
import unittest
from unittest.mock import patch

from services.trade_intelligence import assist_trade_request, build_trade_workspace
from tests import test_trade_package_adjustment as burrow


class TradeWalkAwayTests(unittest.TestCase):
    def setUp(self):
        self.fixture = burrow.TradePackageAdjustmentTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def prepare_supported_offer(self):
        self.fixture.data['teams'][1]['strategy'] = 'REBUILD'
        self.fixture.change_player('active-qb', value=800)
        self.fixture.change_player('active-rb', value=450)
        self.fixture.data['teams'][0]['picks_owned'].append(
            {'year': 2028, 'round': 3, 'original_roster_id': 2, 'current_owner_id': 1})
        self.fixture.publish()

    def test_win_now_additions_bracket_the_tested_walk_away_point(self):
        self.prepare_supported_offer()
        additions = dict(repair_mode='WALK_AWAY', protected_assets=['active-rb'])
        terms = self.fixture.revision_request(**additions)
        unchanged = copy.deepcopy(terms)
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.fixture.projections):
            response = assist_trade_request(self.fixture.data, terms)
        smaller, larger = response['results']
        self.assertTrue(response['preview_only'])
        self.assertEqual(response['strategy'], 'WIN NOW')
        self.assertEqual(terms, unchanged)
        self.assertEqual(response['cutoff_asset_id'], 'active-qb')
        self.assertEqual(smaller['asset']['asset_id'], '2028-R3-2')
        self.assertEqual(smaller['asset']['original_franchise'], 2)
        self.assertEqual(smaller['market_cost'], 211)
        self.assertTrue(smaller['credible'])
        self.assertEqual(smaller['impact']['lineup']['delta'], 0)
        self.assertEqual(smaller['impact']['reserves']['delta'], 0)
        self.assertEqual(larger['market_cost'], 800)
        self.assertFalse(larger['credible'])
        self.assertEqual(larger['owner_assessment'], 'NOT WORTH IT')
        self.assertEqual(larger['impact']['lineup']['delta'], -3)
        self.assertEqual(larger['impact']['reserves']['delta'], -10)
        for change in response['results']:
            self.assertEqual(change['impact']['week'], 12)
            self.assertEqual(change['proposal']['assets_sent'], [*terms['assets_sent'], change['asset']['asset_id']])
            self.assertEqual(change['proposal']['assets_received'], terms['assets_received'])
        self.assertEqual(response['search_evidence'], dict(full_evaluations=3, evaluation_budget=3, bounded=True))

    def test_equal_cost_or_only_one_tested_option_establishes_no_cutoff(self):
        self.prepare_supported_offer()
        self.fixture.change_player('active-qb', value=211)
        self.fixture.publish()
        same_price = self.fixture.revise(repair_mode='WALK_AWAY', protected_assets=['active-rb'])
        self.assertEqual([row['market_cost'] for row in same_price['results']], [211, 211])
        self.assertIsNone(same_price['cutoff_asset_id'])
        one = self.fixture.revise(repair_mode='WALK_AWAY', protected_assets=['active-rb', 'active-qb'])
        self.assertEqual([row['asset']['asset_id'] for row in one['results']], ['2028-R3-2'])
        self.assertIsNone(one['cutoff_asset_id'])
        self.assertIn('no clear walk-away point', one['quiet_state'])
        conflict = self.fixture.revise(repair_mode='WALK_AWAY', protected_assets=[burrow.PICK])
        self.assertEqual(conflict['state'], 'CONSTRAINT_CONFLICT')
        self.assertEqual(conflict['search_evidence']['full_evaluations'], 0)

    def test_custom_cost_is_separate_and_prepared_projection_gaps_withhold_cutoff(self):
        self.prepare_supported_offer()
        prices = {asset.asset_id: asset.trade_value
                  for pool in build_trade_workspace(self.fixture.data, 1)['pools'].values() for asset in pool}
        custom = {'mode': 'custom', 'method': 'personal-current-market-slot-curve-v1', 'revision': 1,
                  'values': {**prices, '2028-R3-2': 189}, 'neutral_values': prices,
                  'preferences': {'active-rb': {'protect': True}}}
        response = self.fixture.revise(repair_mode='WALK_AWAY', _personal_context=custom)
        smaller, larger = response['results']
        self.assertEqual((smaller['asset']['asset_id'], smaller['market_cost'], smaller['custom_cost']), ('2028-R3-2', 211, 189))
        self.assertEqual(smaller['custom_method'], custom['method'])
        self.assertEqual(larger['asset']['asset_id'], 'active-qb')
        self.assertEqual(response['cutoff_asset_id'], 'active-qb')

        publish = self.fixture.projections.publish_horizon
        def omit_projection(payloads, **kwargs):
            return publish({week: [row for row in observations if row['player_id'] != 'active-qb']
                            for week, observations in payloads.items()}, **kwargs)

        with patch.object(self.fixture.projections, 'publish_horizon', side_effect=omit_projection):
            self.fixture.publish()
        missing = self.fixture.revise(repair_mode='WALK_AWAY', _personal_context=custom)
        self.assertIsNone(missing['cutoff_asset_id'])
        smaller, larger = missing['results']
        self.assertTrue(smaller['credible'])
        self.assertEqual(smaller['impact']['lineup']['delta'], 0)
        self.assertIsNone(smaller['impact']['reserves'])
        self.assertFalse(larger['credible'])
        self.assertIsNone(larger['impact']['lineup'])
        self.assertIsNone(larger['impact']['reserves'])
        self.assertIn('No supported Sleeper projection', larger['reason'])

    def test_unknown_burrow_partner_has_no_cutoff_or_recommendation(self):
        original = self.fixture.evaluate()
        self.assertEqual(original['market_evidence']['difference'], 0)
        self.assertFalse(original['generated_trade_eligible'])
        for sent, received in ((('nix', 'young', burrow.PICK, 'active-rb'), ('burrow', 'skattebo')),
                               (('nix', 'young', burrow.PICK), ('burrow',))):
            evaluation = self.fixture.evaluate(sent, received)
            self.assertTrue(evaluation['legal'])
            self.assertTrue(evaluation['package_adjustment']['partner']['blocks_recommendation'])
            self.assertFalse(evaluation['generated_trade_eligible'])
        response = self.fixture.revise(repair_mode='WALK_AWAY')
        self.assertEqual(response['current_verdict'], 'COUNTERPARTY LIMITED')
        self.assertIsNone(response['cutoff_asset_id'])
        self.assertTrue(response['results'])
        self.assertTrue(all(not row['credible'] for row in response['results']))
        rb = next(row for row in response['results'] if row['asset']['asset_id'] == 'active-rb')
        self.assertEqual(rb['verdict'], 'COUNTERPARTY LIMITED')
        self.assertIn('projected lineup points', rb['partner_limit'])

    def test_rendered_review_price_check_leaves_draft_in_place_on_phones(self):
        import json
        import os
        from contextlib import nullcontext
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from urllib.parse import urlsplit

        import dtos_app
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from fastapi.testclient import TestClient
        from playwright.sync_api import expect, sync_playwright
        from routes.trades import create_trades_router
        from tools.validation.browser_runtime import launch_chromium

        self.prepare_supported_offer()
        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: self.fixture.data,
                                               page=dtos_app.page))
        app.mount('/static', StaticFiles(directory='static'), name='static')
        account = SimpleNamespace(account_id='fixture', session_id='walk-away-replay', csrf_token='fixture-only',
            display_name='Manager', membership=SimpleNamespace(league_id='league-1', roster_id=1,
                league_name='Dynasty Best Ball', franchise_name='The tankers'))

        with TestClient(app) as http, patch('src.core.projection_intelligence.projection_service', self.fixture.projections), \
                patch('dtos_app.current_account', return_value=account), \
                patch.object(dtos_app.account_store, 'memberships', return_value=[]), \
                patch('routes.trades.current_account', return_value=account), \
                patch('services.trade_workspace_context.current_account', return_value=account), sync_playwright() as engine:
            for width, height in ((320, 432), (390, 844)):
                with self.subTest(width=width):
                    browser = launch_chromium(engine, headless=True)
                    try:
                        page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=True)
                        requests, responses = [], []
                        workspace = {}

                        def render(intercept):
                            request = intercept.request
                            url = urlsplit(request.url)
                            if url.netloc != 'dtos.test':
                                return intercept.abort()
                            pin = patch('services.trade_intelligence.generate_proposals', side_effect=self.fixture.burrow_construction)
                            with pin if url.path == '/api/trades/generate' else nullcontext():
                                reply = http.request(request.method, url.path+'?'+url.query, content=request.post_data,
                                    headers={key: value for key, value in request.headers.items() if key == 'content-type'})
                            if url.path == '/api/trades/workspace':
                                workspace.update(reply.json())
                            if url.path == '/api/trades/assist':
                                requests.append(json.loads(request.post_data))
                                responses.append(reply.json())
                            intercept.fulfill(status=reply.status_code, headers=dict(reply.headers), body=reply.content)

                        def draft():
                            key = 'dtos-trade-workspace:' + workspace['workspace_context']['binding']
                            return page.evaluate('key => JSON.parse(sessionStorage.getItem(key)).currentProposal', key)

                        page.route('**/*', render)
                        page.goto('https://dtos.test/trades/trade-for?asset_id=burrow&front_office=1')
                        page.get_by_label('Trade strategy', exact=True).select_option('WIN NOW')
                        page.locator('#trade-find').click()
                        page.get_by_role('button', name='Review trade', exact=True).click()
                        if width == 390:
                            page.get_by_role('button', name='Use this offer in my draft', exact=True).click()
                            page.locator('#trade-run').click()
                        panel = page.locator('.tw-walk-away')
                        action = panel.get_by_role('button', name='What can I afford to add?')
                        expect(action).to_be_visible()
                        old_draft = draft()
                        if width == 390:
                            self.assertEqual(old_draft['sent'], ['nix', 'young', burrow.PICK])
                            self.assertEqual(old_draft['received'], ['burrow', 'skattebo'])
                        self.assertFalse(requests)
                        action.evaluate("e=>e.scrollIntoView({block:'center'})")
                        self.assertTrue(action.evaluate('''e => {
                            const r = e.getBoundingClientRect();
                            const nav = document.querySelector('.manager-nav').getBoundingClientRect();
                            return r.height >= 44 && r.top >= 0 && r.bottom <= Math.min(innerHeight, nav.top)
                                && e.contains(document.elementFromPoint(r.x + r.width/2, r.y + r.height/2));
                        }'''))
                        if width == 320:
                            action.tap()
                        else:
                            action.press('Enter')
                        expect(panel).to_have_attribute('data-state', 'CHECKED')
                        expect(panel).to_contain_text('Past your walk-away point')
                        expect(panel).to_contain_text('Still fits · both teams pass')
                        expect(panel).to_contain_text('originally Crayon Eaters (#2)')
                        expect(panel).to_contain_text('Starting lineup: -3')
                        expect(panel).to_contain_text('Eligible backups: -10')
                        choices = panel.locator('article')
                        self.assertEqual(choices.count(), 2)
                        self.assertEqual(panel.get_by_role('button', name='Use this offer in my draft').count(), 0)
                        detail = choices.last.locator('summary')
                        detail.evaluate("e=>e.scrollIntoView({block:'center'})")
                        self.assertTrue(detail.evaluate('''e => {
                            const box = e.getBoundingClientRect();
                            return box.top >= 0 && box.bottom <= document.querySelector('.manager-nav').getBoundingClientRect().top;
                        }'''))
                        detail.press('Enter')
                        expect(choices.last.get_by_text('Win Now fit is weak', exact=False)).to_be_visible()
                        detail.press('Enter')
                        self.assertEqual(requests[0]['origin_asset_id'], 'burrow')
                        self.assertEqual(requests[0]['assets_sent'], ['nix', 'young', burrow.PICK])
                        self.assertEqual(draft(), old_draft)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        if directory := os.environ.get('DTOS_WALK_AWAY_EVIDENCE'):
                            path = Path(directory)
                            path.mkdir(parents=True, exist_ok=True)
                            panel.screenshot(path=str(path/f'walk-away-{width}.png'))
                            if width == 390:
                                (path/'rendered-response.json').write_text(json.dumps(responses[0], indent=2))
                        page.reload()
                        expect(page.locator('#trade-target')).to_be_visible()
                        self.assertEqual(draft(), old_draft)
                        self.assertEqual(len(requests), 1)
                    finally:
                        browser.close()
