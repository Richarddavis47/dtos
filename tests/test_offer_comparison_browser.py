"""Actual source/evaluator -> phone comparison, with zero comparison HTTP work."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_team_trade_need_browser as need
from tests import test_contextual_back as back


class OfferComparisonBrowserTests(unittest.TestCase):
    def fixture(self, superflex=False):
        source = need.TeamTradeNeedBrowserTests()
        self.addCleanup(source.doCleanups)
        helper, f = source.fixture(superflex=superflex)
        points = {'a': 20, 'b': 10, 'e': 8, 'c': 28, 'd': 24, 'f': 6}
        for row in source.rows:
            if row['player_id'] in points:
                row['stats'] = {'pass_yd': points[row['player_id']]}
        # The reused need fixture has extra depth to exercise positional flags.
        # Give this legal-execution control real configured bench capacity;
        # never bypass canonical roster-space qualification.
        slots = [s for s in f.editor.data['league']['roster_positions'] if s != 'BN'] + ['BN'] * 20
        f.editor.data['league']['roster_positions'] = slots
        f.editor.data['roster_positions'] = slots
        source.publish(f)
        return source, helper, f

    def record(self, name, rows, page=None):
        folder = os.environ.get('DTOS_COMPARE_EVIDENCE')
        if folder:
            destination = Path(folder)
            destination.mkdir(parents=True, exist_ok=True)
            report = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                          tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
                          working_tree_clean=not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip(),
                          source='Disposable authenticated prepared Sleeper fixture; actual canonical evaluator',
                          physical_safari_tested=False, observations=rows)
            (destination / (name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
            if page:
                page.screenshot(path=str(destination / (name + '.png')), full_page=True)

    def evaluate(self, page, helper, target, with_pick=False):
        if page.locator('#trade-board').is_hidden():
            page.locator('#trade-edit').click()
        page.select_option('#trade-partner', '2')
        page.select_option('#trade-strategy', 'WIN NOW')
        page.locator('[data-side=sent]').click()
        desired = ['2028-R1-3', 'a'] if with_pick else ['a']
        current = helper.draft(page)['currentProposal']
        for asset_id in list(current['sent']):
            page.locator(f'#trade-sent-board button[data-asset-id="{asset_id}"]').click()
        for asset_id in desired:
            page.locator(f'#trade-sent-board button[data-asset-id="{asset_id}"]').click()
        page.locator('[data-side=received]').click()
        current = helper.draft(page)['currentProposal']
        for asset_id in list(current['received']):
            page.locator(f'#trade-received-board button[data-asset-id="{asset_id}"]').click()
        page.locator(f'#trade-received-board button[data-asset-id="{target}"]').click()
        with page.expect_response(lambda r: r.url.endswith('/api/trades/evaluate') and r.request.method == 'POST') as response:
            page.locator('#trade-run').click()
        body = response.value.json()
        self.assertIn('evaluation', body, body)
        page.locator('#trade-result > .tw-compare-add').wait_for()
        return body['evaluation']

    def open_readonly(self, page, requests):
        before = list(requests)
        with (patch('routes.trades.compare_trade_requests', side_effect=AssertionError('No recomparison')),
              patch('routes.trades.evaluate_trade_request', side_effect=AssertionError('No reevaluation')),
              patch('routes.trades.generate_trade_workflow', side_effect=AssertionError('No search'))):
            page.get_by_role('button', name='Compare selected offers', exact=True).click()
            page.locator('#trade-comparison h3').wait_for()
            self.assertEqual(requests, before)
        return before

    def test_phone_two_real_evaluations_keep_packages_costs_and_exact_draft(self):
        source, helper, f = self.fixture()
        saved = deepcopy(f.editor.state())
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        first = self.evaluate(page, helper, 'd')
        page.locator('#trade-result > .tw-compare-add').click()
        second = self.evaluate(page, helper, 'c', with_pick=True)
        page.locator('#trade-result > .tw-compare-add').click()
        original = helper.draft(page)
        offers = original['comparisonOffers']
        self.assertEqual(offers[0]['summary']['lineup']['delta'], first['decision_context']['lineup_comparisons']['current_week']['delta'])
        self.assertEqual(offers[1]['summary']['lineup']['delta'], second['decision_context']['lineup_comparisons']['current_week']['delta'])
        self.assertGreater(offers[1]['summary']['lineup']['delta'], offers[0]['summary']['lineup']['delta'])
        self.assertGreater(offers[1]['summary']['neutral']['sent'], offers[0]['summary']['neutral']['sent'])
        self.assertEqual(offers[1]['proposal']['assets_sent'], ['2028-R1-3', 'a'])
        rows = []
        for width, height in [(320,432), (375,667), (390,844), (1280,900)]:
            page.set_viewport_size(dict(width=width, height=height))
            count = self.open_readonly(page, requests)
            panel = page.locator('#trade-comparison')
            self.assertEqual(panel.get_attribute('data-comparison-state'), 'recorded')
            self.assertIn('Keep the roster', panel.inner_text())
            self.assertEqual(panel.locator('.tw-comparison-offer').count(), 2)
            self.assertIn('Original franchise: 3', panel.inner_text())
            self.assertEqual(panel.locator('[data-comparison-slot="2"] ol').first.locator('small').all_text_contents(),
                             ['Exact asset: 2028-R1-3', 'Exact asset: a'])
            self.assertIn('Their case:', panel.inner_text())
            disclosure = panel.locator('.tw-comparison-offer > details').first
            disclosure.locator('summary').first.press('Enter')
            self.assertTrue(disclosure.evaluate('e=>e.open'))
            self.assertEqual(requests, count)
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            close = page.get_by_role('button', name='Return to my offer or draft', exact=True)
            self.assertGreaterEqual(close.bounding_box()['height'], 44)
            page.keyboard.press('Tab')
            close.focus()
            self.assertNotEqual(close.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
            self.record('phone-' + str(width), dict(width=width, height=height, no_http=True,
                        independent_evaluations=2, higher_gain_higher_cost=True, asset_order_preserved=True,
                        native_deltas=[first['decision_context']['lineup']['delta'], second['decision_context']['lineup']['delta']],
                        native_sent_market=[first['market_evidence']['sent']['total'], second['market_evidence']['sent']['total']],
                        lineage='Current exact picks only; no historical conversion inferred'), page)
            if width == 390:
                cdp = page.context.new_cdp_session(page)
                cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                box = close.bounding_box()
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
                cdp.detach()
            else:
                close.press('Enter')
            self.assertTrue(panel.is_hidden())
            after = helper.draft(page)
            for key in ['currentProposal', 'valuationMode', 'strategy', 'currentAssessment']:
                self.assertEqual(after[key], original[key])
            self.assertEqual(requests, count)
            rows.append(dict(width=width, height=height, preserved_draft=True, no_http=True))
        self.assertFalse(errors, errors)
        self.assertEqual(f.editor.state(), saved)
        self.record('phone-round-trips', rows)
        self.open_readonly(page, requests)
        before_posts = [request for request in requests if request[0] == 'POST']
        with (patch('routes.trades.compare_trade_requests', side_effect=AssertionError('No recomparison')),
              patch('routes.trades.evaluate_trade_request', side_effect=AssertionError('No reevaluation')),
              patch('routes.trades.generate_trade_workflow', side_effect=AssertionError('No search'))):
            page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted: true}))')
            page.evaluate('dispatchEvent(new PageTransitionEvent("pageshow", {persisted: true}))')
            page.wait_for_function("document.querySelector('#trade-comparison').dataset.comparisonState==='retained'")
            panel = page.locator('#trade-comparison')
            self.assertTrue(panel.is_visible())
            self.assertEqual(panel.get_by_text('Retained assessment · NOT REVALIDATED', exact=True).count(), 2)
            restored = helper.draft(page)
            self.assertEqual(len(restored['comparisonOffers']), 2)
            for before, retained in zip(offers, restored['comparisonOffers']):
                for key in ['id', 'scope', 'baseline', 'assets', 'proposal', 'summary']:
                    self.assertEqual(retained[key], before[key])
                self.assertTrue(retained['retained'])
                self.assertTrue(retained['context']['restored'])
            self.assertEqual(panel.locator('[data-comparison-slot="2"] ol').first.locator('small').all_text_contents(),
                             ['Exact asset: 2028-R1-3', 'Exact asset: a'])
            for key in ['currentProposal', 'valuationMode', 'strategy']:
                self.assertEqual(restored[key], original[key])
            self.assertEqual([request for request in requests if request[0] == 'POST'], before_posts)
        self.assertFalse(errors, errors)
        self.assertEqual(f.editor.state(), saved)
        self.record('retained-bfcache', dict(selected_offers=2, exact_snapshots=True,
                    retained_qualification_visible=True, exact_draft=True, no_trade_http=True), page)
        page.reload()
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        count = self.open_readonly(page, requests)
        self.assertEqual(page.locator('#trade-comparison').get_attribute('data-comparison-state'), 'retained')
        self.assertIn('NOT REVALIDATED', page.locator('#trade-comparison').inner_text())
        self.assertEqual(helper.draft(page)['currentProposal'], original['currentProposal'])
        self.assertEqual(requests, count)
        self.record('retained-reload', dict(selected_offers=2, same_prepared_generation=True,
                    retained_qualification_visible=True, exact_draft=True, no_http=True), page)

    def test_superflex_replacement_removal_and_missing_depth_stay_independent(self):
        source, helper, f = self.fixture(superflex=True)
        missing = {'id': 'unknown-cover', 'name': 'Unpriced uncovered receiver', 'position': 'WR',
                   'fantasy_positions': ['WR'], 'status': 'Active', 'roster_slot': 'Bench'}
        f.editor.data['players'][missing['id']] = missing.copy()
        f.editor.data['teams'][0]['players'].append(missing.copy())
        source.publish(f)
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        for target, pick in [('d', False), ('c', True), ('f', False)]:
            self.evaluate(page, helper, target, with_pick=pick)
            page.locator('#trade-result > .tw-compare-add').click()
        self.assertIn('Two offers are selected', page.locator('.tw-comparison-replace').inner_text())
        before = helper.draft(page)['currentProposal']
        page.get_by_role('button', name='Replace offer 1', exact=True).click()
        entries = helper.draft(page)['comparisonOffers']
        self.assertEqual(entries[0]['proposal']['assets_received'], ['f'])
        self.assertEqual(entries[1]['proposal']['assets_received'], ['c'])
        count = self.open_readonly(page, requests)
        panel = page.locator('#trade-comparison')
        self.assertIn('reserve', panel.inner_text().lower())
        self.assertRegex(panel.inner_text().lower(), r'incomplete|unknown|unavailable')
        self.assertEqual(entries[0]['summary']['partnerReason'], entries[0]['context']['evaluation']['decision_context']['partner_summary'])
        page.get_by_role('button', name='Remove offer 1', exact=True).click()
        self.assertEqual(len(helper.draft(page)['comparisonOffers']), 1)
        self.assertEqual(helper.draft(page)['comparisonOffers'][0]['proposal']['assets_received'], ['c'])
        self.assertEqual(helper.draft(page)['currentProposal'], before)
        self.assertEqual(requests, count)
        self.assertFalse(errors, errors)
        self.record('superflex-depth-replace-remove', dict(actual_evaluations=3, missing_depth_qualified=True,
                    counterparty_attached=True, explicit_replacement=True, no_http=True), page)

    def test_aged_publication_reload_withholds_shared_numbers_and_keeps_original_offers(self):
        source, helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        self.evaluate(page, helper, 'd')
        page.locator('#trade-result > .tw-compare-add').click()
        source.publish(f, age=8)
        page.reload()
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        count = self.open_readonly(page, requests)
        panel = page.locator('#trade-comparison')
        self.assertIn(panel.get_attribute('data-comparison-state'), ['stale', 'unknown'])
        self.assertIn('Shared lineup comparison withheld', panel.inner_text())
        self.assertEqual(panel.locator('.tw-comparison-gain').count(), 0)
        self.assertIn('NOT REVALIDATED', panel.inner_text())
        self.assertEqual(len(helper.draft(page)['comparisonOffers']), 1)
        self.assertEqual(requests, count)
        self.assertFalse(errors, errors)
        self.record('aged-incompatible', dict(source_age_hours=8, shared_numbers_withheld=True,
                    retained_offer_visible=True, no_http=True), page)

    def test_recommendations_compare_without_adoption_and_league_switch_discards_scope(self):
        helper = back.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page, '/trades/recommended')
        page.select_option('#trade-strategy', 'REBUILD')
        with page.expect_response(lambda r: r.url.endswith('/api/trades/generate') and r.request.method == 'POST') as response:
            page.locator('#trade-find').click()
        generated = response.value.json()
        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='complete'")
        buttons = page.locator('#trade-result .tw-compare-add:visible')
        self.assertGreaterEqual(buttons.count(), 2)
        buttons.nth(0).click()
        buttons.nth(1).click()
        draft = helper.draft(page)['currentProposal']
        before = self.open_readonly(page, requests)
        page.get_by_role('button', name='Return to my offer or draft', exact=True).click()
        self.assertEqual(helper.draft(page)['currentProposal'], draft)
        self.assertEqual(requests, before)
        f.editor.store.upsert_membership('account-a', {'league_id': 'league-2', 'name': 'Other'},
                                         'account-a', 1, 'Other', 'active')
        f.editor.store.activate('account-a', 'league-2')
        f.editor.data['league']['league_id'] = 'league-2'
        helper.ready(page, '/trades/recommended')
        self.assertTrue(page.locator('#trade-comparison-tray').is_hidden())
        self.assertEqual(helper.draft(page).get('comparisonOffers'), [])
        self.assertFalse(errors, errors)
        self.record('recommendation-league-scope', dict(real_searches=1, no_comparison_search=True,
                    qualified_source_offers=sum(row['evaluation'].get('generated_trade_eligible') is True for row in generated.get('results', [])),
                    no_adoption=True, league_switch_discards_comparison=True))

    def test_two_actual_source_generations_cannot_share_a_lineup_comparison(self):
        source, helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        self.evaluate(page, helper, 'd')
        page.locator('#trade-result > .tw-compare-add').click()
        for row in source.rows:
            if row['player_id'] == 'c':
                row['stats']['pass_yd'] = 29
        source.publish(f)
        page.reload()
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        self.evaluate(page, helper, 'c', with_pick=True)
        page.locator('#trade-result > .tw-compare-add').click()
        offers = helper.draft(page)['comparisonOffers']
        self.assertNotEqual(offers[0]['baseline']['projection'], offers[1]['baseline']['projection'])
        before = self.open_readonly(page, requests)
        panel = page.locator('#trade-comparison')
        self.assertEqual(panel.get_attribute('data-comparison-state'), 'stale')
        self.assertEqual(panel.locator('.tw-comparison-gain').count(), 0)
        self.assertIn('projection generation', panel.inner_text())
        self.assertEqual(requests, before)
        self.assertFalse(errors, errors)
        self.record('two-generations', dict(actual_evaluations=2, incompatible_generations_withheld=True,
                    original_packages_retained=True, no_http=True), page)

    def test_supported_offer_effect_survives_an_incomplete_other_lineup(self):
        source, helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        self.evaluate(page, helper, 'd')
        page.locator('#trade-result > .tw-compare-add').click()
        page.locator('#trade-edit').click()
        page.locator('[data-side=sent]').click()
        for pid in ['b', 'e']:
            page.locator(f'#trade-sent-board button[data-asset-id="{pid}"]').click()
        page.locator('[data-side=received]').click()
        page.locator('#trade-received-board button[data-asset-id="d"]').click()
        page.locator('#trade-received-board button[data-asset-id="2028-R1-4"]').click()
        with page.expect_response(lambda r: r.url.endswith('/api/trades/evaluate') and r.request.method == 'POST') as response:
            page.locator('#trade-run').click()
        incomplete = response.value.json()['evaluation']
        self.assertIsNone(incomplete['decision_context']['lineup_comparisons']['current_week']['delta'])
        page.locator('#trade-result > .tw-compare-add').click()
        before = self.open_readonly(page, requests)
        panel = page.locator('#trade-comparison')
        self.assertEqual(panel.get_attribute('data-comparison-state'), 'incomplete')
        self.assertEqual(panel.locator('.tw-comparison-gain').count(), 1)
        self.assertIn('Supported individual effect', panel.inner_text())
        self.assertIn('Shared lineup comparison withheld', panel.inner_text())
        self.assertEqual(requests, before)
        self.assertFalse(errors, errors)
        self.record('partial-pair', dict(actual_evaluations=2, supported_individual_delta_preserved=True,
                    incomplete_other_lineup_unknown=True, no_http=True), page)

    def test_custom_and_neutral_values_remain_attached_to_their_actual_evaluations(self):
        helper = back.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        helper.choose(page)
        originals = []
        for mode in ['custom', 'neutral']:
            page.select_option('#trade-valuation-mode', mode)
            with page.expect_response(lambda r: r.url.endswith('/api/trades/evaluate') and r.request.method == 'POST') as response:
                page.locator('#trade-run').click()
            e = response.value.json()['evaluation']
            page.locator('#trade-result > .tw-compare-add').wait_for()
            page.locator('#trade-result > .tw-compare-add').click()
            originals.append(e)
        selected = helper.draft(page)['comparisonOffers']
        self.assertEqual([r['summary']['mode'] for r in selected], ['custom', 'neutral'])
        for index, e in enumerate(originals):
            self.assertEqual(selected[index]['summary']['neutral']['sent'], e['market_evidence']['sent']['total'])
            self.assertEqual(selected[index]['summary']['neutral']['received'], e['market_evidence']['received']['total'])
        self.assertEqual(selected[0]['summary']['personal']['sent'], originals[0]['personal_value_evidence']['sent']['total'])
        draft = helper.draft(page)['currentProposal']
        before = self.open_readonly(page, requests)
        panel = page.locator('#trade-comparison')
        self.assertIn('Valuation modes or methods differ', panel.inner_text())
        self.assertEqual(panel.get_attribute('data-comparison-state'), 'incomplete')
        self.assertTrue(any(e['decision_context']['lineup_comparisons']['current_week']['state'] != 'supported'
                            for e in originals))
        self.assertIn('Your Custom values', panel.inner_text())
        self.assertEqual(panel.locator('.tw-comparison-offer').count(), 2)
        page.get_by_role('button', name='Return to my offer or draft', exact=True).click()
        self.assertEqual(helper.draft(page)['currentProposal'], draft)
        self.assertEqual(requests, before)
        self.assertFalse(errors, errors)
        self.record('neutral-custom', dict(actual_evaluations=2, neutral_values_match_originals=True,
                    custom_values_match_original=True, modes_separate=True, no_http=True), page)
        page.reload()
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        count = self.open_readonly(page, requests)
        self.assertEqual(page.locator('#trade-comparison').get_attribute('data-comparison-state'), 'incomplete',
                         page.locator('#trade-comparison > p').first.inner_text())
        self.assertTrue(all(not r['context'].get('stale_reason') for r in helper.draft(page)['comparisonOffers']))
        self.assertIn('NOT REVALIDATED', page.locator('#trade-comparison').inner_text())
        self.assertEqual(len(helper.draft(page)['comparisonOffers']), 2)
        self.assertEqual(helper.draft(page)['currentProposal'], draft)
        self.assertEqual(requests, count)
        self.record('custom-incomplete-reload', dict(selected_offers=2, same_prepared_generation=True,
                    original_incomplete_lineup_preserved=True, draft_mode_does_not_mutate_selected_assessment=True,
                    retained_qualification_visible=True, exact_draft=True, no_http=True), page)
