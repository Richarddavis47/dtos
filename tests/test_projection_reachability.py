"""Storage inventory must follow identities, never week labels, without writes."""

import sqlite3
import unittest

from src.core.projection_intelligence import state_storage
from tools.projection_reachability import analyze, horizon_references


class ProjectionReachabilityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript(
            state_storage.SCHEMA
            + """
          CREATE TABLE projection_snapshots(snapshot_id TEXT PRIMARY KEY,
            league_id TEXT,season INTEGER,week INTEGER,generated_at TEXT,payload TEXT);
          CREATE TABLE projection_publication_heads(league_id TEXT PRIMARY KEY,snapshot_id TEXT);
          CREATE TABLE projection_actuals(snapshot_id TEXT);
        """
        )

    def snapshot(self, identity, week=2, league="a", **extra):
        body = dict(
            projection_snapshot_id=identity,
            league_id=league,
            season=2026,
            week=week,
            generated_at="2026-09-23",
            scoring_profile_id="ppr",
            model_version="1",
            contract_version="1",
            players={"player": {"canonical_projection": 0, "week": week}},
            **extra,
        )
        encoded = state_storage.encode(self.db, body)
        self.db.execute(
            "INSERT INTO projection_snapshots VALUES (?,?,?,?,?,?)",
            (identity, league, 2026, week, body["generated_at"], encoded),
        )

    def head(self, identity, league="a"):
        self.db.execute(
            "INSERT INTO projection_publication_heads VALUES (?,?)", (league, identity)
        )

    def test_week_keys_are_not_snapshot_ids_and_report_is_read_only(self):
        self.snapshot("week-two")
        self.snapshot("week-three", 3)
        self.snapshot("head", horizon_snapshot_ids={"2": "week-two", "3": "week-three"})
        self.head("head")
        self.db.commit()
        before = self.db.total_changes
        self.db.execute("PRAGMA query_only=ON")
        report = analyze(self.db, details=True)
        self.assertTrue(report["graph_valid"], report)
        self.assertEqual(report["classifications"]["ACTIVE_REACHABLE"]["rows"], 5)
        self.assertEqual(before, self.db.total_changes)
        self.assertEqual(report, analyze(self.db, details=True))
        self.assertFalse(report["deletion_authorized"])

    def test_genuinely_missing_snapshot_is_reported(self):
        self.snapshot("head", horizon_snapshot_ids={"3": "absent"})
        self.head("head")
        result = analyze(self.db)
        self.assertFalse(result["graph_valid"])
        self.assertEqual(
            result["unresolved_references"][0]["reason"], "MISSING_SNAPSHOT"
        )

    def test_other_league_cannot_supply_horizon(self):
        self.snapshot("foreign", 3, "b")
        self.snapshot("head", horizon_snapshot_ids={"3": "foreign"})
        self.head("head")
        result = analyze(self.db)
        self.assertFalse(result["graph_valid"])
        self.assertIn("HORIZON_SCOPE_MISMATCH", str(result["unresolved_references"]))

    def test_actuals_preserve_old_snapshot(self):
        self.snapshot("old", 1)
        self.snapshot("recent", 3)
        self.snapshot("head")
        self.head("head")
        self.db.execute("INSERT INTO projection_actuals VALUES ('old')")
        result = analyze(self.db)
        self.assertTrue(result["graph_valid"])
        self.assertEqual(
            result["classifications"]["HISTORICAL_CHECKPOINT_REACHABLE"]["rows"], 2
        )

    def test_missing_player_state_blocks_graph(self):
        self.snapshot("head")
        self.head("head")
        self.db.execute("DELETE FROM projection_player_states")
        result = analyze(self.db)
        self.assertFalse(result["graph_valid"])
        self.assertIn("MISSING_PLAYER_STATE", str(result["unresolved_references"]))

    def test_invalid_manifest_is_not_silently_ignored(self):
        for value in (["id"], {"19": "id"}, {"2": None}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                horizon_references({"horizon_snapshot_ids": value})


if __name__ == "__main__":
    unittest.main()
