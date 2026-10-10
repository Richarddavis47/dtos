"""Real canonical publisher/evaluator, rendered workspace, intercepted transport.

Collection placement is controlled; numerical results are never mocked. These
are disposable-source Chromium fixtures, not authenticated production evidence.
"""
from dataclasses import asdict
import unittest

from services.trade_intelligence import build_trade_workspace
from tests import test_trade_scout_state_browser as scout
from tests.test_trade_projection_freshness import PublishedTradeEvidence


class ProjectionFreshnessBrowserTests(unittest.TestCase):
    def setUp(self):
        self.source = PublishedTradeEvidence(self)
        self.harness = scout.ScoutWorkspaceStateBrowserTests()
        self.workspace = {'workspace_context': {'binding': 'scout-session', 'ownership_generation': 'owned'},
            'manager_context': {'league_id': 'league-1'}, 'csrf_token': 'fixture',
            'calculator_generation': 'market-one'}
        self.refresh_workspace()
        self.pending = []
        self.collection = 'exploratory_results'
        self.other_offer = False

    def refresh_workspace(self):
        w = build_trade_workspace(self.source.data, 1)
        self.workspace['projection_evidence'] = w['projection_evidence']
        self.workspace['teams'] = [{'roster_id': t['roster_id'], 'team_name': t['team_name'],
            'assets': [asdict(a) for a in w['pools'][t['roster_id']]]} for t in w['teams']]

    @staticmethod
    def click(page, selector):
        p = page.locator(selector).first
        p.scroll_into_view_if_needed()
        assert p.evaluate('e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
        p.click()

    def response(self, route, payload):
        row = self.source.assess(['b'], ['d']) if self.other_offer else self.source.assess()
        row.update(exploration=True, search_result_type='SUPPORTED FIXTURE ALTERNATIVE', workflow='trade_for')
        if route.request.url.endswith('/evaluate'):
            route.fulfill(json={'evaluation': row['evaluation']})
        elif route.request.url.endswith('/balance'):
            self.pending.append((route, row))
        else:
            body = {'results': [], 'count': 0}
            if self.collection == 'markets':
                body['markets'] = [{'counterparty_roster_id': 2, 'returns': [row]}]
            else:
                body[self.collection] = [row]
            route.fulfill(json=body)

    def original(self, page, expected='NOT WORTH IT'):
        self.harness.ready(page, '/trades/trade-for?asset_id=c')
        page.select_option('#trade-strategy', 'WIN NOW')
        self.click(page, '#trade-find')
        self.click(page, '.tw-offer .tw-next-action')
        self.click(page, '#trade-result button:text-is("Adopt alternative")')
        self.assertIn(expected, page.locator('#trade-result').inner_text())

    def test_changed_exploratory_only_source_preview_keep_original_and_reevaluate(self):
        for width, height in ((320,483),(320,568),(375,483),(375,667),(390,483),(390,844),(1280,900)):
            self.source.publish(8)
            self.refresh_workspace()
            with self.subTest(width=width,height=height), self.harness.page(width,workspace=self.workspace,api=self.response) as (page, requests):
                page.set_viewport_size({'width':width,'height':height})
                self.original(page)
                original = self.harness.proposal(page)
                self.source.publish()
                self.click(page, '#trade-find')
                self.click(page, '.tw-offer .tw-next-action')
                self.click(page, '#trade-result button:text-is("Keep original")')
                retained = page.locator('#trade-evaluation-retained').inner_text()
                self.assertIn('Source evidence changed', retained)
                self.assertIn('NOT WORTH IT', retained)
                self.assertIn('Major drawback', retained)
                self.assertEqual(self.harness.proposal(page), original)
                self.click(page, '[data-reevaluate]')
                page.locator('#trade-result').get_by_text('SMASH ACCEPT',exact=False).first.wait_for()
                self.assertNotIn('not revalidated', page.locator('#trade-result').inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width+1)
                page.locator('#trade-run').focus()
                self.assertEqual(page.evaluate('document.activeElement.id'),'trade-run')

    def test_reload_changed_source_keep_or_adopt_then_balance_retains_warning(self):
        for adopt in (False,True):
            # This separate negative-offer case has a genuine 10-point overpay,
            # so Balance is available. The exact Scout transition stays equal
            # priced in the backend and phone fixtures above.
            self.source.fixture.prices(a=260)
            self.source.publish(8)
            self.refresh_workspace()
            with self.subTest(adopt=adopt), self.harness.page(workspace=self.workspace,api=self.response) as (page, requests):
                self.original(page, expected='REJECT')
                self.click(page,'#trade-find')
                self.click(page,'.tw-offer .tw-next-action')
                original = self.harness.proposal(page)
                self.source.publish()
                self.refresh_workspace()
                page.reload()
                page.get_by_role('button',name='Adopt alternative',exact=True).wait_for()
                self.assertIn('projection evidence changed',page.locator('#trade-result').inner_text())
                self.click(page,'#trade-result button:text-is("'+('Adopt alternative' if adopt else 'Keep original')+'")')
                self.assertEqual(self.harness.proposal(page),original)
                self.assertIn('REJECT',page.locator('#trade-result').inner_text())
                self.assertIn('not revalidated',page.locator('#trade-result').inner_text())
                self.click(page,'#trade-balance-offer')
                page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="true"')
                self.assertIn('Major drawback',page.locator('#trade-evaluation-retained').inner_text())
                self.assertIn('projection evidence changed',page.locator('#trade-evaluation-retained').inner_text())
                route,row=self.pending.pop()
                route.fulfill(json={'results':[row],'count':1})
                page.wait_for_function('!document.querySelector("#trade-balance-offer").disabled')
                self.assertIn('REJECT',page.locator('#trade-evaluation-retained').inner_text())

    def test_all_assessed_collections_and_same_source_different_offer_control(self):
        for collection in ('results','exploratory_results','near_misses','comparisons','markets'):
            self.source.publish(8)
            self.refresh_workspace()
            self.collection='exploratory_results'
            with self.subTest(collection=collection), self.harness.page(workspace=self.workspace,api=self.response) as (page, requests):
                self.original(page)
                # A new evaluation ID/result is not a new projection source.
                self.collection=collection
                self.other_offer=True
                self.click(page,'#trade-find')
                page.wait_for_function('!document.querySelector("#trade-find").disabled')
                draft=page.evaluate("JSON.parse(sessionStorage.getItem('dtos-trade-workspace:scout-session'))")
                self.assertFalse(draft['currentAssessment'].get('restored',False))
                self.source.publish()
                self.other_offer=False
                self.click(page,'#trade-find')
                page.wait_for_function('!document.querySelector("#trade-find").disabled')
                draft=page.evaluate("JSON.parse(sessionStorage.getItem('dtos-trade-workspace:scout-session'))")
                self.assertTrue(draft['currentAssessment']['restored'])
                self.assertIn('Source evidence changed',draft['currentAssessment']['stale_reason'])
