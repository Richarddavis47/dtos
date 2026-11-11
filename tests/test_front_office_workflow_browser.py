"""One prepared Home -> real search -> evaluation/comparison/history journey.

Disposable authenticated 1QB/K/DEF and Superflex leagues; native evaluator and
search outcomes, including zero qualified offers. Chromium touch emulation is
not physical Safari evidence.
"""
from copy import deepcopy
from html import unescape
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from tests import test_offer_comparison_browser as comparison
from tools.validation.browser_runtime import launch_chromium


VIEWPORTS = ((320, 432), (375, 667), (390, 844), (1280, 900))


class FrontOfficeWorkflowBrowserTests(unittest.TestCase):
    def fixture(self, *, superflex):
        from routes.history import create_history_router
        from src.core.history_context.season_cache import SleeperSeasonCache
        from src.core.history_context.store import CanonicalHistoryStore
        import dtos_app

        offers = comparison.OfferComparisonBrowserTests()
        self.addCleanup(offers.doCleanups)
        source, helper, f = offers.fixture(superflex=superflex)
        for original in (1, 3):
            f.editor.data['teams'][0]['picks_owned'].append(dict(
                year=2029, round=1, original_roster_id=original, current_owner_id=1))
        quote = dict(f.editor.data['market_data']['pick_quotes']['FantasyCalc'][0], year=2029, value=334 * 12)
        quote['normalization_reference'] = dict(quote['normalization_reference'], raw_value=334 * 12, normalized_value=334)
        f.editor.data['market_data']['pick_quotes']['FantasyCalc'].append(quote)
        f.capital.publish()
        source.publish(f)
        directory = self.enterContext(tempfile.TemporaryDirectory())
        cache = SleeperSeasonCache(Path(directory))
        store = CanonicalHistoryStore()
        self.enterContext(patch('src.core.history_context.store.sleeper_season_cache', cache))
        self.enterContext(patch('services.history.historical_store', store))
        self.enterContext(patch('services.history.canonical_history_store', store))
        store.update_current('league-1', f.editor.data)
        f.editor.app.include_router(create_history_router(
            league_id='league-1', page=dtos_app.page, require_data=lambda: f.editor.data,
            league_resolver=lambda: f.editor.data['league']['league_id']))

        # Use the existing explicit preference save; temporary Trade intent must
        # not become a second way to change the saved franchise goal.
        context = f.editor.client.get('/api/trades/workspace?front_office=1').json()['workspace_context']
        saved = f.editor.client.post('/account/franchise-goal', data={
            'strategy': 'WIN NOW', 'expected_revision': str(context['franchise_goal_revision']),
            'league_id': context['league_id'], 'roster_id': '1', 'csrf_token': f.editor.csrf,
            'strategy_scope': context['strategy_scope'],
        }, follow_redirects=False)
        self.assertEqual(saved.status_code, 303, saved.text)
        team = f.editor.client.get('/teams/1')
        match = re.search(r'id="my-team-trade-need"[^>]*href="([^"]+)"[^>]*>Explore (QB|RB|WR|TE) trades', team.text)
        self.assertIsNotNone(match)
        return offers, source, helper, f, unescape(match[1]), match[2]

    def record(self, name, observations, page=None):
        folder = os.environ.get('DTOS_FRONT_OFFICE_WORKFLOW_EVIDENCE')
        if not folder:
            return
        destination = Path(folder)
        destination.mkdir(parents=True, exist_ok=True)
        report = dict(
            commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
            working_tree_clean=not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip(),
            source='Disposable authenticated prepared Sleeper fixture; native search and canonical evaluator',
            physical_safari_tested=False, observations=observations)
        (destination / (name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
        if page:
            page.screenshot(path=str(destination / (name + '.png')), full_page=True)

    def screenshot(self, name, page):
        folder = os.environ.get('DTOS_FRONT_OFFICE_WORKFLOW_EVIDENCE')
        if folder:
            destination = Path(folder)
            destination.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(destination / (name + '.png')), full_page=True)

    def protect(self, page, exact_id):
        options = page.locator('#trade-search-options')
        if not options.evaluate('e=>e.open'):
            options.locator('summary').press('Enter')
        page.select_option('#recommendation-protection-asset', exact_id)
        page.locator('#recommendation-protection-add').press('Enter')

    def touch(self, page, locator):
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        self.assertGreaterEqual(box['height'], 44)
        cdp = page.context.new_cdp_session(page)
        try:
            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
                {'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
        finally:
            cdp.detach()

    def evaluate(self, page, helper, target, *, with_pick=False):
        """Use Calculator's visible asset boards; phone side tabs are absent."""
        if page.locator('#trade-board').is_hidden():
            page.locator('#trade-edit').click()
        page.select_option('#trade-partner', '2')
        page.select_option('#trade-strategy', 'WIN NOW')
        for side, selected, desired in (
            ('sent', 'sent', ['2028-R1-3', 'a'] if with_pick else ['a']),
            ('received', 'received', [target]),
        ):
            switch = page.locator(f'[data-side={side}]')
            if switch.is_visible():
                switch.click()
            current = helper.draft(page)['currentProposal']
            for asset_id in list(current[selected]):
                page.locator(f'#trade-{side}-board button[data-asset-id="{asset_id}"]').click()
            for asset_id in desired:
                page.locator(f'#trade-{side}-board button[data-asset-id="{asset_id}"]').click()
        with page.expect_response(lambda response: response.url.endswith('/api/trades/evaluate') and response.request.method == 'POST') as evaluated:
            page.locator('#trade-run').click()
        self.assertEqual(evaluated.value.status, 200, evaluated.value.text())
        body = evaluated.value.json()
        self.assertIn('evaluation', body, body)
        self.assertEqual(evaluated.value.request.post_data_json['protected_assets'], [])
        page.locator('#trade-result > .tw-compare-add').wait_for()
        return body['evaluation']

    def history_return(self, helper, page, requests, *, touch):
        """Native History and Back preserve Calculator's normal query context."""
        link = page.locator('#trade-result .tw-partner-history').first
        self.assertEqual(link.inner_text(), 'See franchise trade history')
        self.assertIn('league-1%3Afranchise%3A2', link.get_attribute('href'))
        before = [row for row in requests if row[0] == 'POST']
        if touch:
            self.touch(page, link)
        else:
            page.keyboard.press('Tab')
            link.focus()
            self.assertNotEqual(link.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
            link.press('Enter')
        page.wait_for_url('**/history/team/league-1%3Afranchise%3A2')
        self.assertIn('Completed trade observations', page.locator('body').inner_text())
        self.assertIn('totals are unknown', page.locator('body').inner_text())
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), page.viewport_size['width'])
        helper.back(page, '/trades/calculator?front_office=1')
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        page.locator('#trade-result .tw-partner-history').first.wait_for()
        self.assertEqual([row for row in requests if row[0] == 'POST'], before)
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), page.viewport_size['width'])

    def journey(self, *, superflex):
        offers, _source, helper, f, need_href, position = self.fixture(superflex=superflex)
        label = 'superflex' if superflex else '1qb-k-def'
        baseline = deepcopy(f.editor.state())
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        self.addCleanup(page.close)
        post_ledger = []
        def observed(response):
            request = response.request
            path = urlsplit(response.url).path
            if request.method == 'POST' and path.startswith('/api/trades/'):
                post_ledger.append(dict(path=path, status=response.status, payload=request.post_data_json))
        page.on('response', observed)
        def posts():
            return [request for request in requests if request[0] == 'POST']
        page.goto(helper.origin + '/')
        page.locator('#home-opportunity-cards article').first.wait_for()
        leading = page.locator('#home-opportunity-cards article').first
        action = leading.get_by_role('link', name=f'Explore {position} trades')
        self.assertEqual(action.get_attribute('href'), need_href)
        self.assertIn('Cost and uncertainty', leading.inner_text())
        home_views = []
        for width, height in VIEWPORTS:
            page.set_viewport_size(dict(width=width, height=height))
            action.scroll_into_view_if_needed()
            action.focus()
            self.assertNotEqual(action.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
            self.assertGreaterEqual(action.bounding_box()['height'], 44)
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            home_views.append(dict(width=width, height=height, title=leading.locator('h3').inner_text(),
                                   action=action.inner_text(), href=action.get_attribute('href')))
            self.screenshot(f'{label}-home-{width}', page)
        self.assertEqual(posts(), [])
        action.press('Enter')
        page.wait_for_function("document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')")
        self.assertEqual(page.locator('#recommendation-position').input_value(), position)
        origin = page.locator('#recommendation-position-origin').inner_text()
        self.assertIn(f'{position} addition', origin)
        self.assertIn('Change or clear, then Generate', origin)
        self.assertEqual(posts(), [])
        initial = helper.draft(page)
        self.protect(page, '2029-R1-1')
        self.protect(page, 'a')
        self.assertIn('2029-R1-3', page.locator('#recommendation-protection-asset option').evaluate_all('es=>es.map(e=>e.value)'))
        protection_views = []
        for width, height in VIEWPORTS:
            page.set_viewport_size(dict(width=width, height=height))
            selected = page.locator('#recommendation-protection-list')
            self.assertIn('2029-R1-1', selected.inner_text())
            self.assertIn('Exact asset: a', selected.inner_text())
            self.assertIn('Original franchise:', selected.inner_text())
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            protection_views.append(dict(width=width, height=height, exact_ids=helper.draft(page)['recommendationProtectedAssets']))
            if width == 390:
                self.touch(page, page.locator('[data-protected-asset="a"]'))
                self.assertEqual(helper.draft(page)['recommendationProtectedAssets'], ['2029-R1-1'])
                self.protect(page, 'a')
        self.assertEqual(posts(), [])

        # Observe the actual outgoing pools; no generated response or verdict is
        # substituted. Zero qualified offers remain a successful completed read.
        import services.recommended_trade_search as search
        original_generate = search.generate_proposals
        outgoing_pools = []
        def observe(*args, **kwargs):
            outgoing_pools.append([asset.asset_id for asset in args[2]])
            return original_generate(*args, **kwargs)
        with patch.object(search, 'generate_proposals', side_effect=observe):
            with page.expect_response(lambda response: response.url.endswith('/api/trades/generate') and response.request.method == 'POST') as generated:
                page.locator('#trade-find').press('Enter')
            self.assertEqual(generated.value.status, 200, generated.value.text())
            payload, body = generated.value.request.post_data_json, generated.value.json()
        page.wait_for_function("document.querySelector('#recommendation-status').dataset.state==='complete'")
        self.assertEqual(payload['recommendation_position'], position)
        self.assertEqual(set(payload['protected_assets']), {'2029-R1-1', 'a'})
        self.assertEqual(set(body['constraints']['protected_assets']), {'2029-R1-1', 'a'})
        self.assertTrue(outgoing_pools, 'Native candidate construction must run')
        self.assertTrue(any('2029-R1-3' in pool for pool in outgoing_pools))
        for pool in outgoing_pools:
            self.assertTrue(set(pool).isdisjoint({'2029-R1-1', 'a'}))
        native = []
        for family in ('results', 'exploratory_results', 'near_misses'):
            for row in body.get(family, []):
                proposal, evaluation = row['proposal'], row['evaluation']
                self.assertTrue(set(proposal['assets_sent']).isdisjoint({'2029-R1-1', 'a'}))
                native.append(dict(family=family, proposal=proposal,
                                   recommendation=evaluation.get('recommendation'),
                                   generated_trade_eligible=evaluation.get('generated_trade_eligible'),
                                   exploration=row.get('exploration', False)))
        if not any(row['family'] == 'results' and row['generated_trade_eligible'] is True for row in native):
            self.assertIn('No qualified recommendations', page.locator('#trade-result').inner_text())
        self.assertEqual(len(posts()), 1)
        prior = deepcopy(helper.draft(page)['recommendedSearch'])
        self.assertEqual(prior['position'], position)
        self.assertEqual({row['id'] for row in prior['protections']}, {'2029-R1-1', 'a'})
        self.assertIn('2029-R1-1', page.locator('#trade-result .tw-applied-protections').inner_text())
        page.locator('#recommendation-protection-clear').press('Enter')
        page.locator('#recommendation-position-clear').press('Enter')
        edited_choice = deepcopy(helper.draft(page)['teamNeedChoice'])
        self.assertEqual(helper.draft(page)['recommendedSearch'], prior)
        self.assertTrue(page.locator('#trade-result').is_hidden())
        previous = page.locator('#recommendation-previous')
        previous.locator('summary').press('Enter')
        self.assertIn(f'Earlier search: {position}', previous.inner_text())
        self.assertIn('2029-R1-1', previous.inner_text())
        self.assertEqual(len(posts()), 1)
        self.assertEqual(helper.draft(page)['currentProposal'], initial['currentProposal'])

        # These two independent native assessments do not depend on discovery
        # finding two qualified offers under the real position/pricing evidence.
        page.locator('.tw-intent-nav a[href*="/trades/calculator"]').press('Enter')
        page.wait_for_url('**/trades/calculator?front_office=1')
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        first = self.evaluate(page, helper, 'd')
        page.locator('#trade-result > .tw-compare-add').press('Enter')
        second = self.evaluate(page, helper, 'c', with_pick=True)
        page.locator('#trade-result > .tw-compare-add').press('Enter')
        draft = helper.draft(page)
        self.assertEqual(draft['currentProposal']['sent'], ['2028-R1-3', 'a'])
        self.assertEqual(draft['currentProposal']['received'], ['c'])
        self.assertEqual([row['proposal']['assets_received'] for row in draft['comparisonOffers']], [['d'], ['c']])
        self.assertEqual(len([request for request in posts() if request[1] == '/api/trades/evaluate']), 2)
        after_evaluations = list(posts())
        comparison_views = []
        with patch('services.sleeper.sleeper_get', side_effect=AssertionError('Navigation must reuse prepared evidence')):
            for width, height in VIEWPORTS:
                page.set_viewport_size(dict(width=width, height=height))
                offers.open_readonly(page, requests)
                panel = page.locator('#trade-comparison')
                self.assertIn('Keep the roster', panel.inner_text())
                keep_option = panel.locator('.tw-comparison-keep h4').inner_text()
                panel_state = panel.get_attribute('data-comparison-state')
                self.assertEqual(panel.locator('.tw-comparison-offer').count(), 2)
                self.assertEqual(panel.locator('[data-comparison-slot="2"] ol').first.locator('small').all_text_contents(),
                                 ['Exact asset: 2028-R1-3', 'Exact asset: a'])
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                self.screenshot(f'{label}-comparison-{width}', page)
                close = page.get_by_role('button', name='Return to my offer or draft', exact=True)
                if width == 390:
                    self.touch(page, close)
                else:
                    page.keyboard.press('Tab')
                    close.focus()
                    self.assertNotEqual(close.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                    close.press('Enter')
                self.history_return(helper, page, requests, touch=width == 390)
                restored = helper.draft(page)
                for key in ('currentProposal', 'valuationMode', 'strategy'):
                    self.assertEqual(restored[key], draft[key])
                self.assertEqual([row['proposal'] for row in restored['comparisonOffers']],
                                 [row['proposal'] for row in draft['comparisonOffers']])
                self.assertEqual(restored['currentAssessment']['identity']['package'], draft['currentAssessment']['identity']['package'])
                self.assertIn('not revalidated', page.locator('#trade-result').inner_text().lower())
                self.assertEqual(posts(), after_evaluations)
                comparison_views.append(dict(width=width, height=height, exact_draft=restored['currentProposal'],
                                             panel_state=panel_state, keep_option=keep_option,
                                             comparison_retained=restored['comparisonOffers'][0].get('retained'),
                                             history_qualification=page.locator('#trade-result').get_attribute('data-assessment-freshness'),
                                             history_return_without_post=True))

        page.reload()
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        offers.open_readonly(page, requests)
        reload_state = page.locator('#trade-comparison').get_attribute('data-comparison-state')
        self.assertEqual(reload_state, 'retained')
        self.assertIn('NOT REVALIDATED', page.locator('#trade-comparison').inner_text())
        self.assertEqual(posts(), after_evaluations)
        page.get_by_role('button', name='Return to my offer or draft', exact=True).press('Enter')
        self.evaluate(page, helper, 'f')
        page.locator('#trade-result > .tw-compare-add').press('Enter')
        self.assertIn('Two offers are selected', page.locator('.tw-comparison-replace').inner_text())
        page.get_by_role('button', name='Replace offer 1', exact=True).press('Enter')
        self.assertEqual(helper.draft(page)['comparisonOffers'][0]['proposal']['assets_received'], ['f'])
        replaced = [deepcopy(row['proposal']) for row in helper.draft(page)['comparisonOffers']]
        last_draft = helper.draft(page)['currentProposal']
        offers.open_readonly(page, requests)
        page.get_by_role('button', name='Remove offer 1', exact=True).press('Enter')
        self.assertEqual(len(helper.draft(page)['comparisonOffers']), 1)
        remaining = [deepcopy(row['proposal']) for row in helper.draft(page)['comparisonOffers']]
        self.assertEqual(helper.draft(page)['currentProposal'], last_draft)
        self.assertEqual(f.editor.state(), baseline)
        goal = f.editor.client.get('/api/trades/workspace?front_office=1').json()['workspace_context']
        self.assertEqual(goal['franchise_goal'], 'WIN NOW')
        old_binding = goal['binding']
        posts_before_scope = list(posts())
        page.get_by_role('button', name='Return to my offer or draft', exact=True).press('Enter')
        page.locator('.tw-intent-nav a[href*="/trades/recommended"]').press('Enter')
        page.wait_for_url('**/trades/recommended?front_office=1')
        page.wait_for_function("document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')")
        self.protect(page, '2029-R1-1')
        self.protect(page, 'a')
        page.locator('#recommendation-position').select_option('QB')
        before_scope = helper.draft(page)
        self.assertEqual(before_scope['recommendationProtectedAssets'], ['2029-R1-1', 'a'])
        self.assertEqual(len(before_scope['comparisonOffers']), 1)
        self.assertEqual(before_scope['currentProposal'], last_draft)
        self.assertEqual(posts(), posts_before_scope)
        f.editor.store.upsert_membership('account-a', {'league_id': 'league-2', 'name': 'Other'},
                                         'account-a', 1, 'Other', 'active')
        f.editor.store.activate('account-a', 'league-2')
        f.editor.data['league']['league_id'] = 'league-2'
        helper.ready(page, '/trades/recommended?front_office=1')
        cleared = helper.draft(page)
        self.assertEqual(cleared['comparisonOffers'], [])
        self.assertEqual(cleared['recommendationProtectedAssets'], [])
        self.assertIsNone(cleared.get('recommendedSearch'))
        self.assertFalse(cleared['currentProposal']['sent'])
        self.assertFalse(cleared['currentProposal']['received'])
        self.assertEqual(page.locator('#recommendation-position').input_value(), '')
        current = f.editor.client.get('/api/trades/workspace?front_office=1').json()['workspace_context']
        self.assertNotEqual(current['binding'], old_binding)
        self.assertEqual(posts(), posts_before_scope)
        self.assertEqual(len(post_ledger), 4)
        self.assertEqual([row['path'] for row in post_ledger], ['/api/trades/generate'] + ['/api/trades/evaluate'] * 3)
        self.assertFalse(errors, errors)
        self.record(label + '-journey', dict(
            league_slots=f.editor.data['league']['roster_positions'], home=home_views,
            handoff=dict(position=position, href=need_href, explanation=origin, existing_my_team_reused=True,
                         initial_choice=initial['teamNeedChoice'], edited_choice=edited_choice),
            protection_views=protection_views, generation_payload=payload,
            applied_constraints=body['constraints'], outgoing_pools=outgoing_pools,
            exact_protected_ids=['2029-R1-1', 'a'], distinct_same_round_pick='2029-R1-3',
            distinct_pick_remained_eligible=any('2029-R1-3' in pool for pool in outgoing_pools), native_offers=native,
            search_evidence=body.get('search_evidence'),
            prior_search={key: prior[key] for key in ('position', 'type', 'count', 'protections')},
            actual_evaluations=[dict(recommendation=e.get('recommendation'),
                                     lineup=e.get('decision_context', {}).get('lineup'),
                                     market=e.get('market_evidence')) for e in (first, second)],
            comparison_offers=[{key: row[key] for key in ('scope', 'baseline', 'proposal', 'summary')}
                               | {'identity': row['context']['identity']} for row in draft['comparisonOffers']],
            comparison_and_history=comparison_views, post_requests=posts(), post_ledger=post_ledger,
            reload_retained=reload_state == 'retained',
            replacement=dict(selected_proposals=replaced, remaining_proposals=remaining, draft=last_draft),
            scope_change=dict(old=old_binding, current=current['binding'], temporary_state_cleared=True,
                              before_protections=before_scope['recommendationProtectedAssets'],
                              before_position=before_scope['teamNeedChoice']['position'],
                              before_draft=before_scope['currentProposal']),
            saved_goal_and_rankings_unchanged=True), page)

    def test_1qb_k_def_normal_front_office_journey(self):
        self.journey(superflex=False)

    def test_superflex_normal_front_office_journey(self):
        self.journey(superflex=True)
