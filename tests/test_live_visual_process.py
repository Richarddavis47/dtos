from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.core.inspection.live_capture_worker import (
    CAPTURE_PROCESS_NICE_INCREMENT,
    _lower_capture_priority,
    run,
)
from src.core.inspection.live_capture_process import capture_page_isolated
from src.core.inspection.live_capture_process import (
    CAPTURE_PROCESS_CONTINUE_SIGNAL,
    CAPTURE_REQUEST_PAUSE_SECONDS,
    CAPTURE_PROCESS_STOP_SIGNAL,
    _isolate_capture_tree_cpu,
    _lower_tree_priority,
    _partition_request_cpu,
    _restore_request_cpu,
    _yield_capture_cpu,
)
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

    def test_linux_capture_worker_yields_cpu_priority_to_request_server(self):
        with patch("src.core.inspection.live_capture_worker.os.name", "posix"), \
                patch(
                    "src.core.inspection.live_capture_worker.os.nice",
                    side_effect=[0, 19], create=True,
                ) as nice:
            self.assertEqual(_lower_capture_priority(), 19)
        self.assertEqual(nice.call_args_list[0].args, (CAPTURE_PROCESS_NICE_INCREMENT,))
        self.assertEqual(nice.call_args_list[1].args, (0,))

    def test_non_posix_capture_worker_does_not_change_priority(self):
        with patch("src.core.inspection.live_capture_worker.os.name", "nt"), \
                patch("src.core.inspection.live_capture_worker.os.nice", create=True) as nice:
            self.assertIsNone(_lower_capture_priority())
        nice.assert_not_called()

    def test_parent_enforces_priority_across_browser_descendants(self):
        root, browser = unittest.mock.Mock(), unittest.mock.Mock()
        root.children.return_value = [browser]
        root.nice.side_effect = [None, 19]
        browser.nice.side_effect = [None, 19]
        with patch(
            "src.core.inspection.live_capture_process.psutil.Process", return_value=root,
        ):
            self.assertEqual(_lower_tree_priority(12_345), 19)
        root.children.assert_called_once_with(recursive=True)
        root.nice.assert_any_call(19)
        browser.nice.assert_any_call(19)

    def test_linux_parent_confines_browser_tree_to_one_cpu(self):
        root, browser = unittest.mock.Mock(), unittest.mock.Mock()
        root.cpu_affinity.return_value = [2, 4]
        root.children.return_value = [browser]
        with patch("src.core.inspection.live_capture_process.sys.platform", "linux"), \
                patch(
                    "src.core.inspection.live_capture_process.psutil.Process",
                    return_value=root,
                ):
            self.assertEqual(_isolate_capture_tree_cpu(12_345), (2, 1))
        root.cpu_affinity.assert_any_call([4])
        browser.cpu_affinity.assert_called_once_with([4])

    def test_linux_parent_reserves_and_restores_capture_cpu(self):
        parent = unittest.mock.Mock()
        parent.cpu_affinity.return_value = [2, 4]
        with patch("src.core.inspection.live_capture_process.sys.platform", "linux"), \
                patch(
                    "src.core.inspection.live_capture_process.psutil.Process",
                    return_value=parent,
                ):
            self.assertEqual(_partition_request_cpu(), ([2, 4], [4]))
            parent.cpu_affinity.assert_any_call([2])
            _restore_request_cpu([2, 4])
            parent.cpu_affinity.assert_any_call([2, 4])

    def test_non_linux_parent_does_not_change_cpu_affinity(self):
        with patch("src.core.inspection.live_capture_process.sys.platform", "win32"), \
                patch("src.core.inspection.live_capture_process.psutil.Process") as process:
            self.assertIsNone(_isolate_capture_tree_cpu(12_345))
        process.assert_not_called()

    def test_linux_capture_tree_yields_in_bounded_cpu_slices(self):
        process = unittest.mock.Mock(pid=12_345)
        process.poll.return_value = None
        root, browser = unittest.mock.Mock(), unittest.mock.Mock()
        root.children.return_value = [browser]
        with patch("src.core.inspection.live_capture_process.sys.platform", "linux"), \
                patch(
                    "src.core.inspection.live_capture_process.psutil.Process",
                    return_value=root,
                ), \
                patch(
                    "src.core.inspection.live_capture_process.os.killpg",
                    side_effect=OSError, create=True,
                ), \
                patch("src.core.inspection.live_capture_process.time.sleep") as sleep, \
                patch("src.core.inspection.live_capture_process.request_active", return_value=False):
            self.assertTrue(_yield_capture_cpu(process))
        root.children.assert_called_once_with(recursive=True)
        browser.suspend.assert_called_once_with()
        root.suspend.assert_called_once_with()
        root.resume.assert_called_once_with()
        browser.resume.assert_called_once_with()
        self.assertEqual([call.args for call in sleep.call_args_list], [(0.01,), (0.02,)])

    def test_linux_capture_remains_suspended_until_product_request_finishes(self):
        process = unittest.mock.Mock(pid=12_345)
        process.poll.return_value = None
        root = unittest.mock.Mock()
        root.children.return_value = []
        with patch("src.core.inspection.live_capture_process.sys.platform", "linux"), \
                patch("src.core.inspection.live_capture_process.psutil.Process", return_value=root), \
                patch(
                    "src.core.inspection.live_capture_process.os.killpg",
                    side_effect=OSError, create=True,
                ), \
                patch("src.core.inspection.live_capture_process.time.sleep"), \
                patch("src.core.inspection.live_capture_process.request_active", return_value=True), \
                patch(
                    "src.core.inspection.live_capture_process.wait_for_request_idle",
                    return_value=False,
                ) as wait:
            self.assertTrue(_yield_capture_cpu(process))
        wait.assert_called_once_with(0.02)
        self.assertLessEqual(CAPTURE_REQUEST_PAUSE_SECONDS, 0.02)
        root.suspend.assert_called_once_with()
        root.resume.assert_called_once_with()

    def test_linux_capture_atomically_suspends_its_complete_process_group(self):
        process = unittest.mock.Mock(pid=12_345)
        process.poll.return_value = None
        with patch("src.core.inspection.live_capture_process.sys.platform", "linux"), \
                patch("src.core.inspection.live_capture_process.time.sleep"), \
                patch("src.core.inspection.live_capture_process.request_active", return_value=True), \
                patch("src.core.inspection.live_capture_process.wait_for_request_idle"), \
                patch("src.core.inspection.live_capture_process.os.killpg", create=True) as killpg, \
                patch("src.core.inspection.live_capture_process.psutil.Process") as psutil_process:
            self.assertTrue(_yield_capture_cpu(process))
        self.assertEqual(
            [call.args for call in killpg.call_args_list],
            [
                (12_345, CAPTURE_PROCESS_STOP_SIGNAL),
                (12_345, CAPTURE_PROCESS_CONTINUE_SIGNAL),
            ],
        )
        psutil_process.assert_not_called()

    def test_non_linux_capture_tree_uses_ordinary_poll_interval(self):
        process = unittest.mock.Mock(pid=12_345)
        with patch("src.core.inspection.live_capture_process.sys.platform", "win32"), \
                patch("src.core.inspection.live_capture_process.time.sleep") as sleep:
            self.assertFalse(_yield_capture_cpu(process))
        sleep.assert_called_once_with(0.05)

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
                    "process_nice": 19,
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
            self.assertEqual(value["capture_process"]["process_nice"], 19)
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
