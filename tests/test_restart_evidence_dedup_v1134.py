import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests import test_capture_restart_evidence_v1133 as capture_tests
from tools.validation.capture_restart_evidence import capture, provider_digest
from tools.validation.restart_evidence import (
    REQUIRED, differences, fingerprint, record_at, snapshot,
)


class RestartEvidenceDedupTests(unittest.TestCase):
    def test_provider_evidence_occurs_once_and_exact_confidence_is_retained(self):
        base = capture_tests.RestartCaptureTests().reader()
        row = {"provider": "FantasyCalc", "raw_value": 6000, "confidence": 76,
               "normalized_value": 600, "freshness": "fresh",
               "updated_at": "2026-09-05T10:00:00+00:00", "unknown_new_field": "private"}
        asset = {"asset_id": "player:1", "providers": [row]}

        def read(path):
            result = base(path)
            if path.startswith("/api/valuation/assets?"):
                result["assets"] = [asset]
            if path == "/api/market/health":
                result["semantic_identity"]["provider_evidence_digest"] = provider_digest([asset])
            return result

        with tempfile.TemporaryDirectory() as folder:
            evidence = capture(read, Path(folder) / "capture.json")
        self.assertEqual(len(evidence["tree"]["provider_confidence"]["children"]), 1)
        location = ("$.semantic_records/0/key:" + fingerprint("valuation")[:16]
                    + "/key:" + fingerprint("providers")[:16] + "/0/")
        self.assertEqual(record_at(evidence, location + "confidence")["value"], 76)
        self.assertEqual(record_at(evidence, location + "normalized_value")["value"], 600)
        self.assertEqual(record_at(evidence, location + "updated_at")["value"], row["updated_at"])
        self.assertNotIn('"private"', json.dumps(evidence))
        self.assertIn("key:" + fingerprint("unknown_new_field")[:16],
                      record_at(evidence, location.rstrip("/"))["children"])

    def test_normalized_change_and_unknown_fields_remain_strict(self):
        original = {key: None for key in REQUIRED}
        original["semantic_records"] = [{"valuation": {"providers": [{"confidence": 76}]}}]
        before = snapshot(original)
        changed = copy.deepcopy(original)
        changed["semantic_records"][0]["valuation"]["providers"][0]["confidence"] = 65
        result = differences(before, snapshot(changed))
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["before"]["value"], result[0]["after"]["value"]), (76, 65))
        changed["semantic_records"][0]["valuation"]["providers"][0]["new_field"] = True
        # Confidence, the new field, and its containing object's size all differ.
        self.assertEqual(len(differences(before, snapshot(changed))), 3)

    def test_private_confidence_outside_exact_provider_location_stays_hashed(self):
        data = {key: None for key in REQUIRED}
        data["semantic_records"] = [{"private": {"confidence": 76}}]
        encoded = json.dumps(snapshot(data))
        self.assertNotIn('"value": 76', encoded)

    def test_old_duplicate_layout_cannot_be_compared_as_same_schema(self):
        current = snapshot({key: None for key in REQUIRED})
        old = {**current, "schema": "dtos-restart-evidence-v2"}
        with self.assertRaisesRegex(ValueError, "schemas"):
            differences(old, current)
