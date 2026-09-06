"""Production-shaped DINS must include the canonical pick-detail surfaces."""
from pathlib import Path
import tempfile
import unittest

from src.core.inspection.discovery import discover_pages
from tools.validation.generate_sanitized_market_fixture import _cache, _trade_replay_fixture
from tools.validation.linux_dins_memory_gate import require_full_inventory


class DinsFixtureInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.data = _cache(Path(directory.name) / "cache.json")

    def test_sleeper_projection_matches_existing_ledger_without_new_assets(self):
        ledger = self.data["pick_ledger"]
        self.assertEqual(len(ledger), 120)
        expected = {(str(row["season"]), row["round"], row["original_roster_id"]): row["current_owner_id"]
                    for row in ledger if row["is_traded"]}
        actual = {(row["season"], row["round"], row["roster_id"]): row["owner_id"]
                  for row in self.data["traded_picks"]}
        self.assertEqual(expected, actual)
        self.assertEqual(len(actual), len(self.data["traded_picks"]))

    def test_valued_historical_trade_assets_are_existing_canonical_players(self):
        seasons, occurrences = _trade_replay_fixture()
        self.assertEqual(len(occurrences), 1578)
        self.assertEqual(sum(len(rows) for weeks in seasons.values() for rows in weeks.values()), 231)
        valued = {asset for _, asset, _ in occurrences if not asset.startswith("unavailable-")}
        self.assertEqual(len(valued), 50)
        self.assertTrue(valued <= self.data["players"].keys())

    def test_full_application_inventory_contains_four_pick_dossiers(self):
        from dtos_app import app

        pages = discover_pages(app.routes, {"data": self.data}, historical_trades=("fixture-1", "fixture-2", "fixture-3"))
        rows = [{"route": row.route, "excluded": row.excluded} for row in pages]
        require_full_inventory({"pages": rows})
        picks = [row for row in pages if row.route.startswith("/picks/") and not row.excluded]
        self.assertEqual(len(picks), 4)
        self.assertTrue(all("{" not in row.route for row in picks))
        self.assertEqual(sum(not row.excluded for row in pages), 61)

    def test_missing_pick_pages_fail_before_capture_not_by_lowering_coverage(self):
        with self.assertRaisesRegex(AssertionError, "61 pages"):
            require_full_inventory({"pages": [{"route": f"/fixture/{i}"} for i in range(57)]})
        with self.assertRaisesRegex(AssertionError, "Diagnostic"):
            require_full_inventory({"pages": [{"route": "/__validation__/control"}] * 61})
