"""Display compatibility is independent of source/scoring compatibility."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core.projection_intelligence.service import (
    ProjectionService,
    qualify_retained_display,
)
from src.core.projection_intelligence.scoring import DISPLAY_METHOD_VERSION
from services.player_projection_view import player_projection_view


class LegacyDisplayIntegrityTests(unittest.TestCase):
    def test_read_contract_preserves_original_points_identity_and_provenance(self):
        old = {
            "projection_snapshot_id": "original",
            "players": {
                "t": {
                    "canonical_projection": 7.5,
                    "sleeper_web_display_projection": "5.00",
                    "display_method_version": "sleeper-web-sequential-number-tofixed2-v1",
                }
            },
        }
        read = qualify_retained_display(old)
        self.assertEqual(old["players"]["t"]["sleeper_web_display_projection"], "5.00")
        self.assertEqual(read["projection_snapshot_id"], "original")
        self.assertEqual(read["players"]["t"]["canonical_projection"], 7.5)
        self.assertIsNone(read["players"]["t"]["sleeper_web_display_projection"])
        self.assertEqual(
            read["players"]["t"]["retained_display_evidence"]["value"], "5.00"
        )
        self.assertIn("unverified", read["players"]["t"]["display_reason"])

    def test_same_version_restart_zero_missing_foreign_context_and_no_growth(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch(
                "services.global_evidence.retained_global_evidence", return_value=None
            ),
        ):
            path = Path(folder) / "p.sqlite3"
            data = {
                "league": {
                    "league_id": "a",
                    "season": "2026",
                    "scoring_settings": {"rec": 1, "bonus_rec_te": 0.5},
                },
                "week": 1,
                "players": {"t": {"id": "t", "position": "TE"}},
            }
            service = ProjectionService(path, league_id="a")
            for stats, expected in (
                ({"rec": 5}, 7.5),
                ({"rec": 5, "bonus_rec_te": 0}, 5),
                ({"rec": 0}, 0),
                ({}, None),
            ):
                feed = {
                    1: [
                        {
                            "player_id": "t",
                            "season": 2026,
                            "week": 1,
                            "player": {"position": "TE"},
                            "stats": stats,
                        }
                    ]
                }
                snapshot = service.publish_horizon(
                    feed, data=data, league_id="a", season=2026, current_week=1
                )
                restarted = ProjectionService(path, league_id="a")
                row = restarted.player("t")
                self.assertEqual(row["canonical_projection"], expected)
                self.assertEqual(row["display_method_version"], DISPLAY_METHOD_VERSION)
                self.assertNotIn("retained_display_evidence", row)
                size = path.stat().st_size
                for _ in range(8):
                    self.assertEqual(
                        player_projection_view(data, "t", restarted)["value"], expected
                    )
                self.assertEqual(size, path.stat().st_size)
                self.assertEqual(
                    snapshot["projection_snapshot_id"],
                    service.publish_horizon(
                        feed, data=data, league_id="a", season=2026, current_week=1
                    )["projection_snapshot_id"],
                )
                self.assertEqual(size, path.stat().st_size)
                foreign = {**data, "league": {**data["league"], "league_id": "b"}}
                self.assertIsNone(
                    player_projection_view(foreign, "t", restarted)["value"]
                )
                other_scoring = {
                    **data,
                    "league": {
                        **data["league"],
                        "scoring_settings": {"rec": 1, "bonus_rec_te": 1},
                    },
                }
                self.assertIsNone(
                    player_projection_view(other_scoring, "t", restarted)["value"]
                )
