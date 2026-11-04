"""Missing-price decision presentation over canonical producers and auth HTTP."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from services.trade_decision import decision_context
from services.trade_search_policy import classify
from tests import test_trade_endorsement_integrity as integrity


class MissingMarketPresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = integrity.EndorsementIntegrityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.configure(sent=500, received=400, delta=5)
        self.data = self.fixture.data

    def remove_prices(self, *ids):
        quotes = self.data['market_data']['providers']['FantasyCalc']
        for pid in ids:
            quotes.pop(pid, None)

    def evaluate(self):
        return self.fixture.evaluate(strategy='REBUILD')

    def assert_conditional(self, e):
        self.assertEqual(e['recommendation'], 'WORTH PURSUING')
        self.assertFalse(e['generated_trade_eligible'])
        self.assertEqual(classify(e), 'MISSING REQUIRED EVIDENCE')
        self.assertEqual(e['assessment_state']['state'], 'fresh_incomplete')
        self.assertEqual(e['decision_context']['strategy']['resolved'], 'REBUILD')
        self.assertEqual(e['decision_context']['lineup']['delta'], 5)
        self.assertIn('not an endorsement', e['decision_context'].get('qualification') or '')
        self.assertIn('Market cost cannot be fully assessed', e['decision_context']['main_cost'])
        self.assertIn('Market', e['decision_context']['blocker'] or '')
        self.assertNotIn('No material downside identified', e['explanation_html'])
        self.assertIn('tw-verdict-qualification', e['explanation_html'])

    def test_missing_sent_received_and_both_prices_keep_numeric_evidence_and_guard(self):
        for missing in (('1q',), ('2w',), ('1q', '2w')):
            with self.subTest(missing=missing):
                self.fixture.configure(sent=500, received=400, delta=5)
                self.remove_prices(*missing)
                e = self.evaluate()
                self.assertEqual(e['market_evidence']['availability'],
                                 'unavailable' if len(missing) == 2 else 'partial')
                self.assertEqual(e['values']['sent'] is None, '1q' in missing)
                self.assertEqual(e['values']['received'] is None, '2w' in missing)
                self.assert_conditional(e)

    def test_fully_priced_benefit_zero_and_severe_loss_preserve_normal_presentation(self):
        for sent, received, delta, label in ((500, 400, 5, 'WORTH PURSUING'),
                                           (0, 0, 5, 'SMASH ACCEPT'),
                                           (995, 75, .01, 'REJECT')):
            with self.subTest(sent=sent, received=received):
                self.fixture.configure(sent=sent, received=received, delta=delta)
                e = self.evaluate()
                self.assertEqual(e['market_evidence']['availability'], 'full')
                self.assertEqual(e['recommendation'], label)
                self.assertFalse(e['decision_context'].get('qualification'))
                self.assertNotIn('tw-verdict-qualification', e['explanation_html'])
                self.assertEqual(e['generated_trade_eligible'], label != 'REJECT')

    def test_missing_projection_does_not_invent_a_benefit(self):
        from src.core.projection_intelligence.service import ProjectionService
        self.remove_prices('1q')
        self.fixture.publisher.reader = ProjectionService(
            Path(self.fixture.publisher.tmp.name) / 'unpublished.sqlite3')
        e = self.evaluate()
        self.assertIsNone(e['recommendation'])
        self.assertFalse(e['generated_trade_eligible'])
        self.assertIsNone(e['decision_context']['lineup']['delta'])
        self.assertIn('cannot be verified', e['decision_context']['lineup']['explanation'])
        self.assertNotIn('lineup gain:', e['explanation_html'])
        self.assertIn('Market cost cannot be fully assessed', e['decision_context']['main_cost'])

    def test_presentation_does_not_mutate_analytical_result_or_source(self):
        self.remove_prices('1q')
        e = self.evaluate()
        before = copy.deepcopy(e)
        data = copy.deepcopy(self.data)
        snapshot = self.fixture.publisher.reader.snapshot()
        decision_context(e)
        self.assertEqual(e, before)
        self.assertEqual(self.data, data)
        self.assertEqual(self.fixture.publisher.reader.snapshot(), snapshot)
        # Raw retained analytical evidence remains available, not rewritten.
        self.assertIn('No material downside identified', e['major_drawback'])
        self.assert_conditional(e)

    def test_existing_renderer_without_decision_dto_uses_same_qualification(self):
        from services.trade_explanation import render_trade_explanation
        self.remove_prices('1q')
        e = self.evaluate()
        e.pop('decision_context')
        before = copy.deepcopy(e)
        html = render_trade_explanation(e, league_id='league-1')
        self.assertIn('not an endorsement', html)
        self.assertIn('Market cost cannot be fully assessed', html)
        self.assertNotIn('No material downside identified', html)
        self.assertNotIn('<details class="tw-evaluation-detail">', html)
        self.assertEqual(e, before)

    def test_missing_price_preserves_independently_supported_reserve_cost(self):
        self.fixture.configure(sent=500, received=400, delta=5, spare_qb=False)
        self.remove_prices('1q')
        e = self.evaluate()
        self.assertIn('Reserve coverage declines', e['major_drawback'])
        self.assertIn('Reserve coverage declines', e['decision_context']['main_cost'])
        self.assertIn('Market cost cannot be fully assessed', e['decision_context']['main_cost'])
        self.assertEqual(e['decision_context']['lineup']['delta'], 5)
        self.assertFalse(e['generated_trade_eligible'])

    def test_authenticated_builder_adjust_and_discovery_keep_missing_evidence_guard(self):
        self.remove_prices('1q', '2w')
        harness = self.browser_fixture()
        client = harness.auth.client
        context = client.get('/api/trades/workspace').json()['workspace_context']
        headers = {'X-CSRF-Token': harness.auth.csrf}
        payload = {**self.fixture.payload, 'workspace_context': context}
        response = client.post('/api/trades/evaluate', json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assert_conditional(response.json()['evaluation'])
        for workflow, target in (('trade_for', '2w'), ('shop', '1q'), ('recommended', None)):
            with self.subTest(workflow=workflow):
                response = client.post('/api/trades/generate', json={
                    'workflow': workflow, 'active_roster_id': 1, 'asset_id': target,
                    'strategy': 'REBUILD', 'workspace_context': context}, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                if target:
                    self.assertEqual(body['result_state'], 'MISSING REQUIRED EVIDENCE')
                    self.assertEqual(body['results'], [])
                for row in body['results']:
                    self.assertEqual(row['evaluation']['market_evidence']['availability'], 'full')
                    self.assertFalse(row['evaluation']['decision_context'].get('qualification'))
        response = client.post('/api/trades/assist',
            json={**payload, 'instruction': 'make it cheaper'}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['result_state'], 'MISSING REQUIRED EVIDENCE')
        self.assertEqual(response.json()['results'], [])

    def browser_fixture(self):
        from tests import test_trade_decision_http_browser as browser
        harness = browser.DecisionHTTPBrowserTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        harness.data, harness.f = self.data, self.fixture.publisher
        self.enterContext(patch('services.trade_intelligence._trade_projection_service',
                                return_value=self.fixture.publisher.reader))
        self.enterContext(patch('src.core.projection_intelligence.projection_service',
                                self.fixture.publisher.reader))
        return harness

    def test_authenticated_http_and_phone_primary_qualification(self):
        self.remove_prices('1q')
        harness = self.browser_fixture()
        rows = []
        for width, height in ((320, 432), (375, 667), (390, 844)):
            with self.subTest(width=width), harness.browser(width, height) as page:
                harness.ready(page)
                page.select_option('#trade-partner', '2')
                page.select_option('#trade-strategy', 'REBUILD')
                harness.select(page, 'sent', '1q')
                harness.select(page, 'received', '2w')
                page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                page.locator('.dtos-explanation').wait_for()
                e = harness.responses[-1]['evaluation']
                primary = page.locator('.dtos-explanation > p').first
                qualifier = page.locator('.tw-verdict-qualification').first
                rect = qualifier.bounding_box() if qualifier.count() else None
                row = {'width': width, 'height': height, 'heading': primary.inner_text(),
                    'qualification': rect, 'scroll_y': page.evaluate('scrollY'),
                    'document_width': page.evaluate('document.documentElement.scrollWidth'),
                    'primary_drawback': page.locator('.tw-decision > .tw-drawback').all_text_contents(),
                    'no_downside_claim': 'No material downside identified' in page.locator('.dtos-explanation').text_content(),
                    'recommendation': e['recommendation'], 'eligible': e['generated_trade_eligible'],
                    'lineup_delta': e['decision_context']['lineup']['delta']}
                rows.append(row)
                target = os.environ.get('DTOS_MISSING_MARKET_EVIDENCE')
                if target:
                    Path(target).write_text(json.dumps(rows, indent=2))
                self.assert_conditional(e)
                self.assertNotIn('WORTH PURSUING', primary.inner_text())
                self.assertIn('Recommendation unavailable', primary.inner_text())
                self.assertIn('WORTH PURSUING', page.locator('.tw-side-assessment').inner_text())
                self.assertIsNotNone(rect)
                self.assertGreaterEqual(rect['y'], 0)
                self.assertLessEqual(rect['y'] + rect['height'], height)
                self.assertLessEqual(row['document_width'], width)
                self.assertFalse(row['no_downside_claim'])
                page.locator('.tw-evaluation-detail > summary').focus()
                page.locator('.tw-evaluation-detail > summary').press('Enter')
                self.assertIn('Market cost cannot be fully assessed', page.locator('.tw-evaluation-detail').inner_text())

    def test_released_client_fallback_and_older_saved_context_stay_qualified(self):
        self.remove_prices('1q')
        harness = self.browser_fixture()
        with patch('services.trade_explanation.render_trade_explanation', return_value=''), harness.browser() as page:
            harness.ready(page)
            page.select_option('#trade-partner', '2')
            page.select_option('#trade-strategy', 'REBUILD')
            harness.select(page, 'sent', '1q')
            harness.select(page, 'received', '2w')
            page.get_by_role('button', name='Evaluate Trade', exact=True).click()
            page.locator('#trade-result .tw-verdict-qualification').wait_for()
            current = harness.responses[-1]['evaluation']
            self.assertFalse(current['generated_trade_eligible'])
            self.assertEqual(classify(current), 'MISSING REQUIRED EVIDENCE')
            self.assertIn('not an endorsement', page.locator('#trade-result').inner_text())
            self.assertIn('Market cost cannot be fully assessed', page.locator('#trade-result').inner_text())
            # Simulate the already-bounded v1.21.64 saved fields, not a new copy.
            page.evaluate('''() => {
              const key=Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'));
              const saved=JSON.parse(sessionStorage.getItem(key));
              const e=saved.currentAssessment.evaluation;
              delete e.decision_context.qualification;
              e.decision_context.main_cost=e.major_drawback+' Earlier supported age trade-off remains a cost.';
              e.decision_context.blocker=null;
              sessionStorage.setItem(key,JSON.stringify(saved));
              // Reload deliberately prefers the matching history-entry draft.
              history.replaceState({...history.state,dtosTrade:{...history.state.dtosTrade,draft:saved}},'');
            }''')
            posts = len(harness.requests)
            page.reload()
            page.locator('#trade-result .tw-verdict-qualification').wait_for()
            text = page.locator('#trade-result').inner_text()
            self.assertIn('not an endorsement', text)
            self.assertIn('Market cost cannot be fully assessed', text)
            self.assertIn('Earlier supported age trade-off remains a cost.', text)
            self.assertNotIn('No material downside identified', text)
            self.assertEqual(len(harness.requests), posts)


if __name__ == '__main__':
    unittest.main()
