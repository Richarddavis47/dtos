from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.core.asset_market.semantic_contract import digest
from src.core.valuation.normalization import normalize_value


class ProviderNormalizationFreshnessTests(unittest.TestCase):
    def normalized(self, hours: float, raw: float = 6000):
        observed = datetime(2026, 9, 4, 17, 30, tzinfo=timezone.utc)
        with patch("src.core.valuation.normalization.datetime") as clock:
            clock.now.return_value = observed + timedelta(hours=hours)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            return normalize_value(
                "FantasyCalc", raw, updated_at=observed.isoformat(),
                provider_confidence=85,
            )

    def test_identical_evidence_within_material_state_is_identical(self):
        first = self.normalized(16.673)
        later = self.normalized(16.862)
        self.assertEqual(first, later)
        self.assertEqual(first.confidence_score, 76)

    def test_all_market_freshness_boundaries_remain_material(self):
        for boundary in (36, 72, 168):
            with self.subTest(boundary=boundary):
                before = self.normalized(boundary - 0.001)
                after = self.normalized(boundary)
                self.assertGreater(before.confidence_score, after.confidence_score)
                self.assertEqual(before.normalized_value, after.normalized_value)

    def test_provider_digest_stable_within_tier_not_across_boundary(self):
        def identity(hours):
            row = self.normalized(hours)
            return digest({"normalized_value": row.normalized_value,
                           "confidence": row.confidence_score})
        self.assertEqual(identity(16.673), identity(16.862))
        self.assertNotEqual(identity(35.999), identity(36))

    def test_changed_raw_evidence_still_changes_value(self):
        self.assertNotEqual(self.normalized(1).normalized_value,
                            self.normalized(1, 7000).normalized_value)

    def test_fresh_processes_preserve_digest_until_material_boundary(self):
        script = """
import json, sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from src.core.valuation.normalization import normalize_value
from src.core.asset_market.semantic_contract import digest
observed = datetime(2026, 9, 4, tzinfo=timezone.utc)
with patch('src.core.valuation.normalization.datetime') as clock:
    clock.now.return_value = observed + timedelta(hours=float(sys.argv[1]))
    clock.fromisoformat.side_effect = datetime.fromisoformat
    row = normalize_value('FantasyCalc', 6000, updated_at=observed.isoformat(), provider_confidence=85)
print(json.dumps({'digest': digest(asdict(row)), 'confidence': row.confidence_score}))
"""
        def run(hours):
            result = subprocess.run([sys.executable, "-c", script, str(hours)],
                                    capture_output=True, text=True, check=True, timeout=20)
            return json.loads(result.stdout)
        self.assertEqual(run(16.673), run(16.862))
        self.assertNotEqual(run(35.999)["digest"], run(36)["digest"])


if __name__ == "__main__":
    unittest.main()
