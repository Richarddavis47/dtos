from copy import deepcopy
import unittest

from services.asset_explanations import (
    player_projection_explanation, market_explanation, pick_explanation, pick_history_explanation,
)
from src.ui.explanations import explanation_panel


class AssetExplanationTests(unittest.TestCase):
    def test_projection_zero_missing_and_week_are_exact(self):
        for value, display in ((27.335, '27.33'), (0, '0.00'), (None, 'Unavailable')):
            source = dict(player_id='p', league_id='A', season=2026, week=3, generation='g',
                          value=value, display=display, confidence=None)
            view = player_projection_explanation(source)
            self.assertEqual(view.evidence[0].display, display if value is not None else None)
            self.assertIn('Week 3', explanation_panel(view))
            self.assertNotIn('27.34', explanation_panel(view))

    def test_incompatible_history_cannot_claim_movement(self):
        detail = {'asset': {'asset_id': 'player:p', 'values': {'market_value': None}, 'rank': 4},
                  'market_generation': 'g', 'providers': ['FantasyCalc']}
        trend = {'direction': 'rising', 'comparison_reasons': ['METHODOLOGY_VERSION_CHANGED']}
        view = market_explanation(detail, trend, league_id='A')
        html = explanation_panel(view)
        self.assertIn('No comparable evidence', html)
        self.assertNotIn('rising', html)
        self.assertNotIn('#4', html)
        self.assertIsNone(view.evidence[0].display)
        self.assertIn('DTOS methodology changed', html)
        self.assertIn('not a player price surge or decline', html)

    def test_coverage_and_method_boundary_reasons_remain_distinct(self):
        detail = {'asset': {'asset_id': 'player:p', 'values': {'market_value': 400}}}
        html = explanation_panel(market_explanation(detail, {'direction': 'not_comparable',
            'comparison_reasons': ['COMPARABLE_HISTORY_UNAVAILABLE', 'INCOMPATIBLE_OBSERVATION_BOUNDARY']}, league_id='A'))
        self.assertIn('missing coverage is not stable performance', html)
        self.assertIn('no numeric movement is claimed', html)
        self.assertNotIn('DTOS methodology changed', html)

    def test_known_movement_does_not_invent_cause(self):
        detail = {'asset': {'asset_id': 'player:p', 'values': {'market_value': 400}}}
        html = explanation_panel(market_explanation(detail, {'direction': 'falling'}, league_id='A'))
        self.assertIn('falling', html)
        self.assertIn('does not by itself establish why', html)
        self.assertNotIn('injury', html)

    def test_pick_origin_owner_price_range_and_history_remain_distinct(self):
        pick = dict(league_id='A', year=2027, round=1, original_roster_id=1, current_owner_id=4,
                    projected_range='UNKNOWN', projected_range_confidence='LOW', exact_slot='1.03')
        market = {'normalized_market_price': None, 'quote': None}
        original = deepcopy(pick)
        view = pick_explanation(pick, market, league_id='A')
        html = explanation_panel(view)
        self.assertNotIn('1.03', html)
        self.assertIn('UNKNOWN', html)
        self.assertIn('not whether the pick is good or bad', html)
        for _ in range(100):
            self.assertEqual(explanation_panel(pick_explanation(pick, market, league_id='A')), html)
        self.assertEqual(pick, original)
        with self.assertRaises(ValueError):
            pick_explanation(pick, market, league_id='B')
        history = pick_history_explanation(dict(pick_id='p', owner_chain=['A', 'B', 'A'],
            ownership_chain_gaps=['missing-transfer']), league_id='A')
        self.assertIn('A → B → A', explanation_panel(history))
        self.assertIn('missing transfer links', explanation_panel(history))


if __name__ == '__main__':
    unittest.main()
