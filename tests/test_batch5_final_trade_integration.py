"""Active auxiliary endpoints must retain the completed workflow semantics."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from services.trade_intelligence import compare_trade_requests, create_trade_alternatives, build_trade_workspace
from src.core.trade_intelligence.models import TradeProposal
from tests.test_trade_intelligence import fixture_data


class FinalTradeIntegrationTests(unittest.TestCase):
    def test_alternative_passes_reuse_exact_assessment_only_within_request(self):
        data = fixture_data()
        w = build_trade_workspace(data, 1)
        assets = {a.asset_id: a for pool in w['pools'].values() for a in pool}
        proposal = TradeProposal(1, 2, (assets['1-QB-1'],), (assets['2-QB-0'],), 'Fixture')
        p = {'active_roster_id': 1, 'partner_roster_id': 2,
             'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        def result(*args, **kwargs):
            return {'proposal': deepcopy(args[1]), 'evaluation': {'generated_trade_eligible': False}}
        with patch('services.trade_intelligence._bounded_adjustment_candidates', return_value=(proposal,)), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=result) as evaluate:
            create_trade_alternatives(data, p)
            self.assertEqual(evaluate.call_count, 1)
            create_trade_alternatives(data, p)
            self.assertEqual(evaluate.call_count, 2)

    def test_partial_market_comparison_does_not_invent_preference_or_crash(self):
        data = fixture_data()
        before = deepcopy(data)
        calls = []
        def evaluate(source, proposal, **kwargs):
            calls.append(kwargs['projection_reader'])
            return {'proposal': deepcopy(proposal), 'evaluation': {
                'generated_trade_eligible': False, 'recommendation': None,
                'values': {'ratio': None}, 'dimensions': {},
                'provenance': {'evaluation_id': str(len(calls))}}}
        p = {'active_roster_id': 1, 'partner_roster_id': 2,
             'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=evaluate):
            result = compare_trade_requests(data, [p, dict(p, assets_sent=['1-QB-1'])])
        self.assertIsNone(result['preferred_evaluation_id'])
        self.assertEqual(result['preference_availability'], 'unavailable')
        self.assertEqual(len(result['comparisons']), 2)
        self.assertIs(calls[0], calls[1])
        self.assertEqual(data, before)

    def test_alternative_search_rejects_generation_change(self):
        data = fixture_data()
        def changed(*args, **kwargs):
            data['teams'][0]['players'].pop()
            return ()
        with patch('services.trade_intelligence._bounded_adjustment_candidates', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Canonical evidence changed'):
                create_trade_alternatives(data, {'active_roster_id': 1, 'partner_roster_id': 2,
                    'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']})
