"""Fail-closed DINS resource accounting independent of Linux test availability."""
import unittest
from unittest.mock import patch

from tools.validation import linux_dins_memory_gate as gate


class LinuxDinsMemoryTests(unittest.TestCase):
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
