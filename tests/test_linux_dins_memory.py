"""Fail-closed DINS resource accounting independent of Linux test availability."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.validation import linux_dins_memory_gate as gate


class LinuxDinsMemoryTests(unittest.TestCase):
    def test_diagnostic_records_lengths_without_sensitive_payload(self):
        def _capture_page():
            dom = {"secret": "must never be serialized"}
            counts = gate.capture_object_counts()
            self.assertEqual(len(dom), counts["_capture_page.dom"]["length"])
            return counts
        counts = _capture_page()
        self.assertNotIn("secret", json.dumps(counts))
        self.assertNotIn("serialized", json.dumps(counts))

    def test_failed_contract_evidence_is_bounded_and_has_no_query_or_credentials(self):
        manifest = {"interaction_failures": [{"starting_page": "/fixture?token=secret",
                    "target": "https://user:password@example.org/missing?token=secret#private",
                    "http_status": 403, "action": "sensitive text"}] * 101}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "contract.json"
            gate.persist_contract_evidence(manifest, output)
            raw = output.read_text()
        result = json.loads(raw)
        self.assertEqual(result["failure_counts"]["interaction_failures"], 101)
        self.assertEqual(len(result["interaction_failures"]), 100)
        self.assertTrue(result["interaction_details_truncated"])
        self.assertEqual(result["interaction_failures"][0]["target_host"], "example.org")
        for forbidden in ("secret", "password", "sensitive text", "private"):
            self.assertNotIn(forbidden, raw)

    def test_initial_fois_completion_is_not_a_settled_history_boundary(self):
        tasks = {"fois_generation": "complete", "live_visual_capture": "complete",
                 "historical_market_resolution": "waiting"}
        self.assertFalse(gate.startup_settled(tasks))
        tasks["historical_market_resolution"] = "complete"
        tasks["fois_generation"] = "running"
        self.assertFalse(gate.startup_settled(tasks))
        tasks["fois_generation"] = "complete"
        self.assertTrue(gate.startup_settled(tasks))

    def test_dins_does_not_enable_a_second_capture_flight_with_string_zero(self):
        environment = {"DTOS_LIVE_VISUAL_CAPTURE": "0", "DTOS_CACHE_FILE": "fixture.json"}
        with patch.object(gate.subprocess, "Popen") as spawn:
            gate.production_server(["python", "dtos_app:app"], env=environment)
        self.assertNotIn("DTOS_LIVE_VISUAL_CAPTURE", spawn.call_args.kwargs["env"])
        self.assertEqual(spawn.call_args.kwargs["env"]["DTOS_CACHE_FILE"], "fixture.json")
        self.assertEqual(environment["DTOS_LIVE_VISUAL_CAPTURE"], "0")

    def test_real_application_inventory_excludes_profiler_control_endpoints(self):
        command = ["python", "-m", "uvicorn", "tools.validation.market_profile_app:app", "--workers", "1"]
        actual = gate.production_server_command(command)
        self.assertEqual(actual[3], "dtos_app:app")
        self.assertEqual(actual[:3], command[:3])
        self.assertEqual(actual[4:], command[4:])
        self.assertIn("tools.validation.market_profile_app:app", command)

    def test_exact_reserve_passes_and_one_byte_less_fails(self):
        sample = {"effective_working_set_bytes": 2 * 1024**3 - 500 * 1024**2,
                  "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0}}
        gate.enforce_memory(sample)
        sample["effective_working_set_bytes"] += 1
        with self.assertRaisesRegex(AssertionError, "500 MiB"):
            gate.enforce_memory(sample)

    def test_oom_cannot_be_hidden_by_subsequent_memory_recovery(self):
        for event in ("oom", "oom_kill", "oom_group_kill"):
            with self.subTest(event=event), self.assertRaisesRegex(AssertionError, "OOM"):
                gate.enforce_memory({"effective_working_set_bytes": 100,
                                     "memory_events": {event: 1}})

    def test_missing_cgroup_fields_fail_closed(self):
        for stats in ({}, {"anon": 1, "file": 1}, {"inactive_file": 1, "file": 1}):
            with patch.object(gate.lifecycle, "_cgroup_values", return_value=stats):
                with self.assertRaisesRegex(RuntimeError, "accounting"):
                    gate.memory_sample()

    def test_production_baseline_is_not_lowered_to_fit_capture(self):
        self.assertEqual(gate.PRODUCTION_BASELINE, 1_241_243_648)
        self.assertEqual(gate.RESERVE, 500 * 1024**2)


if __name__ == "__main__":
    unittest.main()
