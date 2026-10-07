"""Responsive Chromium navigation, bounded recovery and pending intent guards."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from urllib.parse import urlsplit

from routes.transactions import create_transactions_router
from services import trade_intelligence as trade
from tests import test_make_it_cheaper_browser as cheaper
from tests import test_trade_scout_state_browser as scout


class TradeNavigationBrowserTests(unittest.TestCase):
    def test_cheaper_build_own_dossier_trade_for_recovers_without_reload(self):
        fixture = cheaper.CheaperRepairBrowserTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        async def fresh():
            pass

        fixture.account.client.app.include_router(create_transactions_router(
            ensure_fresh=fresh, require_data=lambda: fixture.account.data,
            refresh_transactions=fresh, state={}, page=lambda title, body: body))
        original = trade.evaluate_trade_request
        for width in (320, 375, 390):
            responses = []
            published = False

            def evaluate(data, payload, **kwargs):
                nonlocal published
                result = original(data, payload, **kwargs)
                if payload.get('workflow') == 'trade_for' and not published:
                    data['market_data']['generation'] = 'phone-publication-' + str(width)
                    published = True
                return result

            initial = fixture.handler(['daniels', '2029-R3-1'])

            def api(route, payload):
                if payload.get('workflow') != 'trade_for':
                    return initial(route, payload)
                response = fixture.account.client.post(urlsplit(route.request.url).path,
                    json=payload, headers={'X-CSRF-Token': fixture.account.csrf})
                responses.append((response.status_code, response.json()))
                route.fulfill(status=response.status_code, json=response.json())

            with self.subTest(width=width), patch('services.trade_intelligence.evaluate_trade_request', side_effect=evaluate), \
                    fixture.harness.page(width, workspace=fixture.workspace, api=api) as (page, requests):
                fixture.start_offer(page)
                fixture.cheaper(page)
                card = page.locator('.tw-offer').filter(has_text='763 → 751')
                card.get_by_role('button', name='Open editable offer:', exact=False).click()
                page.get_by_role('button', name='Adopt alternative', exact=True).click()
                adopted = fixture.proposal(page)
                page.reload()
                page.locator('#trade-target:not([hidden])').wait_for()
                self.assertEqual(fixture.proposal(page), adopted)
                page.click('#trade-build-own')
                page.wait_for_url('**/trades/create?*')
                page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()
                self.assertEqual(fixture.proposal(page)['sent'], [])

                def dossier(route):
                    response = fixture.account.client.get('/players/mcbride')
                    self.assertEqual(response.status_code, 200, response.text)
                    route.fulfill(status=200, content_type='text/html', body=response.content)

                page.route('**/players/mcbride', dossier)
                page.goto('https://dtos.test/players/mcbride')
                page.locator('a[href*="/trades/trade-for?"]').first.click()
                page.locator('#trade-target:not([hidden])').wait_for()
                self.assertIn('Trey McBride', page.locator('#trade-target').inner_text())
                self.assertEqual(page.get_by_label('Counterparty', exact=True).input_value(), '2')
                page.get_by_label('Your strategy', exact=True).select_option('WIN NOW')
                page.click('#trade-find')
                page.locator('.tw-offer').first.wait_for()
                self.assertEqual([status for status, _ in responses], [422, 200])
                self.assertEqual(responses[0][1]['detail']['code'], 'canonical_evidence_changed')
                self.assertGreater(responses[1][1]['count'], 0)
                first_request, retry = [payload for _, payload in requests if payload.get('workflow') == 'trade_for']
                self.assertEqual(first_request, retry)
                self.assertEqual(first_request['workspace_context'], fixture.workspace['workspace_context'])
                self.assertEqual(set(first_request['protected_assets']), {'bijan', '2027-R4-3'})
                self.assertEqual(first_request['asset_id'], 'mcbride')
                self.assertNotIn('different account', page.locator('#trade-result').inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
                # History resolves a fresh authorized workspace and real target owner.
                page.go_back()
                page.locator('a[href*="/trades/trade-for?"]').first.wait_for()
                page.go_forward()
                page.locator('#trade-target:not([hidden])').wait_for()
                self.assertEqual(page.get_by_label('Counterparty', exact=True).input_value(), '2')
                page.reload()
                page.locator('#trade-target:not([hidden])').wait_for()
                self.assertEqual(fixture.proposal(page)['received'], ['mcbride'])

    def test_refresh_retry_bounded_and_real_identity_rejection_never_retried(self):
        fixture = scout.ScoutWorkspaceStateBrowserTests()
        for width in (320, 375, 390):
            for code in ('canonical_evidence_changed', 'workspace_context_changed',
                         'unauthorized_franchise', 'unauthorized_league'):
                def reject(route, payload):
                    route.fulfill(status=422, json={'detail': {'code': code, 'message': 'fixture rejection'}})

                with self.subTest(width=width, code=code), fixture.page(width, api=reject) as (page, requests):
                    fixture.ready(page, '/trades/trade-for?asset_id=player:x&owner_roster_id=1')
                    page.click('#trade-find')
                    page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="false"')
                    if code == 'canonical_evidence_changed':
                        self.assertEqual(len(requests), 2)
                        self.assertIn('Try again', page.locator('#trade-result').inner_text())
                        self.assertNotIn('franchise', page.locator('#trade-result').inner_text())
                    else:
                        self.assertEqual(len(requests), 1)
                        self.assertEqual(page.get_by_role('link', name='Open current Trade Center').get_attribute('href'), '/trades')
                    self.assertFalse(page.locator('#trade-find').is_disabled())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)

    def test_old_intent_cannot_retry_or_replace_result_after_strategy_or_navigation(self):
        fixture = scout.ScoutWorkspaceStateBrowserTests()
        for event in ('strategy', 'pagehide', 'retry_strategy'):
            pending = []

            def hold(route, payload):
                pending.append((route, payload))

            with self.subTest(event=event), fixture.page(api=hold) as (page, requests):
                fixture.ready(page, '/trades/recommended')
                page.click('#trade-find')
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                if event == 'retry_strategy':
                    with page.expect_request('**/api/trades/generate'):
                        pending[0][0].fulfill(status=422, json={'detail': {'code': 'canonical_evidence_changed'}})
                    page.wait_for_function('document.querySelector("#trade-result").textContent.includes("once more")')
                    self.assertEqual(len(pending), 2)
                if event in ('strategy', 'retry_strategy'):
                    page.locator('#trade-strategy').select_option('WIN NOW')
                else:
                    # Explicit lifecycle dispatch covers BF-cache behavior that
                    # route interception disables in Chromium's test transport.
                    page.evaluate('dispatchEvent(new PageTransitionEvent("pagehide", {persisted: true}))')
                    self.assertFalse(page.locator('#trade-find').is_disabled())
                    # A restored page may start a newer request before the old
                    # response finishes. Its busy state belongs to that new run.
                    page.click('#trade-find')
                    page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                    pending[0][0].fulfill(json={'results': [fixture.offer(['player:a'], ['player:x'])], 'count': 1})
                    self.assertTrue(page.locator('#trade-find').is_disabled())
                    self.assertEqual(page.locator('.tw-offer').count(), 0)
                    pending[1][0].fulfill(json={'results': [fixture.offer(['player:a'], ['player:x'])], 'count': 1})
                    page.locator('.tw-offer').wait_for()
                    self.assertEqual(len(requests), 2)
                    continue
                pending[-1][0].fulfill(json={'results': [fixture.offer(['player:a'], ['player:x'])], 'count': 1})
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="false"')
                self.assertEqual(len(requests), 2 if event == 'retry_strategy' else 1)
                self.assertEqual(page.locator('.tw-offer').count(), 0)
                self.assertNotIn('Try again', page.locator('#trade-result').inner_text())
                page.click('#trade-find')
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                pending[-1][0].fulfill(json={'results': [fixture.offer(['player:a'], ['player:x'])], 'count': 1})
                page.locator('.tw-offer').wait_for()

    def test_changed_authorized_binding_never_restores_another_workspace_draft(self):
        fixture = scout.ScoutWorkspaceStateBrowserTests()
        data = deepcopy(fixture.workspace())
        with fixture.page(workspace=data) as (page, requests):
            fixture.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            fixture.adopt(page)
            self.assertEqual(fixture.proposal(page)['sent'], ['player:a'])
            # Server-selected context after a legitimate league or session change.
            # Colliding roster/asset IDs cannot carry the preceding draft or locks.
            for binding, league in (('same-account-new-league', 'second-league'),
                                    ('other-authenticated-session', 'third-league')):
                data['workspace_context']['binding'] = binding
                data['manager_context']['league_id'] = league
                fixture.ready(page, '/trades/create?front_office=999')
                saved = page.evaluate('key => JSON.parse(sessionStorage.getItem(key))',
                                      'dtos-trade-workspace:' + binding)
                self.assertEqual(saved['currentProposal'], {'sent': [], 'received': [], 'partner': 0})
                self.assertEqual(saved['protectedAssets'], [])
                self.assertIn(league, page.locator('#trade-context').inner_text())
            # An isolated browser session has no access to that tab's proposal.
        with fixture.page() as (page, requests):
            fixture.ready(page, '/trades/create')
            self.assertEqual(fixture.proposal(page), {'sent': [], 'received': [], 'partner': 0})

