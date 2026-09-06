"""Fail-closed DINS resource accounting independent of Linux test availability."""
import unittest
from unittest.mock import patch

from tools.validation import linux_dins_memory_gate as gate


class LinuxDinsMemoryTests(unittest.TestCase):
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
