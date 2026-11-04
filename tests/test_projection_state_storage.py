import copy
import json
import sqlite3
import unittest

from src.core.projection_intelligence import state_storage as storage


class ProjectionStateStorageTests(unittest.TestCase):
    def test_changed_subset_stores_only_changed_players_and_round_trips(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript(storage.SCHEMA)
        first = {"league_id": "A", "model_version": "one", "players": {
            "1": {"value": None, "generated_at": "then", "projection_snapshot_id": "one"},
            "2": {"value": 0, "generated_at": "then", "projection_snapshot_id": "one"},
        }}
        second = copy.deepcopy(first)
        second["players"]["1"]["value"] = 12
        for player in second["players"].values():
            player.update(generated_at="later", projection_snapshot_id="two")
        before = storage.encode(db, first)
        after = storage.encode(db, second)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM projection_player_states").fetchone()[0], 3)
        self.assertEqual(storage.decode(db, before), first)
        self.assertEqual(storage.decode(db, after), second)
        self.assertEqual(storage.decode(db, json.dumps(first)), first)
        other = copy.deepcopy(first)
        other["league_id"] = "B"
        storage.encode(db, other)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM projection_player_states").fetchone()[0], 5)

    def test_unknown_evidence_and_model_changes_are_not_deduplicated(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript(storage.SCHEMA)
        base = {"league_id": "A", "players": {"1": {"value": None, "as_of": "2025"}}}
        for mutation in ({}, {"value": 0}, {"as_of": "2026"}, {"new_evidence": True}):
            snapshot = copy.deepcopy(base)
            snapshot["players"]["1"].update(mutation)
            encoded = storage.encode(db, snapshot)
            self.assertEqual(storage.decode(db, encoded), snapshot)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM projection_player_states").fetchone()[0], 4)
        db.execute("DELETE FROM projection_player_states")
        with self.assertRaisesRegex(ValueError, 'Missing'):
            storage.decode(db, encoded)
