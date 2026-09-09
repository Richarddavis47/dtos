import tempfile
import subprocess
import sys
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from collections import namedtuple

from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact


class GlobalEvidenceStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "global.sqlite3"
        self.store = GlobalEvidenceStore(self.path)
        self.fact = GlobalFact("production", "sleeper:1", "approved-fixture", "game:1",
                               "2025-09-01T00:00:00Z", "2025-09-02T00:00:00Z",
                               {"pass_yd": 250, "pass_int": 0}, season=2025, week=1)

    def tearDown(self):
        self.directory.cleanup()

    def test_500_consumers_share_one_fact_and_replay_has_zero_file_growth(self):
        self.store.publish([self.fact], retrieved_at="2026-01-01T00:00:00Z")
        before = self.path.read_bytes()
        for _ in range(500):
            result = self.store.publish([self.fact], retrieved_at="2026-02-01T00:00:00Z")
            self.assertEqual(result, {"created": 0, "reused": 1})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.counts(), {"production": 1})

    def test_correction_preserves_prior_as_of_and_restart(self):
        correction = replace(self.fact, known_at="2025-09-05T00:00:00Z", values={"pass_yd": 249, "pass_int": 0})
        self.store.publish([self.fact, correction], retrieved_at="2026-01-01T00:00:00Z")
        reopened = GlobalEvidenceStore(self.path)
        self.assertEqual(reopened.read("production", "sleeper:1", as_of="2025-09-03T00:00:00Z")[0]["values"]["pass_yd"], 250)
        self.assertEqual(reopened.read("production", "sleeper:1", as_of="2025-09-06T00:00:00Z")[0]["values"]["pass_yd"], 249)
        self.assertEqual(reopened.read("production", "sleeper:1", as_of="2025-08-01T00:00:00Z"), [])

    def test_unknown_publication_time_cannot_backdate_knowledge(self):
        self.store.publish([replace(self.fact, known_at=None)], retrieved_at="2026-01-01T00:00:00Z")
        self.assertEqual(self.store.read("production", "sleeper:1", as_of="2025-10-01T00:00:00Z"), [])

    def test_a_b_a_transition_reuses_payload_but_preserves_temporal_revision(self):
        a = replace(self.fact, known_at=None)
        b = replace(a, values={"pass_yd": 249})
        for fact, day in ((a, 1), (b, 2), (a, 3)):
            self.store.publish([fact], retrieved_at=f"2026-01-0{day}T00:00:00Z")
        self.assertEqual(self.store.counts(), {"production": 2})
        for day, yards in ((1, 250), (2, 249), (3, 250)):
            rows = self.store.read("production", "sleeper:1", as_of=f"2026-01-0{day}T12:00:00Z")
            self.assertEqual(rows[0]["values"]["pass_yd"], yards)

    def test_read_facade_does_not_create_storage_or_allow_publication(self):
        from services.global_evidence import retained_global_evidence
        absent = Path(self.directory.name) / "absent" / "never.sqlite3"
        self.assertIsNone(retained_global_evidence(absent))
        self.assertFalse(absent.parent.exists())
        reader = retained_global_evidence(self.path)
        with self.assertRaises(PermissionError):
            reader.publish([self.fact], retrieved_at="2026-01-01T00:00:00Z")

    def test_storage_path_preserves_environment_overrides(self):
        from config import Settings
        custom = str(Path(self.directory.name) / "custom.sqlite3")
        with patch.dict(os.environ, {"DTOS_GLOBAL_EVIDENCE_FILE": custom}):
            self.assertEqual(Settings.from_environment().global_evidence_file, Path(custom))

    def test_private_or_nonfinite_payload_rolls_back_batch(self):
        for values in ({"nested": {"league_id": "private"}}, {"pass_yd": float("nan")}):
            with self.assertRaises(ValueError):
                self.store.publish([self.fact, replace(self.fact, values=values)], retrieved_at="2026-01-01T00:00:00Z")
            self.assertEqual(self.store.counts(), {})

    def test_batch_limit_and_naive_timestamps_fail_closed(self):
        with self.assertRaises(ValueError):
            self.store.publish([self.fact, self.fact], retrieved_at="2026-01-01T00:00:00Z", max_records=1)
        self.assertEqual(self.store.counts(), {})
        with self.assertRaises(ValueError):
            self.store.publish([self.fact], retrieved_at="2026-01-01")

    def test_disk_admission_preserves_last_valid_and_allows_unchanged_reuse(self):
        self.store.publish([self.fact], retrieved_at="2026-01-01T00:00:00Z")
        usage = namedtuple("Usage", "total used free")(100, 99, 1)
        with patch("src.core.data_platform.global_evidence.shutil.disk_usage", return_value=usage):
            self.assertEqual(self.store.publish([self.fact], retrieved_at="2026-02-01T00:00:00Z")["reused"], 1)
            with self.assertRaises(OSError):
                self.store.publish([replace(self.fact, values={"pass_yd": 999})], retrieved_at="2026-02-01T00:00:00Z")
        self.assertEqual(self.store.counts(), {"production": 1})

    def test_cross_process_reopen_returns_identical_fingerprint(self):
        self.store.publish([self.fact], retrieved_at="2026-01-01T00:00:00Z")
        expected = self.store.read("production", "sleeper:1", as_of="2026-01-02T00:00:00Z")[0]["fingerprint"]
        result = subprocess.run([sys.executable, "-c",
            "from pathlib import Path; from src.core.data_platform.global_evidence import GlobalEvidenceStore; import sys; "
            "s=GlobalEvidenceStore(Path(sys.argv[1])); print(s.read('production','sleeper:1',as_of='2026-01-02T00:00:00Z')[0]['fingerprint'])",
            str(self.path)], capture_output=True, text=True, timeout=20, check=True)
        self.assertEqual(result.stdout.strip(), expected)
