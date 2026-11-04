"""Exact semantic preservation precedes any production migration."""
import copy
import json
import sqlite3
import unittest

from src.core.fois import state_storage as storage


class FOISStateStorageTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(storage.SCHEMA)
        self.addCleanup(self.db.close)
        self.payload = {
            "score_key": "private-league:gm:period:model", "league_id": "league-a",
            "franchise_id": "1", "gm_id": "gm-a", "tenure_id": "tenure-a",
            "model_version": "5.0", "evaluation_start_season": 2021,
            "generated_at": "2026-09-01", "brain_snapshot_id": "brain-1",
            "overall_score": 70, "evidence": {"as_of": "2021-01-01", "value": None},
        }

    def test_observations_share_exact_state_and_round_trip(self):
        second = {**self.payload, "generated_at": "2026-09-02", "brain_snapshot_id": "brain-2"}
        for payload in (self.payload, second):
            self.assertEqual(storage.decode(self.db, storage.encode(self.db, payload)), payload)
        self.assertEqual(self.db.execute("SELECT count(*) FROM fois_semantic_states").fetchone()[0], 1)

    def test_every_material_or_unknown_field_is_semantic(self):
        identity = storage.split(self.payload)[0]
        for field, value in {
            "league_id": "league-b", "franchise_id": "2", "gm_id": "gm-b",
            "tenure_id": "tenure-b", "model_version": "6.0", "overall_score": 71,
            "evaluation_start_season": 2022, "account_scope": "private-b",
            "new_future_semantic_field": 1, "evidence": {"as_of": "2022-01-01", "value": 0},
        }.items():
            with self.subTest(field=field):
                self.assertNotEqual(identity, storage.split({**self.payload, field: value})[0])

    def test_missing_is_not_null_or_zero_and_nested_dates_are_semantic(self):
        missing = copy.deepcopy(self.payload)
        del missing["evidence"]["value"]
        self.assertNotEqual(storage.split(missing)[0], storage.split(self.payload)[0])
        for field in storage.OBSERVATION_FIELDS:
            missing = dict(self.payload)
            del missing[field]
            self.assertEqual(storage.decode(self.db, storage.encode(self.db, missing)), missing)

    def test_legacy_payload_and_corrupt_reference_fail_closed(self):
        self.assertEqual(storage.decode(self.db, json.dumps(self.payload)), self.payload)
        value = storage.encode(self.db, self.payload)
        self.db.execute("DELETE FROM fois_semantic_states")
        with self.assertRaises(ValueError):
            storage.decode(self.db, value)

    def test_classification_does_not_mutate(self):
        self.db.execute("CREATE TABLE fois_snapshot_history(snapshot_id TEXT,payload TEXT)")
        self.db.executemany("INSERT INTO fois_snapshot_history VALUES (?,?)", [
            (str(i), json.dumps({**self.payload, "generated_at": str(i)})) for i in range(3)
        ])
        before = self.db.total_changes
        report = storage.classify(self.db)
        self.assertEqual((report["observations"], report["semantic_states"], report["duplicate_observations"]), (3, 1, 2))
        self.assertEqual(self.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
