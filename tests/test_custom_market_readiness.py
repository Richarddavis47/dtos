"""Canonical publication admission → saved intent → actual Trade readiness.

All mutations use disposable accounts. Prices are controls, not player quotes.
No source/valuation rules are relaxed; actual resource gates run separately.
"""
from copy import deepcopy
from contextlib import ExitStack
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.responses import HTMLResponse
from playwright.sync_api import sync_playwright

from routes.market import create_market_router
from routes.trades import create_trades_router
from services.personal_rankings import PersonalRankingError, build_universe, personal_bootstrap
from src.core.accounts.personal_store import load_personal
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from tests import test_personal_rankings_availability as canonical
from tests import test_personal_trade_browser as browser_controls
from tools.validation.browser_runtime import launch_chromium


def evidence(name, value):
    if os.getenv('DTOS_CUSTOM_READINESS_EVIDENCE'):
        root = Path(os.environ['DTOS_CUSTOM_READINESS_EVIDENCE'])
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + '.json')).write_text(json.dumps(value, indent=2))


class CanonicalCustomReadinessTests(unittest.TestCase):
    def fixture(self):
        f = canonical.CanonicalRankingAvailabilityTests('test_real_market_ready_without_synthetic_provider_timestamp')
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.cache.wait_for_background)
        f.runtime_state = {'data': f.data}
        self.enterContext(patch('routes.market.historical_store', f.history))
        self.enterContext(patch('routes.market.history_progress_contracts', return_value={}))
        self.enterContext(patch('routes.market.retained_history_progress_contracts', return_value={}))
        with patch('routes.market.intelligence_checkpoint_store', IntelligenceCheckpointStore(Path(f.temp.name) / 'trends.sqlite3')):
            f.app.include_router(create_market_router(
                require_data=lambda: f.data, state=f.runtime_state, league_id='league-1',
                page=lambda title, body: HTMLResponse(body),
                context_resolver=lambda: SimpleNamespace(state=f.runtime_state, league_id='league-1', market=f.cache)))
        f.app.include_router(create_trades_router(
            ensure_fresh=AsyncMock(), require_data=lambda: f.data,
            page=lambda title, body: HTMLResponse(body),
            personal_bootstrap=lambda data, active: personal_bootstrap(data, active, store=f.store, market_reader=f.market)))
        f.initialize()
        return f

    def transition(self, f, data):
        f.data = data
        f.runtime_state['data'] = data
        self.assertTrue(f.cache.reconcile(data, f.runtime_state, f.history, 'league-1'))
        f.cache.wait_for_background(10)
        self.assertFalse(f.cache.metrics()['build_active'])
        f.market = f.cache.current()

    def test_semantically_equal_refresh_preserves_one_publication_and_all_custom_values(self):
        f = self.fixture()
        f.post('reorder', asset_id='player:3', to_position=1)
        f.post('tiers', asset_id='player:2', tier_start=True)
        f.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        saved = deepcopy(load_personal(f.store, 'account-a', 'league-1', 1))
        before = f.state()
        market = f.market
        original_marker = market._prepared_input_marker
        original_directory = market.directory(limit=250)
        original_personal = f.client.get('/api/trades/workspace?mode=calculator').json()['personalization']
        data = deepcopy(f.data)
        data['valuation_intelligence']['semantic_generation'] += '-same-content'
        f.data = data
        self.assertFalse(market.compatible_prepared_inputs(data))
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 409)
        self.transition(f, data)
        self.assertIs(f.market, market)
        self.assertEqual(market._prepared_input_marker, original_marker)
        self.assertTrue(market.compatible_prepared_inputs(data))
        self.assertEqual(f.cache.metrics()['market_rebuild_requests_noop'], 1)
        self.assertEqual(f.cache.preparation_status(data, f.runtime_state, f.history, 'league-1')['state'], 'ready')
        actual_market = f.client.get('/api/market/assets?limit=250')
        self.assertEqual(actual_market.status_code, 200, actual_market.text)
        self.assertEqual(actual_market.json()['market_generation'], original_directory['market_generation'])
        self.assertEqual([(r['asset_id'], r['values']['market_value']) for r in actual_market.json()['assets']],
                         [(r['asset_id'], r['values']['market_value']) for r in original_directory['assets']])
        after = f.state()
        self.assertEqual(after['rows'], before['rows'])
        self.assertEqual(after['revision'], before['revision'])
        self.assertEqual(after['generation'], before['generation'])
        for path in ['/api/trades/workspace', '/api/trades/workspace?mode=calculator']:
            response = f.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            p = response.json()['personalization']
            self.assertTrue(p['available'])
            self.assertEqual(p['values'], original_personal['values'])
            self.assertEqual(p['revision'], before['revision'])
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)
        evidence('canonical-noop', {'market_ready': True, 'my_dtos_status': 200, 'trade_custom_available': True,
            'same_immutable_generation': True, 'build_provenance_unchanged': True,
            'all_personal_values_unchanged': True, 'saved_document_unchanged': True,
            'source_generation': market.generated_at, 'revision': after['revision']})

    def test_pending_or_failed_preparation_does_not_certify_new_inputs(self):
        f = self.fixture()
        market, marker = f.market, f.market._admitted_input_marker
        saved = deepcopy(load_personal(f.store, 'account-a', 'league-1', 1))
        data = deepcopy(f.data)
        data['valuation_intelligence']['semantic_generation'] += '-unprepared'
        f.data = data
        self.assertFalse(market.compatible_prepared_inputs(data))
        p = f.client.get('/api/trades/workspace').json()['personalization']
        self.assertFalse(p['available'])
        self.assertEqual(p['readiness_code'], 'market_source_changed')
        with patch.object(f.cache, '_isolated_semantic_identities', side_effect=RuntimeError('synthetic unavailable preparation')):
            self.transition(f, data)
        self.assertIs(f.market, market)
        self.assertEqual(market._admitted_input_marker, marker)
        self.assertFalse(market.compatible_prepared_inputs(data))
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 409)
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)

    def test_changed_price_requires_new_generation_not_an_equivalence_admission(self):
        f = self.fixture()
        market = f.market
        data = deepcopy(f.data)
        data['valuation_intelligence']['semantic_generation'] += '-new-price'
        data['valuation_intelligence']['assets']['player:3']['valuation_layers']['market_value']['value'] = 440
        f.data = data
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 409)
        self.transition(f, data)
        self.assertIsNot(f.market, market)
        self.assertNotEqual(f.market.semantic_generation, market.semantic_generation)
        self.assertFalse(market.compatible_prepared_inputs(data))
        row = next(x for x in f.state()['rows'] if x['asset_id'] == 'player:3')
        self.assertEqual(row['market_value'], 440)
        self.assertEqual(f.client.get('/api/trades/workspace').json()['personalization']['revision'], 1)

    def test_preparation_transition_and_foreign_scope_still_fail_closed(self):
        f = self.fixture()
        market, marker = f.market, f.market._admitted_input_marker
        data = deepcopy(f.data)
        data['valuation_intelligence']['semantic_generation'] += '-pending'
        original = f.cache._isolated_semantic_identities
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            data['valuation_intelligence']['semantic_generation'] += '-superseded'
            return result
        with patch.object(f.cache, '_isolated_semantic_identities', side_effect=changed):
            self.transition(f, data)
        self.assertEqual(market._admitted_input_marker, marker)
        self.assertFalse(market.compatible_prepared_inputs(data))
        foreign = deepcopy(data)
        foreign['league']['league_id'] = 'foreign-league'
        with self.assertRaises(PersonalRankingError) as error:
            build_universe(foreign, market)
        self.assertEqual(error.exception.code, 'market_scope_changed')
        f.use_account('account-b')
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 409)
        self.assertIsNone(load_personal(f.store, 'account-b', 'league-1', 1))

    def test_admitted_ordinary_reads_add_no_heavy_work_or_preference_writes(self):
        f = self.fixture()
        saved = deepcopy(load_personal(f.store, 'account-a', 'league-1', 1))
        data = deepcopy(f.data)
        data['valuation_intelligence']['semantic_generation'] += '-equivalent'
        self.transition(f, data)
        guards = ['services.sleeper.sleeper_get',
                  'services.trade_intelligence.generate_trade_workflow',
                  'src.core.fois.service.FOISService._generate_sync',
                  'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
                  'src.core.projection_intelligence.service.ProjectionService.generate',
                  'src.core.trade_intelligence.lineup_memo.optimal_legal_lineup']
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(name, side_effect=AssertionError('Unexpected ordinary-read work: ' + name)))
                     for name in guards]
            spies += [stack.enter_context(patch.object(f.cache, name, side_effect=AssertionError('Read prepared evidence only')))
                      for name in ['_isolated_semantic_identities', '_construct']]
            for path in ['/api/market', '/api/market/assets?limit=1', '/api/my-dtos', '/api/trades/workspace']:
                response = f.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('no-store', response.headers['cache-control'])
            for spy in spies:
                spy.assert_not_called()
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)
        evidence('read-costs', {'ordinary_reads': 4, 'guarded_heavy_calls': 0, 'market_builds': 0,
                              'semantic_preparations_on_reads': 0, 'saved_document_unchanged': True})


