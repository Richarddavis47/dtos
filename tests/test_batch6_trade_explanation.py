import copy
from time import perf_counter
import unittest
from unittest.mock import patch

from services.trade_explanation import trade_explanation, render_trade_explanation
from services.trade_intelligence import evaluate_trade_request
from src.ui.explanations import explanation_panel
from src.core.trade_intelligence.bilateral import evaluate_bilateral
from src.core.trade_intelligence.models import TradeProposal
from tests.test_batch5_trade_strategy import asset, side
from tests.test_trade_intelligence import fixture_data


class ActiveTradeExplanationTests(unittest.TestCase):
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
        proposal = TradeProposal(1, 2, (asset('a', None, 1),), (asset('b', 200, 2),), 'Manual')
        active = side(1, 5)
        active['horizons']['playoff_window']['delta'] = -9
        result = evaluate_bilateral(proposal, active_team={}, partner_team={}, league={'league_id': 'A'},
            horizon_impact={'sides': {'active': active, 'partner': side(2, 3)}})
        result['provenance'].update(evaluation_id='completed-fixture', inputs={
            'league_id': 'A', 'active_roster_id': 1, 'partner_roster_id': 2})
        before = copy.deepcopy(result)
        start = perf_counter()
        rendered = explanation_panel(trade_explanation(result, league_id='A'))
        for _ in range(100):
            self.assertEqual(explanation_panel(trade_explanation(result, league_id='A')), rendered)
        print({'scope': 'completed bilateral fixture; 101 explanation renders, no storage', 'seconds': perf_counter() - start})
        self.assertEqual(result, before)
        self.assertIn('Current week optimal-lineup change: <strong>5', rendered)
        self.assertIn('Playoff window optimal-lineup change: <strong>-9', rendered)
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
        proposal = TradeProposal(1, 2, (asset('a', None, 1),), (asset('b', 200, 2),), 'Manual')
        active = side(1, 5)
        active['horizons']['playoff_window']['delta'] = -9
        active['horizons']['rest_of_regular_season'].update(delta=None, availability='partial_or_unavailable',
                                                          supported_week_delta_subtotal=5)
        active['weekly'][2]['pre']['optimal']['projected_points'] = 27.335
        active['weekly'][2]['post']['optimal']['projected_points'] = 32.335
        active['weekly'][3] = copy.deepcopy(active['weekly'][2])
        active['weekly'][3]['pre']['optimal']['projected_points'] = 0.0
        active['weekly'][3]['post']['optimal']['projected_points'] = None
        active['weekly'][3]['delta'] = None
        result = evaluate_bilateral(proposal, active_team={}, partner_team={}, league={'league_id': 'A'},
            horizon_impact={'sides': {'active': active, 'partner': side(2, 3)}})
        result['provenance'].update(evaluation_id='completed', inputs={'league_id': 'A'})
        original = copy.deepcopy(result)
        html = render_trade_explanation(result, league_id='A')
        before_detail = html.split('<details>')[0]
        self.assertIn('Current week: 5', before_detail)
        self.assertIn('Playoff window: -9', before_detail)
        self.assertIn('Rest of regular season: Unavailable', before_detail)
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
