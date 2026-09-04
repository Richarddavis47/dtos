"""Adversarial multi-league intelligence-isolation regressions for v1.13.0."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import unittest

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request
from src.core.front_office_intelligence import build_league_model
from src.core.intelligence.context import build_context
from src.core.trade_intelligence.evidence_context import build_trade_evidence_context
from tests.test_trade_intelligence import fixture_data


def _league_data(league_id: str) -> dict:
    data = fixture_data()
    data["league"]["league_id"] = league_id
    return data


def _behavior(league_id: str, position: str = "QB") -> dict:
    return {
        "league_id": league_id,
        "overall_confidence": "high",
        "transaction_count": 8,
        "evidence_completeness": 90,
        "semantic_identity": f"behavior:{league_id}",
        "dimensions": [
            {
                "key": "positional", "tendency": f"acquire_{position}",
                "confidence": "high", "evidence_references": [f"event:{league_id}"],
            },
        ],
    }


class MultiLeagueIntelligenceIsolationTests(unittest.TestCase):
    def test_trade_context_rejects_private_rows_and_preserves_global_trend(self) -> None:
        data = _league_data("league-b")
        workspace = build_trade_workspace(data, 1)
        asset_id = workspace["pools"][2][0].asset_id
        data["gm_behavioral_intelligence"] = {"2": _behavior("league-a")}
        data["front_office_evidence"] = {
            "2": {"league_id": "league-a", "partner_counts": {"1": 8}},
        }
        data["market_trend_summaries"] = {
            asset_id: {
                "direction": "rising", "confidence": "high",
                "league_liquidity": {
                    "league_id": "league-a", "recent_transaction_count": 9,
                    "confidence": "high",
                },
            },
        }

        context = build_trade_evidence_context(data, (workspace["pools"][2][0],))

        self.assertEqual(context.behavior_by_roster, {})
        self.assertEqual(context.front_office_by_roster, {})
        self.assertEqual(context.trends_by_asset[asset_id]["direction"], "rising")
        self.assertNotIn("league_liquidity", context.trends_by_asset[asset_id])
        self.assertEqual(context.wrong_league_evidence_rejected, 3)
        self.assertEqual(context.wrong_league_evidence_consumed, 0)

    def test_same_roster_id_cannot_import_rich_wrong_league_history(self) -> None:
        data = _league_data("league-b")
        data["front_office_evidence"] = {
            "1": {
                "league_id": "league-a", "transaction_count": 99,
                "partner_counts": {"2": 8},
            },
        }

        model = build_league_model(data)

        self.assertNotEqual(model.reports[1].activity.trades, 99)
        self.assertIsNone(model.reports[1].front_office_evidence)

    def test_wrong_league_rows_do_not_change_derived_cache_identity(self) -> None:
        data = _league_data("league-b")
        baseline = build_context(data, 1).snapshot_key
        data["front_office_evidence"] = {
            "1": {"league_id": "league-a", "semantic_identity": "private-a"},
        }
        data["gm_behavioral_intelligence"] = {
            "1": {"league_id": "league-a", "semantic_identity": "behavior-a"},
        }
        self.assertEqual(build_context(data, 1).snapshot_key, baseline)

    def test_direct_load_matches_switching_after_another_league(self) -> None:
        league_a = _league_data("league-a")
        league_b = _league_data("league-b")
        workspace = build_trade_workspace(league_b, 1)
        payload = {
            "workflow": "create", "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": [workspace["pools"][1][0].asset_id],
            "assets_received": [workspace["pools"][2][0].asset_id],
        }
        direct = evaluate_trade_request(copy.deepcopy(league_b), payload)
        build_league_model(league_a)
        switched = evaluate_trade_request(copy.deepcopy(league_b), payload)
        self.assertEqual(direct, switched)

    def test_concurrent_leagues_keep_private_evidence_isolated(self) -> None:
        def resolve(league_id: str, other_id: str) -> tuple[str, int, int]:
            data = _league_data(league_id)
            data["gm_behavioral_intelligence"] = {
                "2": _behavior(league_id), "1": _behavior(other_id),
            }
            context = build_trade_evidence_context(data)
            return context.league_id, len(context.behavior_by_roster), context.wrong_league_evidence_rejected

        with ThreadPoolExecutor(max_workers=3) as executor:
            rows = list(executor.map(lambda pair: resolve(*pair), (
                ("league-a", "league-b"), ("league-b", "league-c"),
                ("league-c", "league-a"),
            )))
        self.assertEqual(rows, [
            ("league-a", 1, 1), ("league-b", 1, 1), ("league-c", 1, 1),
        ])


if __name__ == "__main__":
    unittest.main()
