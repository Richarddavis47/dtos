"""Canonical fixture ownership, trade and semantic discovery integrity."""
from pathlib import Path
import tempfile
import unittest

from src.core.inspection.discovery import discover_pages
from tools.validation.generate_sanitized_market_fixture import _cache, _trade_replay_fixture


class CanonicalFixtureInventoryTests(unittest.TestCase):
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
        all_assets = {asset for _, asset, _ in occurrences}
        from tools.validation.browser_fixture_images import prepared_ids
        self.assertTrue(all_assets <= set(prepared_ids()))
        self.assertTrue(all_assets <= self.data["players"].keys())
        valued = {asset for asset in all_assets if int(asset[1:]) < 1000}
        self.assertEqual(len(valued), 50)
        self.assertTrue(valued <= self.data["players"].keys())

    def test_full_application_inventory_contains_four_pick_dossiers(self):
        from dtos_app import app

        pages = discover_pages(app.routes, {"data": self.data}, historical_trades=("fixture-1", "fixture-2", "fixture-3"))
        picks = [row for row in pages if row.route.startswith("/picks/") and not row.excluded]
        self.assertEqual(len(picks), 4)
        self.assertTrue(all("{" not in row.route for row in picks))
