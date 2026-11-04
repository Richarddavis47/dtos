import unittest
from src.core.asset_intelligence import AssetContext
from src.core.trade_intelligence.market.trade_market import _pick_asset


class PickYearIdentityTests(unittest.TestCase):
    def test_same_year_round_different_origin_and_traded_owner_remain_distinct(self):
        assets = [_pick_asset({'year': 2028, 'round': 1, 'original_roster_id': origin,
                              'current_owner_id': 3}, AssetContext('A', 3, {}), 3)
                  for origin in (1, 2)]
        self.assertNotEqual(assets[0].asset_id, assets[1].asset_id)
        self.assertEqual([a.original_roster_id for a in assets], [1, 2])
        self.assertEqual([a.current_owner_id for a in assets], [3, 3])

    def test_year_only_ledger_does_not_collapse_future_years(self):
        assets = [_pick_asset({'year': year, 'round': 1, 'original_roster_id': 1,
                              'current_owner_id': 2}, AssetContext('A', 2, {}), 2)
                  for year in (2027, 2028, 2029)]
        self.assertEqual([a.season for a in assets], [2027, 2028, 2029])
        self.assertEqual(len({a.asset_id for a in assets}), 3)
        self.assertTrue(all(a.original_roster_id == 1 and a.current_owner_id == 2 for a in assets))

    def test_missing_or_conflicting_year_fails_closed(self):
        for pick in ({'round': 1}, {'year': 2028, 'season': 2027, 'round': 1}):
            with self.assertRaises(ValueError):
                _pick_asset(pick, AssetContext('A', 2, {}), 2)
