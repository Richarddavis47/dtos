"""Native free-page maintenance must not execute on request/event-loop threads."""
import asyncio
import threading
import unittest
from unittest.mock import patch

from src.platform import memory_reclamation as module


class MemoryReclamationTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_backlog_drains_off_loop_with_capacity_bound_and_yields(self):
        for available, capacity, expected_calls in ((89, 512, 90), (89, 4, 4), (0, 512, 1)):
            with self.subTest(available=available, capacity=capacity):
                state = {"requests": 0, "remaining": available}
                threads, loop_observations = [], []
                loop = asyncio.get_running_loop()
                completed = asyncio.Event()

                def expire():
                    threads.append(threading.get_ident())
                    loop.call_soon_threadsafe(loop_observations.append, len(threads))
                    state["remaining"] -= 1
                    return state["remaining"] >= 0

                def release():
                    loop.call_soon_threadsafe(completed.set)

                with patch.object(module, "release_unused_allocator_pages", release):
                    task = asyncio.create_task(module.maintain_unused_memory(
                        lambda: state["requests"], lambda: True, interval=.01,
                        expire_one=expire, expiry_limit=capacity,
                    ))
                    try:
                        await asyncio.sleep(.02)
                        state["requests"] = 1
                        await asyncio.wait_for(completed.wait(), 3)
                        self.assertEqual(len(threads), expected_calls)
                        self.assertTrue(all(value != threading.get_ident() for value in threads))
                        self.assertEqual(loop_observations, list(range(1, expected_calls + 1)))
                        await asyncio.sleep(.03)
                        self.assertEqual(len(threads), expected_calls)
                    finally:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)

    def tearDown(self):
        module._native_trim.cache_clear()

    def test_windows_and_unavailable_native_api_are_safe_noops(self):
        for platform, failure in (("win32", None), ("linux", OSError)):
            module._native_trim.cache_clear()
            with patch.object(module.sys, "platform", platform), patch("ctypes.CDLL", side_effect=failure) as library:
                self.assertFalse(module.release_unused_allocator_pages())
                if platform == "win32":
                    library.assert_not_called()

    def test_native_release_preserves_live_objects(self):
        live = {"league": "fixture", "values": [1, 2, 3]}
        with patch.object(module, "_native_trim") as native:
            native.return_value.return_value = 1
            self.assertTrue(module.release_unused_allocator_pages())
            native.return_value.assert_called_once_with(0)
        self.assertEqual(live, {"league": "fixture", "values": [1, 2, 3]})

    async def test_bounded_off_loop_work_only_after_ready_request_activity(self):
        state = {"requests": 0, "ready": False}
        threads = []
        idle_threads = []
        expiry_threads = []
        called = asyncio.Event()
        loop = asyncio.get_running_loop()

        def release():
            threads.append(threading.get_ident())
            loop.call_soon_threadsafe(called.set)

        with patch.object(module, "release_unused_allocator_pages", release):
            task = asyncio.create_task(module.maintain_unused_memory(
                lambda: state["requests"], lambda: state["ready"], interval=.01,
                retire_idle=lambda: idle_threads.append(threading.get_ident()),
                expire_one=lambda: expiry_threads.append(threading.get_ident()),
            ))
            try:
                await asyncio.sleep(.03)
                self.assertEqual(threads, [])
                state["requests"] = 1
                await asyncio.sleep(.03)
                self.assertEqual(threads, [])
                state["ready"] = True
                await asyncio.wait_for(called.wait(), 1)
                await asyncio.sleep(.03)
                self.assertEqual(len(threads), 1)
                self.assertEqual(len(idle_threads), 1)
                self.assertEqual(len(expiry_threads), 1)
                self.assertNotEqual(expiry_threads[0], threading.get_ident())
                self.assertNotEqual(idle_threads[0], threading.get_ident())
                self.assertNotEqual(threads[0], threading.get_ident())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(task.cancelled())
