"""Targeted tests for Transactions Center business logic."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from services.transactions import (
    filter_transactions,
    normalize_transactions,
    sort_transactions,
    transaction_center,
    transaction_summary,
)
from services.sleeper import STATE, sync_transactions


class TransactionsCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = {
            "teams": [
                {"roster_id": 1, "team_name": "Alpha", "owner": "Alice"},
                {"roster_id": 2, "team_name": "Bravo", "owner": "Bob"},
            ],
            "players": {
                "p1": {"full_name": "Quarter Back", "position": "QB", "team": "BUF"},
                "p2": {"full_name": "Wide Receiver", "position": "WR", "team": "MIA"},
                "p3": {"full_name": "Running Back", "position": "RB", "team": "NYJ"},
            },
            "transactions": [
                {
                    "transaction_id": "trade-1",
                    "type": "trade",
                    "status": "complete",
                    "created": 1_767_225_600_000,
                    "roster_ids": [1, 2],
                    "adds": {"p1": 2},
                    "drops": {"p1": 1},
                    "draft_picks": [
                        {
                            "season": "2027",
                            "round": 2,
                            "roster_id": 2,
                            "previous_owner_id": 2,
                            "owner_id": 1,
                        }
                    ],
                },
                {
                    "transaction_id": "waiver-1",
                    "type": "waiver",
                    "status": "complete",
                    "created": 1_767_312_000_000,
                    "roster_ids": [1],
                    "adds": {"p2": 1},
                    "drops": {"p3": 1},
                    "draft_picks": [],
                },
                {
                    "transaction_id": "add-1",
                    "type": "free_agent",
                    "status": "complete",
                    "created": 1_767_398_400_000,
                    "roster_ids": [2],
                    "adds": {"p3": 2},
                    "drops": None,
                    "draft_picks": [],
                },
            ],
        }
        self.transactions = normalize_transactions(self.data)

    def test_normalizes_player_and_pick_movements(self) -> None:
        trade = next(item for item in self.transactions if item["type"] == "trade")
        self.assertEqual(trade["assets"][0]["source"], "Alpha")
        self.assertEqual(trade["assets"][0]["destination"], "Bravo")
        self.assertEqual(trade["assets"][0]["position"], "QB")
        self.assertTrue(trade["has_draft_pick"])
        self.assertEqual(trade["assets"][1]["label"], "2027 Round 2")

    def test_calculates_all_summary_statistics(self) -> None:
        summary = transaction_summary(self.transactions, self.data)
        self.assertEqual(summary["trades"], 1)
        self.assertEqual(summary["waivers"], 1)
        self.assertEqual(summary["adds"], 3)
        self.assertEqual(summary["drops"], 2)
        self.assertEqual(summary["most_active_team"], "Alpha")
        self.assertNotEqual(summary["most_recent"], "—")

    def test_filters_every_supported_dimension(self) -> None:
        cases = (
            ({"team": "2"}, 2),
            ({"owner": "Alice"}, 2),
            ({"type": "waiver"}, 1),
            ({"player": "Quarter Back"}, 1),
            ({"draft_pick": "yes"}, 1),
            ({"draft_pick": "no"}, 2),
            ({"date_from": "2026-01-02"}, 2),
            ({"date_to": "2026-01-01"}, 1),
            ({"q": "trade-1"}, 1),
            ({"q": "2027 round 2"}, 1),
        )
        for filters, expected in cases:
            with self.subTest(filters=filters):
                self.assertEqual(
                    len(filter_transactions(self.transactions, filters)), expected
                )

    def test_sorts_and_paginates_cached_transactions(self) -> None:
        ordered = sort_transactions(self.transactions, "date", "desc")
        self.assertEqual(ordered[0]["id"], "add-1")
        view = transaction_center(
            self.data,
            {"sort": "date", "direction": "asc", "page": 2, "per_page": 10},
        )
        self.assertEqual(view["page"], 1)
        self.assertEqual(view["page_count"], 1)
        self.assertEqual(view["total_filtered"], 3)
        self.assertEqual(view["transactions"][0]["id"], "trade-1")


class TransactionSyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_state = dict(STATE)
        STATE.update(
            {
                "data": {
                    "week": 7,
                    "teams": [{"roster_id": 1, "team_name": "Cached Team"}],
                    "transactions": [{"transaction_id": "cached"}],
                },
                "transactions_last_sync": None,
                "transactions_last_error": None,
                "transactions_syncing": False,
            }
        )

    def tearDown(self) -> None:
        STATE.clear()
        STATE.update(self.original_state)

    async def test_refresh_updates_only_transactions(self) -> None:
        refreshed = [{"transaction_id": "fresh"}]
        with (
            patch(
                "services.sleeper.sleeper_get", AsyncMock(return_value=refreshed)
            ) as sleeper_get,
            patch("services.sleeper.save_cache") as save_cache,
        ):
            result = await sync_transactions()

        self.assertTrue(result)
        self.assertEqual(STATE["data"]["transactions"], refreshed)
        self.assertEqual(
            STATE["data"]["teams"],
            [{"roster_id": 1, "team_name": "Cached Team"}],
        )
        self.assertIn("/transactions/7", sleeper_get.await_args.args[1])
        self.assertIsNone(STATE["transactions_last_error"])
        save_cache.assert_called_once()

    async def test_refresh_failure_preserves_cached_transactions(self) -> None:
        with (
            patch(
                "services.sleeper.sleeper_get",
                AsyncMock(side_effect=RuntimeError("Sleeper unavailable")),
            ),
            patch("services.sleeper.save_cache") as save_cache,
        ):
            result = await sync_transactions()

        self.assertFalse(result)
        self.assertEqual(
            STATE["data"]["transactions"], [{"transaction_id": "cached"}]
        )
        self.assertEqual(
            STATE["transactions_last_error"], "RuntimeError: Sleeper unavailable"
        )
        save_cache.assert_not_called()


if __name__ == "__main__":
    unittest.main()
