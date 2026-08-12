from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app_metadata import BUILD_NUMBER, VERSION
from src.core.inspection.live import PublicSurface, external_mirror_policy
from src.core.inspection.live_visual import live_visual_capture_requests
from tools.inspection.mirror import build_mirror
from tools.inspection.verify_mirror import verify


def png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (390, 844), "navy").save(stream, "PNG")
    return stream.getvalue()


class ExternalVisualMirrorTests(unittest.TestCase):
    def fixture(self) -> dict[str, bytes]:
        starters = [{
            "player_id": str(index), "player_name": f"Player {index}",
            "displayed": {"sleeper_projection": float(index), "dtos_projection": float(index + 1)},
        } for index in range(1, 23)]
        semantic = {
            "teams": [{"roster_id": "1", "starters": starters[:11]},
                      {"roster_id": "2", "starters": starters[11:]}],
        }
        captures = []
        for surface_id, semantic_url, starter_count in (
            ("matchups-1", "/semantic/matchup", 22),
            ("home", "/semantic/home", 0),
        ):
            for viewport in ("mobile", "desktop"):
                captures.append({
                    "surface_id": surface_id, "title": surface_id,
                    "human_url": "/" if surface_id == "home" else "/matchups/1",
                    "semantic_url": semantic_url, "viewport": viewport,
                    "status": "current", "captured_at": "2026-01-01T00:00:00Z",
                    "screenshot_url": f"/png/{surface_id}/{viewport}",
                    "presentation": {"presentation_contract": {
                        "starter_count": starter_count,
                        "sleeper_projection_visible": starter_count == 22,
                        "dtos_projection_visible": starter_count == 22,
                    }},
                })
        audit = {"identity": {"projection_snapshot_id": "projection"}, "players": [
            {"matchup_id": "1", "roster_id": "1" if index <= 11 else "2",
             "player_id": str(index), "sleeper_projection": float(index),
             "dtos_projection": float(index + 1)}
            for index in range(1, 23)
        ]}
        live = {"identity": {
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "commit": "commit", "league_id": "league", "league_name": "League",
            "projection_snapshot_id": "projection", "brain_snapshot_id": "brain",
            "asset_market_generation": "market",
        }}
        return {
            "/api/inspect/live": json.dumps(live).encode(),
            "/api/inspect/live/visual/manifest": json.dumps({
                "status": "complete", "last_capture": "2026-01-01T00:00:00Z",
                "captures": captures,
            }).encode(),
            "/api/audit/projections/current": json.dumps(audit).encode(),
            "/api/inspect/live/visual": json.dumps({
                "eligible_surfaces": [{"surface_id": "home"}, {"surface_id": "future"}],
            }).encode(),
            "/semantic/matchup": json.dumps(semantic).encode(),
            "/semantic/home": b'{"surface":{"surface_id":"home"}}',
            **{f"/png/{surface}/{viewport}": png()
               for surface in ("matchups-1", "home") for viewport in ("mobile", "desktop")},
        }

    def test_exact_verified_artifacts_are_mirrored_with_stable_discovery(self):
        fixture = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            result = build_mirror(
                base_url="https://dtos.example", output=Path(folder),
                fetch=lambda path: fixture[path],
            )
            self.assertEqual(result["status"], "complete")
            self.assertEqual(len(result["entries"]), 4)
            self.assertEqual(len([row for row in result["entries"] if row["surface_id"] == "matchups-1"]), 2)
            self.assertEqual(result["current_manifest_url"],
                             "https://github.com/Richarddavis47/dtos/releases/latest/download/dtos-live-inspection-current.json")
            source = fixture["/png/matchups-1/mobile"]
            mirrored = (Path(folder) / "matchup-1-mobile.png").read_bytes()
            self.assertEqual(source, mirrored)
            self.assertEqual(result["entries"][2]["starter_count"], 22)
            self.assertLess(result["total_bytes"], 5_000_000)

    def test_projection_mismatch_fails_closed(self):
        fixture = self.fixture()
        audit = json.loads(fixture["/api/audit/projections/current"])
        audit["players"][0]["dtos_projection"] = 999
        fixture["/api/audit/projections/current"] = json.dumps(audit).encode()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "projection audit"):
                build_mirror(base_url="https://dtos.example", output=Path(folder),
                             fetch=lambda path: fixture[path])

    def test_public_surface_registration_inherits_mirror_policy(self):
        future = PublicSurface(
            surface_id="future-dashboard", surface_type="page", title="Future",
            category="Future", method="GET", route="/future", human_url="/future",
            semantic_url="/api/inspect/live/surfaces/future-dashboard", parameterized=False,
        )
        representative = PublicSurface(
            surface_id="future-entity", surface_type="page", title="Future Entity",
            category="Future", method="GET", route="/future/{id}", human_url="/future/{id}",
            semantic_url="/api/inspect/live/surfaces/future-entity", parameterized=True,
        )
        self.assertEqual(external_mirror_policy(future), "always")
        self.assertEqual(external_mirror_policy(representative), "representative_or_requested")
        inspector = SimpleNamespace(
            data={"matchups": {}}, projection_snapshot=None, surfaces=(future, representative),
            identity=lambda: {"inspection_generated_at": "now"},
        )
        requests = live_visual_capture_requests(inspector)
        self.assertEqual({row.surface_id for row in requests}, {"future-dashboard"})
        self.assertEqual({row.viewport for row in requests}, {"mobile", "desktop"})

    def test_sensitive_json_is_rejected(self):
        fixture = self.fixture()
        live = json.loads(fixture["/api/inspect/live"])
        live["private"] = "C:\\Users\\someone\\secret"
        fixture["/api/inspect/live"] = json.dumps(live).encode()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "forbidden"):
                build_mirror(base_url="https://dtos.example", output=Path(folder),
                             fetch=lambda path: fixture[path])

    def test_github_only_verifier_never_needs_the_render_origin(self):
        fixture = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            result = build_mirror(
                base_url="https://dtos.example", output=output,
                fetch=lambda path: fixture[path],
            )
            manifest_url = result["current_manifest_url"]
            published = {f"https://github.com/Richarddavis47/dtos/releases/download/v{VERSION}/{path.name}": path.read_bytes()
                         for path in output.iterdir()}
            published[manifest_url] = (output / "dtos-live-inspection-current.json").read_bytes()
            verified = verify(manifest_url, fetch=lambda url: published[url])
            self.assertEqual(verified["status"], "complete")
            self.assertEqual(verified["matchups"], 1)
            self.assertEqual(verified["hash_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
