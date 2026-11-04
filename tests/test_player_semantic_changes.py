import copy
import json
import unittest

from src.core.valuation_intelligence.changes import compare, snapshot, METHODOLOGY_ID


class PlayerSemanticChangeTests(unittest.TestCase):
    def test_active_timeline_replay_is_bounded_and_legacy_transition_once(self):
        from src.core.valuation_intelligence.engine import build_valuation_intelligence
        data = {'league': {'league_id': 'league-a'}, 'normalized_players': {
            '1': {'name': 'Fixture', 'position': 'QB', 'status': 'Active', 'age': 25}},
            'market_data': {'providers': {}},
            'valuation_intelligence_timeline': {'player:1': [{'timestamp': 'old', 'confidence': 1}]}}
        first = build_valuation_intelligence(data, {})
        self.assertEqual(first['timeline']['player:1'][-1]['reason_codes'], ('METHODOLOGY_VERSION_CHANGED',))
        prior = copy.deepcopy(data['valuation_intelligence_timeline'])
        build_valuation_intelligence(data, {})
        self.assertEqual(data['valuation_intelligence_timeline'], prior)
        for i in range(55):
            data['normalized_players']['1']['status'] = 'Active' if i % 2 else 'Inactive'
            build_valuation_intelligence(data, {})
        history = data['valuation_intelligence_timeline']['player:1']
        self.assertEqual(len(history), 50)
        self.assertIn('STATUS_CHANGED', history[-1]['reason_codes'])
        self.assertEqual(sum('semantic_snapshot' in row for row in history), 1)

    def baseline(self):
        return snapshot({'asset_id': 'player:1', 'scores': {'confidence': 80},
            'intrinsic_evidence_profile': {'demonstrated_quality': 70, 'latest_observed_usage': 50},
            'ranks': {'global_market': {'overall': {'rank': 2, 'scope': 'global',
                'value_basis': 'market_value', 'position': None, 'universe_size': 10, 'ranked_count': 10}}}},
            {'status': 'Active', 'nfl_team': 'BUF'}, 'league-a', ({'provider': 'FantasyCalc', 'raw_value': 5000},))

    def test_method_transition_is_not_mass_player_movement(self):
        before, after = self.baseline(), self.baseline()
        before['methodology_id'] = 'pre-batch3'
        after.update(production_quality=90, confidence=99, market_prices={'FantasyCalc': 9999})
        self.assertEqual(compare(before, after), ('METHODOLOGY_VERSION_CHANGED',))

    def test_peer_rank_movement_is_not_own_evidence_change(self):
        before, after = self.baseline(), self.baseline()
        after['ranks']['global_market']['overall']['rank'] = 3
        self.assertEqual(compare(before, after), ('RANK_CHANGED_PEER_MOVEMENT',))
        after['market_prices']['FantasyCalc'] = 5100
        self.assertEqual(set(compare(before, after)), {'MARKET_PRICE_UP', 'RANK_CHANGED'})

    def test_missing_zero_boundaries_and_replay(self):
        before = self.baseline()
        self.assertEqual(compare(before, copy.deepcopy(before)), ())
        self.assertEqual(compare(json.loads(json.dumps(before)), before), ())
        after = {**before, 'projection': 0}
        self.assertEqual(compare(before, after), ('PROJECTION_AVAILABILITY_CHANGED',))
        self.assertEqual(compare(before, {**before, 'league_id': 'league-b'}), ('CONTEXT_BOUNDARY_CHANGED',))
        self.assertEqual(before['methodology_id'], METHODOLOGY_ID)

    def test_production_usage_status_confidence_have_codes(self):
        before = self.baseline()
        after = {**before, 'production_quality': 75, 'production_sample': [[2025], 18],
            'usage': 55, 'confidence': 90, 'status': 'Inactive', 'role': ['GB', 2]}
        self.assertEqual(set(compare(before, after)), {'PRODUCTION_QUALITY_UP',
            'PRODUCTION_SAMPLE_UPDATED', 'USAGE_UP', 'CONFIDENCE_UP', 'STATUS_CHANGED', 'ROLE_CHANGED'})
