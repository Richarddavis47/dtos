"""Native free-page maintenance must not execute on request/event-loop threads."""
import asyncio
import threading
import unittest
from unittest.mock import patch

from src.platform import memory_reclamation as module


class MemoryReclamationTests(unittest.IsolatedAsyncioTestCase):
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
        called = asyncio.Event()
        loop = asyncio.get_running_loop()

        def release():
            threads.append(threading.get_ident())
            loop.call_soon_threadsafe(called.set)

        with patch.object(module, "release_unused_allocator_pages", release):
            task = asyncio.create_task(module.maintain_unused_memory(
                lambda: state["requests"], lambda: state["ready"], interval=.01,
                retire_idle=lambda: idle_threads.append(threading.get_ident()),
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
                self.assertNotEqual(idle_threads[0], threading.get_ident())
                self.assertNotEqual(threads[0], threading.get_ident())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(task.cancelled())
