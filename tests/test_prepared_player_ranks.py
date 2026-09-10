"""Prepared ranks compare players, never selected roster ownership or pick values."""
from copy import deepcopy
import unittest

from src.core.valuation_intelligence import build_valuation_intelligence
from src.core.valuation.ranking import prepare_global_player_ranks
from tests.test_provider_network import fixture


class PreparedPlayerRankTests(unittest.TestCase):
    def build(self, data):
        return build_valuation_intelligence(data, {"data": data})["assets"]

    def test_full_player_universe_includes_unrostered_and_excludes_picks(self):
        data, _ = fixture()
        ranks = self.build(data)["player:1"]["ranks"]
        for basis in ranks.values():
            self.assertEqual(basis["overall"]["universe_size"], 80)
            self.assertEqual(basis["position"]["universe_size"], 20)
        self.assertEqual(ranks["global_intrinsic"]["overall"]["scope"], "global")
        self.assertEqual(ranks["league_adjusted"]["overall"]["scope"], "league_adjusted")

    def test_ownership_and_roster_value_overrides_do_not_change_global_ranks(self):
        data, _ = fixture()
        before = self.build(deepcopy(data))
        data["teams"] = [{"roster_id": 99, "team_name": "Other franchise", "players": [
            {"id": "1", "position": "RB", "dtos_value": 999, "dynasty_value": 999}]}]
        data["league"]["league_id"] = "another-league"
        after = self.build(data)
        for key in before:
            if key.startswith("player:"):
                self.assertEqual(before[key]["ranks"]["global_intrinsic"], after[key]["ranks"]["global_intrinsic"])

    def test_format_adjustment_does_not_change_global_intrinsic_rank(self):
        data, _ = fixture()
        data["league"]["roster_positions"] = ["QB", "RB", "WR", "TE"]
        before = self.build(deepcopy(data))
        data["league"]["roster_positions"].append("SUPER_FLEX")
        after = self.build(data)
        self.assertEqual(before["player:4"]["ranks"]["global_intrinsic"], after["player:4"]["ranks"]["global_intrinsic"])
        self.assertIsNone(after["player:4"]["ranks"]["league_adjusted"]["overall"]["rank"])
        self.assertEqual(before["player:4"]["ranks"]["league_adjusted"], after["player:4"]["ranks"]["league_adjusted"])

    def test_missing_market_is_not_a_zero_rank(self):
        data, _ = fixture()
        data["market_data"]["providers"] = {}
        row = self.build(data)["player:1"]["ranks"]["global_market"]["overall"]
        self.assertIsNone(row["rank"])
        self.assertEqual(row["ranked_count"], 0)

    def test_league_relevance_filter_cannot_masquerade_as_global_rank(self):
        data, _ = fixture()
        data["relevant_player_universe"] = {"member_ids": ["1", "2"]}
        ranks = self.build(data)["player:1"]["ranks"]
        self.assertNotIn("global_intrinsic", ranks)
        self.assertNotIn("global_market", ranks)
        self.assertEqual(ranks["league_universe_intrinsic"]["overall"]["scope"], "league_universe")
        self.assertEqual(ranks["league_universe_intrinsic"]["overall"]["universe_size"], 2)

    def test_retired_player_legacy_value_does_not_make_an_active_dynasty_rank(self):
        data, _ = fixture()
        data["normalized_players"]["1"].update(status="Retired", dtos_value=1000)
        row = self.build(data)["player:1"]["ranks"]["global_intrinsic"]["overall"]
        self.assertIsNone(row["rank"])
        self.assertEqual(row["ranked_count"], 0)

    def test_prepared_global_rank_survives_league_filter(self):
        data, _ = fixture()
        data['market_data']['generation'] = 'market1'
        reference = prepare_global_player_ranks(data)
        expected = reference["players"]["player:1"]["global_intrinsic"]
        data["global_player_ranks"] = reference
        data["relevant_player_universe"] = {"member_ids": ["1", "2"]}
        ranks = self.build(data)["player:1"]["ranks"]
        self.assertEqual(ranks["global_intrinsic"], expected)
        self.assertEqual(ranks["global_intrinsic"]["overall"]["universe_size"], 80)
        self.assertEqual(ranks["league_universe_intrinsic"]["overall"]["universe_size"], 2)

    def test_stale_global_reference_cannot_join_new_market_generation(self):
        data, _ = fixture()
        data['market_data']['generation'] = 'market1'
        data['global_player_ranks'] = prepare_global_player_ranks(data)
        data['market_data']['generation'] = 'market2'
        data['relevant_player_universe'] = {'member_ids': ['1', '2']}
        ranks = self.build(data)['player:1']['ranks']
        self.assertNotIn('global_market', ranks)
        self.assertIn('league_universe_market', ranks)

    def test_global_preparation_rejects_filtered_source(self):
        data, _ = fixture()
        data["relevant_player_universe"] = {"member_ids": ["1"]}
        with self.assertRaises(ValueError):
            prepare_global_player_ranks(data)

    def test_global_preparation_retains_no_private_team_context(self):
        data, _ = fixture()
        before = prepare_global_player_ranks(data)
        data["league"]["league_id"] = "other-private-league"
        data["league"]["roster_positions"] = ["SUPER_FLEX"]
        data["teams"] = [{"roster_id": 99, "owner": "private-owner", "players": [{"id": "1", "dtos_value": 999}]}]
        after = prepare_global_player_ranks(data)
        self.assertEqual(before, after)
        self.assertNotIn("private-owner", str(after))

    def test_dossier_does_not_promote_roster_or_filtered_rank_to_global(self):
        from components.asset_intelligence import _scoped_rank_summary
        html = _scoped_rank_summary({"roster_dynasty": {"overall": {"rank": 1}},
            "league_universe_intrinsic": {"overall": {"rank": 1}}})
        self.assertIn("Global DTOS intrinsic dynasty:</b> Unavailable", html)
        self.assertNotIn("#1", html)
