import copy
import unittest

from tools.validation.build_final_player_panel import build
from src.core.valuation.player_methodology import REFERENCE_SCORING


class FinalPlayerPanelTests(unittest.TestCase):
    def fixture(self):
        stamp = '2026-09-09T00:00:00+00:00'
        source = {'cohort': []}
        market = {'retrieved_at': stamp, 'players': [{'player_id': '1', 'name': 'Fixture',
            'position': 'QB', 'age': 23, 'value': 5000, 'market_rank': 1, 'market_tier': 1}]}
        forward = {'observed_at': stamp, 'season': 2026, 'week': 1, 'players': [{'evidence': {
            'player_id': '1', 'observed_at': stamp, 'expires_at': '2026-09-10T00:00:00+00:00',
            'generation': 'g1', 'team': 'BUF', 'status': 'Active', 'projection_player_id': '1',
            'projection_season': 2026, 'projection_week': 1, 'projection_reference': REFERENCE_SCORING,
            'projected_points': None, 'projection_row_present': True, 'projection_stats_present': False}}]}
        return source, market, forward

    def test_profile_is_not_filled_by_market_or_missing_weekly_evidence(self):
        source, market, forward = self.fixture()
        row = build(source, market, forward)[0]
        self.assertIsNone(row['profile']['intrinsic_value'])
        self.assertIsNone(row['profile']['demonstrated_quality']['score'])
        self.assertIsNone(row['profile']['near_term_expectation']['points'])
        self.assertIsNone(row['league_adjusted_rank'])
        self.assertEqual(row['market']['evidence_state'], 'SINGLE-PROVIDER MARKET')
        market['players'][0]['value'] = 100
        self.assertEqual(build(source, market, forward)[0]['profile'], row['profile'])

    def test_replay_and_real_zero_are_preserved(self):
        inputs = self.fixture()
        evidence = inputs[2]['players'][0]['evidence']
        evidence.update(projected_points=0, projection_stats_present=True)
        result = build(*inputs)
        self.assertEqual(result, build(*copy.deepcopy(inputs)))
        self.assertEqual(result[0]['profile']['near_term_expectation']['points'], 0)

    def test_identity_conflict_stops_panel(self):
        source, market, forward = self.fixture()
        source['cohort'] = [{'player_id': '1', 'position': 'WR'}]
        with self.assertRaises(ValueError):
            build(source, market, forward)
