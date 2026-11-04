import unittest
from unittest.mock import patch
from src.platform.fois_admission import require_fois_headroom, FOISMemoryDeferred
from src.platform.lifecycle import LifecycleCoordinator
from src.core.fois import process_execution


class FOISMemoryAdmissionTests(unittest.TestCase):
    def test_raw_pressure_never_discounts_file_cache_or_host_memory(self):
        for used in [2147483648 - 32768, 1600 * 1024**2]:
            with (
                self.subTest(used=used),
                patch(
                    "src.platform.fois_admission.memory_snapshot",
                    return_value={
                        "cgroup_limit_bytes": 2147483648,
                        "cgroup_current_bytes": used,
                        "cgroup_inactive_file_bytes": used,
                        "system_available_bytes": 100 * 1024**3,
                    },
                ),
            ):
                with self.assertRaises(FOISMemoryDeferred):
                    require_fois_headroom()

    def test_sufficient_headroom_admits_and_missing_measurement_defers(self):
        with patch(
            "src.platform.fois_admission.memory_snapshot",
            return_value={
                "cgroup_limit_bytes": 2147483648,
                "cgroup_current_bytes": 512 * 1024**2,
            },
        ):
            require_fois_headroom()
        with patch("src.platform.fois_admission.memory_snapshot", return_value={}):
            with self.assertRaises(FOISMemoryDeferred):
                require_fois_headroom()

    def test_deferral_precedes_executor_creation(self):
        with (
            patch("src.platform.fois_admission.memory_snapshot", return_value={}),
            patch.object(process_execution, "_executor") as executor,
        ):
            with self.assertRaises(FOISMemoryDeferred):
                process_execution._submit(lambda: None)
            executor.assert_not_called()

    def test_sync_never_waits_on_event_loop_for_active_fois(self):
        coordinator = LifecycleCoordinator()
        coordinator.reserve_fois_generation()
        with self.assertRaisesRegex(RuntimeError, "deferred"):
            with coordinator.phase("sleeper_sync"):
                pass
        coordinator.release_fois_generation()
        with coordinator.phase("sleeper_sync"):
            pass

    def test_sync_and_fois_reservation_do_not_overlap(self):
        import threading

        coordinator = LifecycleCoordinator()
        entered = threading.Event()

        def reserve():
            coordinator.reserve_fois_generation()
            entered.set()
            coordinator.release_fois_generation()

        with coordinator.phase("sleeper_sync"):
            thread = threading.Thread(target=reserve)
            thread.start()
            self.assertFalse(entered.wait(0.05))
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(entered.is_set())


class FOISForcedRetirementTests(unittest.TestCase):
    def test_sync_can_reap_idle_worker_without_waiting_retention(self):
        import asyncio
        import psutil
        from src.core.fois.process_execution import (
            warm_fois_executor,
            retire_idle_fois_executor_sync,
            shutdown_fois_executor_sync,
        )

        worker = asyncio.run(warm_fois_executor())["pid"]
        try:
            self.assertTrue(retire_idle_fois_executor_sync(force=True))
            self.assertFalse(psutil.pid_exists(worker))
        finally:
            shutdown_fois_executor_sync()
