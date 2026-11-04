"""Provider freshness cannot be reconstructed from a successful retrieval."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import freshness_state


class ProjectionSourceTimeTests(unittest.TestCase):
    def test_invalid_naive_future_and_missing_times_are_not_fresh(self):
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        for value in (None, "invalid", "2026-09-13", "2027-01-01T00:00:00+00:00"):
            with self.subTest(value=value):
                self.assertEqual(freshness_state(value, now=now), "Unavailable")

    def test_active_generation_uses_provider_time_not_retrieval(self):
        data = {"league": {"season": 2026, "scoring_settings": {"pass_yd": .04}},
                "week": 1, "players": [{"id": "10", "position": "QB"}]}
        with tempfile.TemporaryDirectory() as temporary:
            service = ProjectionService(Path(temporary) / "projection.sqlite3")
            for timestamp, expected in (("2001-01-01T00:00:00+00:00", "Stale"),
                                        (None, "Unavailable")):
                payload = [{"player_id": "10", "season": 2026, "week": 1,
                            "updated_at": timestamp, "stats": {"pass_yd": 250}}]
                with patch("src.core.projection_intelligence.service._now",
                           return_value="2026-09-13T00:00:00+00:00"):
                    service.ingest_sleeper(payload, data=data, league_id="a", season=2026, week=1)
                row = service.snapshot()["players"]["10"]
                self.assertEqual(row["source_freshness"], expected)
                self.assertEqual(row["source_timestamp"], timestamp)
                self.assertEqual(row["canonical_projection"], 10)

    def test_genuine_provider_update_is_fresh(self):
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        self.assertEqual(freshness_state(now.isoformat(), now=now), "Fresh")
