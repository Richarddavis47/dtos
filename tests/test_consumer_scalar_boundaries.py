"""Consumer boundaries cannot manufacture an unavailable intrinsic scalar."""
import unittest

from src.core.valuation.universe import ValuationUniverse
from src.core.valuation_intelligence.engine import _score_asset
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.valuation.player_methodology import REFERENCE_SCORING
from tests.test_valuation_universe import fixture


class ConsumerScalarBoundaryTests(unittest.TestCase):
    def test_agreement_requires_comparison_and_preserves_real_zero(self):
        asset = {'asset_id': 'player:1', 'asset_type': 'player', 'layers': {}}
        for values, expected in (([], None), ([10], None), ([0, 1000], 0), ([0, 0], 100)):
            rows = [{'normalized_value': value, 'provider_id': str(i)} for i, value in enumerate(values)]
            comparison = {'compatible_evidence_family_count': 2, 'dispersion': 500 if values == [0, 1000] else 0} if len(values) == 2 else None
            report = _score_asset(asset, rows, {}, comparison)
            self.assertEqual(report['scores']['agreement'], expected)
            self.assertIsNone(_score_asset(asset, rows, {}, None)['scores']['agreement'])

    def test_no_comparable_intrinsic_evidence_is_not_perfect_calibration(self):
        from src.core.valuation.automation import audit_market_calibration
        data = {'league': {'league_id': 'a'}, 'teams': [], 'normalized_players': {
            '1': {'player_id': '1', 'full_name': 'Fixture Player', 'position': 'QB', 'age': 25}}}
        report = audit_market_calibration(data, {}, apply=False)
        self.assertEqual(report['summary']['comparable_assets'], 0)
        self.assertIsNone(report['summary']['overall_calibration_score'])

    def test_cached_scores_market_and_metadata_do_not_fill_intrinsic_or_production(self):
        data, state = fixture()
        data['normalized_players']['1'].update(dtos_value=999, dynasty_value=777, fantasy_points=456)
        row = ValuationUniverse(data, state).by_id['player:1']
        for field in ('intrinsic_dtos_value', 'league_adjusted_value', 'contender_value',
                      'rebuilder_value', 'future_value', 'current_production_value', 'liquidity_score'):
            self.assertIsNone(row['layers'][field]['value'], field)
        self.assertEqual(row['layers']['market_value']['value'], 750)  # FC alone; no incompatible averaging.
        data['market_data']['providers'].pop('DynastyProcess')
        self.assertEqual(ValuationUniverse(data, state).by_id['player:1']['layers']['market_value']['value'],
                         row['layers']['market_value']['value'])
        self.assertIsNone(row['comparison']['difference_percent'])

    def test_checkpoint_keeps_adjusted_and_intrinsic_independent_including_zero(self):
        for adjusted in (None, 0, 500):
            data = {'valuation_intelligence': {'assets': {'player:1': {'layers': {
                'league_adjusted_value': {'value': adjusted},
                'intrinsic_dtos_value': {'value': 800}, 'market_value': {'value': 700},
            }}}}}
            row = CheckpointPipeline._values(data, '1')
            self.assertEqual(row['dtos_value'], adjusted)
            self.assertEqual(row['intrinsic_value'], 800)
            self.assertEqual(row['market_value'], 700)

    def test_brain_preserves_separate_reference_quality_profile_without_price(self):
        data, state = fixture()
        data['league'] = {'league_id': 'league-a'}
        data['canonical_player_production'] = {
            'league_id': 'league-a', 'season': 2026, 'generation': 'p1',
            'reference_scoring': REFERENCE_SCORING,
            'players': {'1': {'reference_seasons': [
                {'season': 2025, 'games': 7, 'ppg': 22},
            ]}},
        }
        row = ValuationUniverse(data, state).by_id['player:1']
        profile = row['intrinsic_evidence_profile']
        self.assertIsNotNone(profile['demonstrated_quality'])
        self.assertIsNone(profile['intrinsic_value'])
        self.assertIsNone(profile['intrinsic_tier'])
        self.assertEqual(profile['generation'], 'p1')
        self.assertEqual(_score_asset(row, [], {}, None)['intrinsic_evidence_profile'], profile)


if __name__ == '__main__':
    unittest.main()
