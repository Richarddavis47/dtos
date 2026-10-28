import copy
from time import perf_counter
import unittest
from unittest.mock import patch

from services.trade_explanation import trade_explanation, render_trade_explanation
from services.trade_intelligence import evaluate_trade_request
from src.ui.explanations import explanation_panel
from src.core.trade_intelligence.bilateral import evaluate_bilateral
from tests.test_trade_intelligence import fixture_data


class ActiveTradeExplanationTests(unittest.TestCase):
    def completed_result(self, *, missing_week=False):
        from tests.test_capital_strategy_reconciliation import CapitalStrategyTests
        from src.core.intelligence.team_strength import prepare_for_data
        fixture = CapitalStrategyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.points.update(a=27.335, c=32.335, b=0, e=0)
        fixture.publish()
        for week in (4, 5):
            for row in fixture.payloads[week]:
                if row['player_id'] in ('a', 'c'):
                    row['stats'] = {'pass_yd': 20 if row['player_id'] == 'a' else 15.5}
        fixture.reader.publish_horizon(fixture.payloads, data=fixture.data, league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(fixture.reader, fixture.data)
        fixture.data['market_data']['providers']['FantasyCalc'].pop('a')
        result = fixture.evaluate(['a'], ['c'], intent='RETOOL')
        if missing_week:
            # Model loss of a prepared post-trade result, not an upstream zero.
            # Keep the verified pre-trade zero and independent weeks intact.
            rows = result['multi_horizon_impact']['sides']['active']['weekly']
            rows[3]['pre']['optimal']['projected_points'] = 0.0
            rows[3]['post']['optimal']['projected_points'] = None
            rows[3]['delta'] = None
            for name in ('next_n', 'rest_of_regular_season'):
                row = result['dimensions']['strategic_fit']['active']['horizons'][name]
                valid = [week for week in row['weeks_requested'] if rows[week]['delta'] is not None]
                row.update(delta=None, post_total=None, availability='partial_or_unavailable',
                    post_supported_weeks=valid, comparable_weeks=valid,
                    supported_week_delta_subtotal=sum(rows[week]['delta'] for week in valid))
        return result

    def test_actual_service_output_includes_shared_render_without_second_evaluation(self):
        data = fixture_data()
        with patch('services.trade_intelligence.evaluate_bilateral', wraps=evaluate_bilateral) as evaluator:
            result = evaluate_trade_request(data, {'active_roster_id': 1, 'partner_roster_id': 2,
                'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']})
        self.assertEqual(evaluator.call_count, 1)
        evaluation = result['evaluation']
        self.assertIn('dtos-explanation', evaluation['explanation_html'])
        self.assertIn(evaluation.get('recommendation') or 'Recommendation unavailable', evaluation['explanation_html'])

    def test_actual_evaluator_partial_market_mixed_horizons_and_determinism(self):
        result = self.completed_result()
        before = copy.deepcopy(result)
        start = perf_counter()
        rendered = explanation_panel(trade_explanation(result, league_id='league-1'))
        for _ in range(100):
            self.assertEqual(explanation_panel(trade_explanation(result, league_id='league-1')), rendered)
        print({'scope': 'completed bilateral fixture; 101 explanation renders, no storage', 'seconds': perf_counter() - start})
        self.assertEqual(result, before)
        self.assertEqual(next(item.display for item in trade_explanation(result, league_id='league-1').evidence if item.key == 'active.current_week'), '5')
        self.assertEqual(next(item.display for item in trade_explanation(result, league_id='league-1').evidence if item.key == 'active.playoff_window'), '-9')
        self.assertIn('Some assets lack supported acquisition prices', rendered)
        self.assertIn('not acceptance probability', rendered)
        self.assertNotIn('will accept', rendered.lower())
        with self.assertRaises(ValueError):
            trade_explanation(result, league_id='B')

    def test_unknown_reason_not_invented_and_text_escaped(self):
        result = {'provenance': {'evaluation_id': 'g', 'evaluator': 'm', 'inputs': {'league_id': 'A'}},
                  'recommendation': '<script>no</script>', 'major_risks': ['UNKNOWN_REASON'],
                  'recommendation_trace': {'rule_reasons': ['UNKNOWN_REASON']}}
        rendered = explanation_panel(trade_explanation(result, league_id='A'))
        self.assertNotIn('UNKNOWN_REASON', rendered)
        self.assertNotIn('<script>', rendered)

    def test_horizons_visible_weekly_detail_preserves_zero_missing_and_precision(self):
        result = self.completed_result(missing_week=True)
        # Exercise the shared legacy explanation layer; the compact actual
        # workspace and disclosures are covered through authenticated browsers.
        result.pop('decision_context')
        original = copy.deepcopy(result)
        html = render_trade_explanation(result, league_id='league-1')
        # Package disclosures can precede technical evidence. Assert that every
        # primary horizon is outside *all* closed disclosures, not a tag index.
        from html.parser import HTMLParser

        class PrimaryText(HTMLParser):
            def __init__(self):
                super().__init__()
                self.closed, self.text = [], []

            def handle_starttag(self, tag, attrs):
                if tag == 'details':
                    self.closed.append('open' not in dict(attrs))

            def handle_endtag(self, tag):
                if tag == 'details':
                    self.closed.pop()

            def handle_data(self, data):
                if not any(self.closed):
                    self.text.append(data)

        primary = PrimaryText()
        primary.feed(html)
        before_detail = ''.join(primary.text)
        self.assertIn('weeks 2: 5', before_detail)
        self.assertIn('weeks 4, 5: -9', before_detail)
        self.assertIn('Rest of regular season · Season 2026 · weeks 2, 3: Unavailable', before_detail)
        self.assertIn('not one combined upgrade/downgrade', before_detail)
        self.assertIn('Weekly optimal-lineup detail', html)
        self.assertIn('Before trade optimal total: <strong>27.335', html)
        self.assertIn('Week 3 · Before trade optimal total: <strong>0.0', html)
        self.assertIn('Week 3 · After trade optimal total: <strong>Unavailable', html)
        self.assertIn('Week 3 · Optimal-lineup change: <strong>Unavailable', html)
        self.assertIn('has incomplete week coverage', html)
        self.assertEqual(result, original)

    def test_declared_risks_visible_without_invented_codes_or_probabilities(self):
        result = {'provenance': {'evaluation_id': 'g', 'evaluator': 'm', 'inputs': {'league_id': 'A'}},
                  'recommendation': 'NOT WORTH IT',
                  'major_risks': ['PLAYOFF_WINDOW_DOWNGRADE', 'LOW_COUNTERPARTY_PLAUSIBILITY', 'UNKNOWN_REASON']}
        html = render_trade_explanation(result, league_id='A')
        primary = html.split('<details>')[0]
        self.assertIn('lose projected points', primary)
        self.assertIn('does not predict their response', primary)
        self.assertNotIn('UNKNOWN_REASON', html)

    def test_presentation_group_rejects_missing_or_duplicate_evidence(self):
        result = {'provenance': {'evaluation_id': 'g', 'evaluator': 'm', 'inputs': {'league_id': 'A'}}}
        view = trade_explanation(result, league_id='A')
        for groups in ((('Detail', ('missing',)),), (('One', ('confidence',)), ('Two', ('confidence',)))):
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                explanation_panel(view, evidence_groups=groups)


if __name__ == '__main__':
    unittest.main()
