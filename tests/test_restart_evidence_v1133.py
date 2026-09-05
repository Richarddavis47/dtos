import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validation.restart_evidence import REQUIRED, differences, persist, record_at, snapshot


class RestartEvidenceTests(unittest.TestCase):
    def inputs(self):
        return {key: None for key in REQUIRED} | {
            "account_identity": "private-account",
            "league_identity": "private-league",
            "provider_confidence": [{"provider": "FantasyCalc", "confidence": 76}],
            "market_rows": [{"asset_id": "player:1"}, {"asset_id": "player:2"}],
        }

    def test_exact_comparison_preserves_order_and_isolation(self):
        original = self.inputs()
        before = snapshot(original)
        self.assertEqual(differences(before, snapshot(copy.deepcopy(original))), [])
        for key in ("account_identity", "league_identity", "market_rows"):
            changed = copy.deepcopy(original)
            changed[key] = list(reversed(changed[key])) if isinstance(changed[key], list) else "other"
            changes = differences(before, snapshot(changed))
            self.assertTrue(changes)
            self.assertTrue(all(row["path"].startswith("$." + key) for row in changes))

    def test_confidence_change_has_specific_structural_location(self):
        original = self.inputs()
        changed = copy.deepcopy(original)
        changed["provider_confidence"][0]["confidence"] = 69
        result = differences(snapshot(original), snapshot(changed))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["path"].startswith("$.provider_confidence/0/"))

    def test_secrets_and_incomplete_contract_fail_closed(self):
        with self.assertRaises(ValueError):
            snapshot({})
        data = self.inputs()
        data["calibration"] = {"token": "must-not-survive"}
        with self.assertRaises(ValueError):
            snapshot(data)

    def test_private_values_not_retained(self):
        encoded = json.dumps(snapshot(self.inputs()))
        self.assertNotIn("private-account", encoded)
        self.assertNotIn("private-league", encoded)
        self.assertNotIn("player:1", encoded)

    def test_freshness_state_and_timestamp_are_exact_but_private_strings_are_not(self):
        data = self.inputs()
        data["source_timestamps"] = [{"last_successful_refresh": "2026-09-05T10:00:00+00:00",
                                      "tier": "Aging", "next_threshold_hours": 72,
                                      "source_timestamp": "private-free-text"}]
        evidence = snapshot(data)
        self.assertEqual(record_at(evidence, "$.source_timestamps/0/tier")["value"], "Aging")
        self.assertEqual(record_at(evidence, "$.source_timestamps/0/next_threshold_hours")["value"], 72)
        self.assertEqual(record_at(evidence, "$.source_timestamps/0/last_successful_refresh")["value"],
                         "2026-09-05T10:00:00+00:00")
        self.assertNotIn("private-free-text", json.dumps(evidence))

    def test_failed_publication_preserves_prior_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "before.json"
            evidence = snapshot(self.inputs())
            persist(path, evidence)
            with patch("tools.validation.restart_evidence.os.replace", side_effect=OSError):
                with self.assertRaises(OSError):
                    persist(path, evidence)
            self.assertEqual(json.loads(path.read_text()), evidence)
            self.assertEqual(list(Path(folder).glob(".restart-*")), [])

    def test_compact_key_collision_fails_closed_across_captures(self):
        before = snapshot(self.inputs())
        after = copy.deepcopy(before)
        key = next(iter(after["key_hashes"]))
        after["key_hashes"][key] = key + "f" * 48
        with self.assertRaisesRegex(ValueError, "collision"):
            differences(before, after)

    def test_unknown_nested_field_and_type_change_are_not_ignored(self):
        original = self.inputs()
        changed = copy.deepcopy(original)
        changed["market_rows"][0]["new_contract_field"] = {"evidence": 1}
        added = differences(snapshot(original), snapshot(changed))
        self.assertTrue(any(row["before"] is None for row in added))
        self.assertTrue(all(row["path"].startswith("$.market_rows") for row in added))
        self.assertEqual(len(added), len(differences(snapshot(changed), snapshot(original))))
        changed["market_rows"] = "not-an-array"
        self.assertTrue(differences(snapshot(original), snapshot(changed)))


if __name__ == "__main__":
    unittest.main()
