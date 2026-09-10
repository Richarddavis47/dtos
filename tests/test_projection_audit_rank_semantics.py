from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.projection_audit import _rank_maps


class ProjectionAuditRankSemanticsTests(unittest.TestCase):
    def test_historical_market_adapter_does_not_fill_other_value_dimensions(self):
        from src.core.historical_transaction_intelligence.service import _trade_asset
        from src.core.trade_intelligence.bilateral import evaluate_package_quality
        for value in (None, 0, 800):
            asset = _trade_asset(SimpleNamespace(asset_id='player:a', asset_type='player',
                position='QB', market_value=value, market_confidence=80), 1)
            self.assertEqual(asset.market_value, value)
            self.assertEqual(asset.trade_value, value)
            self.assertIsNone(asset.dynasty_value)
            self.assertIsNone(asset.redraft_value)
            self.assertIsNone(asset.team_fit_value)
            if value is None:
                self.assertEqual(evaluate_package_quality((asset,), ()).assessment, 'UNAVAILABLE')

    def test_crawl_does_not_enumerate_unavailable_team_grades_into_rank(self):
        from services.crawl import standings
        cards = {rid: SimpleNamespace(overall=SimpleNamespace(rank=None, grade='Unavailable'),
                  current_window=SimpleNamespace(value='Unavailable')) for rid in (1, 2)}
        data = {'teams': [{'roster_id': 2}, {'roster_id': 1}]}
        with patch('services.crawl._team_intelligence_cards', return_value=cards):
            result = standings(data)
        self.assertTrue(all(row['rank'] is None for row in result))
        self.assertTrue(all(row['ranking_type'] == 'Canonical Team Assessment' for row in result))

    def test_directory_positions_and_missing_prices_are_not_ranks(self):
        rows = [
            {"asset_id": "player:a", "position": "QB", "values": {"market_value": None}},
            {"asset_id": "player:b", "position": "QB", "values": {"market_value": 0}},
            {"asset_id": "player:c", "position": "QB", "values": {"market_value": 200}},
            {"asset_id": "pick:1", "values": {"market_value": 999}},
        ]
        result = _rank_maps(SimpleNamespace(assets=rows))
        self.assertEqual(result['overall_rank'], {'player:b': 2, 'player:c': 1})
        self.assertEqual(result['position_rank'], result['overall_rank'])
        self.assertEqual(result['contender_rank'], {})
        self.assertEqual(result['rebuilder_rank'], {})
        self.assertEqual(result, _rank_maps(SimpleNamespace(assets=list(reversed(rows)))))
