import unittest

from tools.validation.build_intrinsic_player_panel import panel


class IntrinsicPlayerPanelTests(unittest.TestCase):
    def fixtures(self):
        source = {'as_of': '2026-09-09', 'cohort': [{'player_id': '1', 'position': 'QB',
            'age': 25, 'season_summaries': [{'season': 2025, 'games': 7, 'ppg': 20, 'usage': None}]}]}
        market = {'retrieved_at': '2026-09-09T00:00:00Z', 'players': [
            {'player_id': str(i), 'name': 'Anonymous', 'position': 'QB', 'age': 25,
             'value': 5000, 'market_rank': i, 'market_tier': 2} for i in (1, 2)]}
        return source, market

    def test_missing_player_evidence_does_not_inherit_quality_or_rank(self):
        rows, count, _ = panel(*self.fixtures())
        by_id = {r['player_id']: r for r in rows}
        self.assertEqual(count, 1)
        self.assertIsNone(by_id['2']['intrinsic'])
        self.assertNotIn('intrinsic_rank', by_id['2'])
        self.assertGreater(by_id['2']['market_normalized'], 0)

    def test_identity_position_conflict_fails_closed(self):
        source, market = self.fixtures()
        market['players'][0]['position'] = 'WR'
        with self.assertRaises(ValueError):
            panel(source, market)

    def test_price_does_not_change_intrinsic_or_tier(self):
        source, market = self.fixtures()
        first = panel(source, market)[0][0]
        market['players'][0]['value'] = 1
        second = panel(source, market)[0][0]
        self.assertEqual(first['intrinsic'], second['intrinsic'])
        self.assertEqual(first['intrinsic_tier'], second['intrinsic_tier'])
        self.assertNotEqual(first['market_normalized'], second['market_normalized'])
