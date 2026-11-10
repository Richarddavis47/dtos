"""Exact temporary constraints through real authenticated search and phone UI.

Disposable prepared Sleeper fixtures and actual admission/evaluation. No live
owner league, synthetic successful response, or physical Safari claim.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_contextual_back as back


class RecommendedProtectionBrowserTests(unittest.TestCase):
    def fixture(self):
        helper = back.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        for original in (1, 3):
            f.editor.data['teams'][0]['picks_owned'].append(dict(
                year=2029, round=1, original_roster_id=original, current_owner_id=1))
        quote = dict(f.editor.data['market_data']['pick_quotes']['FantasyCalc'][0], year=2029, value=334 * 12)
        quote['normalization_reference'] = dict(quote['normalization_reference'], raw_value=334 * 12, normalized_value=334)
        f.editor.data['market_data']['pick_quotes']['FantasyCalc'].append(quote)
        f.capital.publish()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f, 320, 432)
        self.addCleanup(lambda: self.assertFalse(errors, errors))
        return helper, f, page, requests

    def record(self, name, facts, page=None):
        folder = os.environ.get('DTOS_PROTECTIONS_EVIDENCE')
        if not folder:
            return
        destination = Path(folder)
        destination.mkdir(parents=True, exist_ok=True)
        report = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                      tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
                      working_tree_clean=not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip(),
                      source='Disposable prepared Sleeper fixture; actual authenticated routes, canonical search and admission',
                      physical_safari_tested=False, observations=facts)
        (destination / (name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
        if page:
            page.screenshot(path=str(destination / (name + '.png')), full_page=True)

    def protect(self, page, asset_id):
        details = page.locator('#recommendation-protection-options')
        if not details.evaluate('e=>e.open'):
            details.locator('summary').press('Enter')
        page.select_option('#recommendation-protection-asset', asset_id)
        page.locator('#recommendation-protection-add').press('Enter')

    def generate(self, page):
        with page.expect_response(lambda r: r.url.endswith('/api/trades/generate') and r.request.method == 'POST') as response:
            page.locator('#trade-find').click()
        body = response.value.json()
        self.assertEqual(response.value.status, 200, body)
        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='complete'")
        return response.value.request.post_data_json, body

    def test_exact_pick_player_and_phone_search_preserve_other_same_round_pick(self):
        helper, f, page, requests = self.fixture()
        saved = deepcopy(f.editor.state())
        helper.ready(page, '/trades/recommended')
        before = [r for r in requests if r[0] == 'POST']
        self.protect(page, '2029-R1-1')
        self.protect(page, 'a')
        self.assertEqual([r for r in requests if r[0] == 'POST'], before)
        self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], ['2029-R1-1', 'a'])
        self.assertIn('2029-R1-3', page.locator('#recommendation-protection-asset option').evaluate_all('es=>es.map(e=>e.value)'))
        rows = []
        for width, height in [(320,432), (375,667), (390,844), (1280,900)]:
            page.set_viewport_size(dict(width=width, height=height))
            selected = page.locator('#recommendation-protection-list')
            self.assertIn('2029-R1-1', selected.inner_text())
            self.assertIn('Original franchise:', selected.inner_text())
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            remove = selected.get_by_role('button').first
            self.assertGreaterEqual(remove.bounding_box()['height'], 44)
            remove.focus()
            self.assertNotEqual(remove.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
            self.record('phone-' + str(width), dict(width=width, height=height, exact_ids=['2029-R1-1','a'], no_search_from_controls=True), page)
            rows.append(dict(width=width, height=height))
        page.set_viewport_size(dict(width=390, height=844))
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        remove = page.locator('[data-protected-asset="a"]')
        remove.scroll_into_view_if_needed()
        cdp = page.context.new_cdp_session(page)
        cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        box = remove.bounding_box()
        cdp.send('Input.dispatchTouchEvent', {'type':'touchStart', 'touchPoints':[{'x':box['x']+box['width']/2, 'y':box['y']+box['height']/2}]})
        cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd', 'touchPoints':[]})
        cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
        cdp.detach()
        self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], ['2029-R1-1'])
        self.protect(page, 'a')
        import services.recommended_trade_search as search
        original = search.generate_proposals
        pools = []
        def observe(*args, **kwargs):
            pools.append([a.asset_id for a in args[2]])
            return original(*args, **kwargs)
        page.select_option('#trade-strategy', 'REBUILD')
        with patch.object(search, 'generate_proposals', side_effect=observe):
            payload, body = self.generate(page)
        self.assertEqual(payload['protected_assets'], ['2029-R1-1', 'a'])
        self.assertEqual(set(body['constraints']['protected_assets']), {'2029-R1-1', 'a'})
        self.assertTrue(pools, 'Actual candidate construction must execute')
        self.assertTrue(any('2029-R1-3' in pool for pool in pools))
        for pool in pools:
            self.assertTrue(set(pool).isdisjoint({'2029-R1-1','a'}))
        offers = body.get('results', []) + body.get('exploratory_results', [])
        for row in offers:
            self.assertTrue(set(row['proposal']['assets_sent']).isdisjoint({'2029-R1-1','a'}))
        self.assertIn('2029-R1-1', page.locator('#trade-result .tw-applied-protections').inner_text())
        self.assertEqual(f.editor.state(), saved)
        self.record('exact-native-search', dict(payload=payload, constraints=body['constraints'], candidate_pools=pools,
                    offers=offers, diagnostics=body.get('search_evidence'), viewports=rows, saved_preferences_unchanged=True))

    def test_clear_controls_retains_original_results_and_no_automatic_search(self):
        helper, f, page, requests = self.fixture()
        helper.ready(page, '/trades/recommended')
        self.protect(page, '2029-R1-1')
        _, body = self.generate(page)
        old = deepcopy(helper.draft(page)['recommendedSearch'])
        count = len([r for r in requests if r[0] == 'POST'])
        page.locator('#recommendation-protection-clear').click()
        self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], [])
        self.assertEqual(helper.draft(page)['recommendedSearch'], old)
        page.locator('#recommendation-previous > summary').click()
        self.assertIn('2029-R1-1', page.locator('#recommendation-previous').inner_text())
        self.assertTrue(page.locator('#trade-result').is_hidden())
        self.assertEqual(len([r for r in requests if r[0] == 'POST']), count)
        payload, second = self.generate(page)
        self.assertEqual(payload['protected_assets'], [])
        self.assertEqual(second['constraints']['protected_assets'], [])
        self.assertIn('No outgoing asset protections were applied', page.locator('#trade-result').inner_text())
        self.record('clear-and-prior-results', dict(old=old, first_constraints=body['constraints'], second_constraints=second['constraints'],
                    old_results_not_relabeled=True, clearing_did_not_search=True))

    def test_evaluate_draft_comparison_return_and_league_isolation(self):
        helper, f, page, requests = self.fixture()
        helper.ready(page)
        helper.choose(page)
        with page.expect_response(lambda r: r.url.endswith('/api/trades/evaluate') and r.request.method == 'POST') as response:
            page.locator('#trade-run').click()
        self.assertEqual(response.value.status, 200)
        page.locator('#trade-result > .tw-compare-add').click()
        original = helper.draft(page)
        page.locator('.tw-intent-nav a[href*=recommended]').click()
        page.wait_for_url('**/trades/recommended?front_office=1')
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        self.protect(page, '2029-R1-1')
        self.protect(page, 'a')
        helper.back(page, '/trades/create')
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        restored = helper.draft(page)
        for key in ['currentProposal','valuationMode','strategy']:
            self.assertEqual(restored[key], original[key], key)
        self.assertEqual(restored['currentAssessment']['evaluation'], original['currentAssessment']['evaluation'])
        self.assertEqual([r['proposal'] for r in restored['comparisonOffers']], [r['proposal'] for r in original['comparisonOffers']])
        with page.expect_response(lambda r: r.url.endswith('/api/trades/evaluate') and r.request.method == 'POST') as evaluated:
            page.locator('#trade-run').click()
        self.assertEqual(evaluated.value.status, 200)
        self.assertEqual(evaluated.value.request.post_data_json['protected_assets'], [])
        helper.ready(page, '/trades/recommended')
        self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], ['2029-R1-1','a'])
        page.reload()
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], ['2029-R1-1','a'])
        f.editor.store.upsert_membership('account-a', {'league_id':'league-2','name':'Other'}, 'account-a',1,'Other','active')
        f.editor.store.activate('account-a','league-2')
        f.editor.data['league']['league_id'] = 'league-2'
        helper.ready(page, '/trades/recommended')
        self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], [])
        self.assertEqual(helper.draft(page)['comparisonOffers'], [])
        self.record('draft-and-scope', dict(real_evaluations=2, recommended_controls_not_applied_to_evaluate=True,
                    original_draft_retained=True, comparison_proposals_retained=True, reload_retained=True, league_switch_cleared=True))

    def test_no_qualified_offers_keeps_applied_restrictions_and_real_completion(self):
        helper, f, page, requests = self.fixture()
        helper.ready(page, '/trades/recommended')
        options = page.locator('#recommendation-protection-asset option').evaluate_all('es=>es.map(e=>e.value).filter(Boolean)')
        for exact in options:
            self.protect(page, exact)
        payload, body = self.generate(page)
        self.assertEqual(set(payload['protected_assets']), set(options))
        self.assertFalse(body.get('results'))
        self.assertFalse(body.get('exploratory_results'))
        self.assertIn('No qualified recommendations', page.locator('#trade-result').inner_text())
        self.assertIn('do not establish why no offer qualified', page.locator('#trade-result').inner_text())
        self.assertEqual(len(helper.draft(page)['recommendedSearch']['protections']), len(options))
        self.record('completed-zero-result', dict(payload=payload, body=body, completed=True, no_protection_causality_claim=True), page)
