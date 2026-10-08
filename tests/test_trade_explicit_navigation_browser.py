"""Explicit dossier actions outrank unrelated drafts; history/reload retain theirs."""
from copy import deepcopy
from html import escape
from time import perf_counter
import unittest
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from src.ui.player_actions import player_actions_html
from tests.test_canonical_asset_facts import facts_fixture
from tests.test_player_actions import player_app
from tests import test_trade_scout_state_browser as scout


class ExplicitNavigationBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = scout.ScoutWorkspaceStateBrowserTests()
        self.data = self.fixture.workspace()
        names = {'player:x': 'Trey McBride', 'player:y': 'CeeDee Lamb',
                 'player:a': 'Bijan Robinson', 'player:d': 'Another owned player'}
        for team in self.data['teams']:
            for asset in team['assets']:
                asset['label'] = names.get(asset['asset_id'], asset['label'])

    @staticmethod
    def state(page):
        return page.evaluate("JSON.parse(sessionStorage.getItem('dtos-trade-workspace:scout-session'))")

    def dossiers(self, page):
        def dossier(route):
            aid = 'player:' + urlsplit(route.request.url).path.rsplit('/', 1)[-1]
            owner = next(t for t in self.data['teams'] if any(a['asset_id'] == aid for a in t['assets']))
            asset = next(a for a in owner['assets'] if a['asset_id'] == aid)
            ownership = {'state': 'OWNED_BY_ME' if owner['roster_id'] == 1 else 'OWNED_BY_OTHER',
                         'actions': ['VIEW_PLAYER', 'SHOP_ASSET' if owner['roster_id'] == 1 else 'TRADE_FOR'],
                         'owner': owner, 'label': owner['team_name'], 'reason': ''}
            route.fulfill(content_type='text/html', body='<h1>' + escape(asset['label']) + '</h1>' +
                          player_actions_html(ownership, aid, 1))
        page.route('**/players/*', dossier)

    def select(self, page, workflow, aid):
        page.goto('https://dtos.test/players/' + aid.removeprefix('player:'))
        page.get_by_role('link', name='Shop Asset' if workflow == 'shop' else 'Trade For', exact=True).click()
        page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()

    def assert_target(self, page, workflow, aid):
        state = self.state(page)
        outgoing = workflow == 'shop'
        self.assertEqual(state['originWorkflow'], 'shop' if outgoing else 'trade_for')
        self.assertEqual(state['requiredOutgoingAsset'], aid if outgoing else None)
        self.assertEqual(state['requiredIncomingAsset'], None if outgoing else aid)
        self.assertEqual(state['currentProposal'], {'sent': [aid] if outgoing else [],
            'received': [] if outgoing else [aid], 'partner': 0 if outgoing else 2})
        label = next(a['label'] for t in self.data['teams'] for a in t['assets'] if a['asset_id'] == aid)
        self.assertIn(label, page.locator('#trade-target').inner_text())
        self.assertIn('shopping' if outgoing else 'want', page.locator('#trade-target h3').inner_text())
        self.assertNotIn('could not verify', page.locator('#trade-result').inner_text())

    def test_dossier_target_and_workflow_matrix_same_tab_reload_and_fresh_tab(self):
        cases = [('trade-for', 'player:x', 'trade-for', 'player:y'),
                 ('trade-for', 'player:y', 'shop', 'player:a'),
                 ('shop', 'player:a', 'shop', 'player:d'),
                 ('shop', 'player:a', 'trade-for', 'player:y'),
                 ('trade-for', 'player:y', 'trade-for', 'player:x'),
                 ('shop', 'player:d', 'trade-for', 'player:x')]
        for width in (320, 375, 390):
            for old_flow, old_id, new_flow, new_id in cases:
                with self.subTest(width=width, old=(old_flow, old_id), new=(new_flow, new_id)), \
                        self.fixture.page(width, workspace=self.data) as (page, _):
                    self.dossiers(page)
                    self.fixture.ready(page, f'/trades/{old_flow}?asset_id={old_id}')
                    self.select(page, new_flow, new_id)
                    self.assert_target(page, new_flow, new_id)
                    same_tab = self.state(page)['currentProposal']
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
                    self.assertTrue(page.locator('#trade-target').is_visible())
                    self.assertTrue(page.locator('#trade-find').is_enabled())
                    page.reload()
                    page.locator('#trade-target:not([hidden])').wait_for()
                    self.assert_target(page, new_flow, new_id)
                    fresh = page.context.new_page()
                    self.fixture.ready(fresh, f'/trades/{new_flow}?asset_id={new_id}')
                    self.assertEqual(self.state(fresh)['currentProposal'], same_tab)
                    fresh.close()

    def test_new_intent_clears_adopted_package_preview_and_constraints_but_not_exact_locks(self):
        with self.fixture.page(workspace=self.data) as (page, requests):
            self.dossiers(page)
            self.fixture.ready(page, '/trades/shop?asset_id=player:a')
            locks = ['player:b', 'pick:2028:1:3']
            page.locator('#shop-protected').select_option(locks)
            page.click('#trade-find')
            self.fixture.adopt(page)
            page.click('#trade-adjust')
            page.fill('#trade-instruction', 'make it cheaper')
            page.click('#trade-apply-adjust')
            page.get_by_role('button', name='Open editable offer:', exact=False).click()
            self.assertIsNotNone(self.state(page)['previewProposal'])
            self.select(page, 'trade-for', 'player:y')
            self.assert_target(page, 'trade-for', 'player:y')
            state = self.state(page)
            for key in ('originalProposal', 'adoptedProposal', 'previewProposal'):
                self.assertIsNone(state[key])
            self.assertEqual(state['adjustmentConstraints'], {})
            self.assertEqual(state['protectedAssets'], locks)
            self.assertIn('previous package was cleared', page.locator('#trade-result').inner_text())
            page.click('#trade-find')
            self.fixture.adopt(page)
            self.assertEqual(requests[-1][1]['asset_id'], 'player:y')
            self.assertEqual(requests[-1][1]['protected_assets'], locks)
            self.assertTrue(set(locks).isdisjoint(self.state(page)['currentProposal']['sent']))
            # Returning to Shop must expose and enforce the same exact locks.
            self.select(page, 'shop', 'player:d')
            self.assertEqual(page.locator('#shop-protected').evaluate('n => [...n.selectedOptions].map(o => o.value)'), locks)

    def test_each_history_entry_restores_its_own_adopted_package_not_latest_global_draft(self):
        with self.fixture.page(workspace=self.data) as (page, _):
            self.dossiers(page)
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            self.fixture.adopt(page)
            adopted = self.state(page)['currentProposal']
            self.select(page, 'trade-for', 'player:y')
            self.assert_target(page, 'trade-for', 'player:y')
            page.go_back()
            page.get_by_role('link', name='Trade For', exact=True).wait_for()
            page.go_back()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(self.state(page)['currentProposal'], adopted)
            self.assertEqual(self.state(page)['requiredIncomingAsset'], 'player:x')
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(self.state(page)['currentProposal'], adopted)
            page.go_forward()
            page.get_by_role('link', name='Trade For', exact=True).wait_for()
            page.go_forward()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assert_target(page, 'trade-for', 'player:y')

    def test_legacy_draft_without_history_entry_preserves_matching_reload_and_repairs_wrong_target(self):
        with self.fixture.page(workspace=self.data) as (page, _):
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            self.fixture.adopt(page)
            adopted = self.state(page)['currentProposal']
            page.evaluate('history.replaceState(null, "")')
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(self.state(page)['currentProposal'], adopted)
            # Mimic v1.21.15's persisted wrong target on a retained newer URL.
            page.evaluate('history.replaceState(null, "", "?asset_id=player:y")')
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assert_target(page, 'trade-for', 'player:y')

    def test_pending_old_search_cannot_restore_old_intent_after_new_dossier_selection(self):
        pending = []

        def hold(route, payload):
            pending.append((route, payload))

        with self.fixture.page(workspace=self.data, api=hold) as (page, requests):
            self.dossiers(page)
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
            old_route = pending[0][0]
            # BF-cache retains a document, but its old run loses result ownership.
            page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted: true}))')
            self.select(page, 'shop', 'player:a')
            self.assert_target(page, 'shop', 'player:a')
            old_route.fulfill(json={'results': [self.fixture.offer(['player:d'], ['player:x'])], 'count': 1})
            page.click('#trade-find')
            page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
            self.assertEqual(requests[-1][1]['asset_id'], 'player:a')
            pending[-1][0].fulfill(json={'markets': [{'counterparty_roster_id': 2,
                'returns': [self.fixture.offer(['player:a'], ['player:y'])]}]})
            page.locator('.tw-offer').wait_for()
            self.assert_target(page, 'shop', 'player:a')
            self.assertNotIn('Trey McBride', page.locator('#trade-result').inner_text())

    def test_history_draft_cannot_cross_fresh_authorized_binding(self):
        with self.fixture.page(workspace=self.data) as (page, _):
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            self.fixture.adopt(page)
            foreign = deepcopy(self.state(page))
            foreign['protectedAssets'] = ['pick:2028:1:3']
            page.evaluate('(draft) => history.replaceState({dtosTrade: {binding:"different-account-league", workflow:"trade_for", preload:"player:x", draft}}, "")', foreign)
            page.evaluate('sessionStorage.clear()')
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assert_target(page, 'trade-for', 'player:x')
            self.assertEqual(self.state(page)['protectedAssets'], [])
            self.assertEqual(page.evaluate('history.state.dtosTrade.binding'), 'scout-session')

    def test_free_agent_deep_link_still_server_blocked_even_with_saved_offer(self):
        with TestClient(player_app(facts_fixture())) as client, self.fixture.page(workspace=self.data) as (page, _):
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            self.fixture.adopt(page)

            def blocked(route):
                response = client.get('/trades/trade-for?front_office=1&asset_id=free')
                self.assertEqual(response.status_code, 422)
                route.fulfill(status=response.status_code, content_type='text/html', body=response.content)

            page.route('**/trades/trade-for?asset_id=free', blocked)
            page.goto('https://dtos.test/trades/trade-for?asset_id=free')
            self.assertIn('Free Agent', page.locator('body').inner_text())
            self.assertEqual(page.locator('#trade-builder').count(), 0)

    def test_history_state_preserves_other_consumers_and_contains_no_result_universe(self):
        with self.fixture.page(workspace=self.data) as (page, requests):
            self.fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.evaluate('history.replaceState({...history.state, unrelated:"retain"}, "")')
            page.get_by_label('Your strategy', exact=True).select_option('WIN NOW')
            started = perf_counter()
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            entry = page.evaluate('history.state')
            self.assertEqual(entry['unrelated'], 'retain')
            self.assertLess(len(str(entry)), 4096)
            self.assertNotIn('results', entry['dtosTrade']['draft'])
            self.assertEqual(requests, [])  # No discovery/upstream request per navigation.
            self.assertLess(perf_counter() - started, 3)

    def test_bfcache_reactivates_its_own_draft_without_reusing_pending_results(self):
        with self.fixture.page(workspace=self.data) as (page, _):
            self.fixture.ready(page, '/trades/shop?asset_id=player:a')
            page.locator('#shop-protected').select_option(['player:b', 'pick:2028:1:3'])
            current = self.state(page)
            page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted: true}))')
            page.evaluate('sessionStorage.removeItem("dtos-trade-workspace:scout-session")')
            page.evaluate('dispatchEvent(new PageTransitionEvent("pageshow", {persisted: true}))')
            self.assertEqual(self.state(page), current)

    def test_late_workspace_load_in_departed_document_cannot_persist_over_newer_intent(self):
        pending = []
        with self.fixture.page(workspace=self.data) as (page, _):
            page.route('**/api/trades/workspace?*', lambda route: pending.append(route))
            page.goto('https://dtos.test/trades/trade-for?asset_id=player:x')
            page.wait_for_function('document.querySelector("#trade-context").textContent.includes("Loading")')
            newer = {'schema': 2, 'originWorkflow': 'trade_for', 'requiredIncomingAsset': 'player:y',
                     'requiredOutgoingAsset': None, 'currentProposal': {'sent': [], 'received': ['player:y'], 'partner': 2}}
            page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted:true}))')
            page.evaluate('draft => sessionStorage.setItem("dtos-trade-workspace:scout-session", JSON.stringify(draft))', newer)
            page.evaluate('sessionStorage.setItem("dtos-trade-workspace:new-authorized-binding", "new league draft")')
            pending[0].fulfill(json=self.data)
            page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
            self.assertEqual(self.state(page), newer)
            self.assertEqual(page.evaluate('sessionStorage.getItem("dtos-trade-workspace:new-authorized-binding")'), 'new league draft')


if __name__ == '__main__':
    unittest.main()