class CustomReadinessRecoveryBrowserTests(unittest.TestCase):
    def test_explicit_recheck_preserves_offer_and_neutral_until_custom_is_selected(self):
        helper = browser_controls.PersonalTradeBrowserTests()
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in helper.viewports:
                    f = helper.fixture()
                    page = None
                    try:
                        f.editor.initialize()
                        saved = deepcopy(load_personal(f.editor.store, 'account-a', 'league-1', 1))
                        page, requests, errors = helper.page(browser, f, width, height)
                        helper.choose_package(page)
                        original = deepcopy(helper.draft(page)['currentProposal'])
                        reader = f.editor.market
                        f.editor.market = None
                        page.reload()
                        select = page.locator('#trade-valuation-mode')
                        select.wait_for()
                        self.assertTrue(select.locator('option[value="custom"]').is_disabled())
                        self.assertIn('prepare Market', select.locator('option[value="custom"]').inner_text())
                        self.assertEqual(select.input_value(), 'neutral')
                        retry = page.get_by_role('button', name='Reload Custom evidence', exact=True)
                        retry.wait_for()
                        retry_box = retry.bounding_box()
                        self.assertGreaterEqual(retry_box['height'], 44)
                        self.assertEqual(helper.draft(page)['currentProposal'], original)
                        output = os.getenv('DTOS_CUSTOM_READINESS_EVIDENCE')
                        if output:
                            Path(output).mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(Path(output) / f'pending-before-recheck-{width}.png'), full_page=True)
                        f.editor.market = reader
                        # Backend is now ready, but this older view must not
                        # silently change mode or claim its packages revalidated.
                        self.assertTrue(f.editor.client.get('/api/trades/workspace').json()['personalization']['available'])
                        self.assertTrue(select.locator('option[value="custom"]').is_disabled())
                        retry.focus()
                        self.assertNotEqual(retry.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                        with page.expect_navigation(wait_until='domcontentloaded'):
                            retry.press('Enter')
                        page.wait_for_function("document.querySelector('#trade-valuation-mode option[value=custom]')?.disabled===false")
                        self.assertEqual(page.locator('#trade-valuation-mode').input_value(), 'neutral')
                        self.assertEqual(helper.draft(page)['currentProposal'], original)
                        self.assertEqual(requests, [])
                        self.assertEqual(page.locator('#trade-personal-retry').count(), 0)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                        self.assertFalse(errors, errors)
                        self.assertEqual(load_personal(f.editor.store, 'account-a', 'league-1', 1), saved)
                        if width < 500:
                            f.editor.market = None
                            page.reload()
                            retry = page.get_by_role('button', name='Reload Custom evidence', exact=True)
                            retry.wait_for()
                            retry.scroll_into_view_if_needed()
                            box = retry.bounding_box()
                            f.editor.market = reader
                            touch = page.context.new_cdp_session(page)
                            touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                            with page.expect_navigation(wait_until='domcontentloaded'):
                                touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
                                    {'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
                                touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                            page.wait_for_function("document.querySelector('#trade-valuation-mode option[value=custom]')?.disabled===false")
                            self.assertEqual(helper.draft(page)['currentProposal'], original)
                            self.assertEqual(requests, [])
                            self.assertEqual(load_personal(f.editor.store, 'account-a', 'league-1', 1), saved)
                        measurements.append({'width': width, 'height': height, 'keyboard_recovery': True,
                            'touch_recovery': width < 500, 'retry_height': retry_box['height'],
                            'same_package': True, 'neutral_preserved': True, 'saved_rankings_unchanged': True,
                            'no_automatic_evaluation_or_discovery': True, 'overflow': False})
                        output = os.getenv('DTOS_CUSTOM_READINESS_EVIDENCE')
                        if output:
                            page.screenshot(path=str(Path(output) / f'ready-recovered-{width}.png'), full_page=True)
                    finally:
                        if page:
                            page.close()
                        f.doCleanups()
            finally:
                browser.close()
        evidence('recovery-browser', measurements)
