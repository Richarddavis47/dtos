from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.core.inspection.live_capture_worker import run
from src.core.inspection.live_capture_process import capture_page_isolated
from src.core.inspection.live_visual import CaptureRequest


class LiveVisualProcessTests(unittest.TestCase):
    def request(self) -> CaptureRequest:
        return CaptureRequest(
            surface_id="matchups-1", title="Matchup 1", human_url="/matchups/1",
            semantic_url="/api/inspect/live/matchups/1", viewport="mobile",
            fingerprint="semantic", canonical={"projection_snapshot_id": "projection"},
        )

    def test_worker_uses_compact_contract_and_returns_bounded_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path, result_path = root / "input.json", root / "result.json"
            output = root / "capture.png"
            input_path.write_text(json.dumps({
                "capture_origin": "http://127.0.0.1:8767",
                "output_path": str(output),
                "request": {
                    "surface_id": "matchups-1", "title": "Matchup 1",
                    "human_url": "/matchups/1",
                    "semantic_url": "/api/inspect/live/matchups/1",
                    "viewport": "mobile", "fingerprint": "semantic",
                    "canonical": {"projection_snapshot_id": "projection"},
                },
            }), encoding="utf-8")

            def capture(origin, request, target):
                self.assertEqual(origin, "http://127.0.0.1:8767")
                self.assertEqual(request.surface_id, "matchups-1")
                Image.new("RGB", (390, 844), "navy").save(target, "PNG")
                return {"visible_text": "Matchup 1"}

            with patch("src.core.inspection.live_browser.capture_page", capture):
                self.assertEqual(run(input_path, result_path), 0)
            value = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "complete")
            self.assertEqual(value["presentation"]["visible_text"], "Matchup 1")
            self.assertTrue(output.is_file())

    def test_worker_failure_is_sanitized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path, result_path = root / "input.json", root / "result.json"
            input_path.write_text("{}", encoding="utf-8")
            self.assertEqual(run(input_path, result_path), 1)
            value = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "failed")
            self.assertNotIn(str(root), json.dumps(value))

    def test_parent_accepts_only_complete_bounded_output_and_cleans_ipc(self):
        class Process:
            returncode = 0
            pid = 12_345

            def __init__(self, command, **_kwargs):
                self.polls = 0
                result = Path(command[command.index("--result") + 1])
                result.write_text(json.dumps({
                    "status": "complete", "presentation": {"visible_text": "Matchup 1"},
                }), encoding="utf-8")

            def poll(self):
                self.polls += 1
                return None if self.polls == 1 else 0

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / ".mobile.partial.png"
            with patch("src.core.inspection.live_capture_process.subprocess.Popen", Process), \
                    patch("src.core.inspection.live_capture_process._tree_rss", return_value=(10, 20, 3)):
                value = capture_page_isolated(
                    "http://127.0.0.1:8767", self.request(), output,
                )
            self.assertEqual(value["visible_text"], "Matchup 1")
            self.assertEqual(value["capture_process"]["worker_pid"], 12_345)
            self.assertEqual(value["capture_process"]["browser_process_peak"], 3)
            self.assertFalse(any(Path(folder).glob("*.capture-*.json")))

    def test_parent_fails_closed_on_missing_child_result(self):
        class Process:
            returncode = 0
            pid = 12_345

            def __init__(self, *_args, **_kwargs):
                pass

            def poll(self):
                return 0

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / ".mobile.partial.png"
            with patch("src.core.inspection.live_capture_process.subprocess.Popen", Process):
                with self.assertRaisesRegex(RuntimeError, "exited unsuccessfully"):
                    capture_page_isolated(
                        "http://127.0.0.1:8767", self.request(), output,
                    )
            self.assertFalse(any(Path(folder).glob("*.capture-*.json")))


if __name__ == "__main__":
    unittest.main()
