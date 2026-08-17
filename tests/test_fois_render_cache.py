from __future__ import annotations

import threading
import unittest

from src.core.fois.render_cache import FOISRenderCache


class FOISRenderCacheTests(unittest.TestCase):
    def test_miss_hit_and_byte_equivalence(self) -> None:
        cache = FOISRenderCache()
        calls = []
        first = cache.get_or_build(("league-a", "current", "g1"), "g1", lambda: calls.append(1) or b"page")
        second = cache.get_or_build(("league-a", "current", "g1"), "g1", lambda: b"wrong")
        self.assertEqual(first, second)
        self.assertEqual(calls, [1])
        self.assertEqual(cache.health()["fois_render_cache_hits"], 1)
        self.assertEqual(cache.health()["fois_render_cache_misses"], 1)

    def test_generation_model_league_and_view_are_isolated_by_key(self) -> None:
        cache = FOISRenderCache()
        keys = (
            ("league-a", "current", "g1", "4.0"),
            ("league-a", "current", "g2", "4.0"),
            ("league-a", "current", "g2", "5.0"),
            ("league-b", "current", "g2", "5.0"),
            ("league-b", "history", "g2", "5.0"),
        )
        for index, key in enumerate(keys):
            self.assertEqual(
                cache.get_or_build(key, str(key[2]), lambda index=index: str(index).encode()),
                str(index).encode(),
            )
        self.assertEqual(cache.health()["fois_render_cache_misses"], len(keys))

    def test_singleflight_builds_once(self) -> None:
        cache = FOISRenderCache()
        entered = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def builder() -> bytes:
            calls.append(1)
            entered.set()
            release.wait(1)
            return b"complete"

        threads = [threading.Thread(
            target=lambda: results.append(cache.get_or_build("key", "g", builder)),
        ) for _ in range(2)]
        for thread in threads:
            thread.start()
        self.assertTrue(entered.wait(1))
        release.set()
        for thread in threads:
            thread.join(1)
        self.assertEqual(calls, [1])
        self.assertEqual(results, [b"complete", b"complete"])
        self.assertEqual(cache.health()["fois_render_singleflight_waiters"], 1)

    def test_failed_build_is_not_published(self) -> None:
        cache = FOISRenderCache()
        with self.assertRaisesRegex(RuntimeError, "broken"):
            cache.get_or_build("key", "g", lambda: (_ for _ in ()).throw(RuntimeError("broken")))
        self.assertEqual(cache.health()["fois_render_cache_entries"], 0)
        self.assertEqual(cache.get_or_build("key", "g", lambda: b"recovered"), b"recovered")

    def test_size_and_entry_bounds_evict_old_generations(self) -> None:
        cache = FOISRenderCache(max_entries=2, max_bytes=8)
        for generation in ("g1", "g2", "g3"):
            cache.get_or_build(generation, generation, lambda: b"1234")
        health = cache.health()
        self.assertEqual(health["fois_render_cache_entries"], 2)
        self.assertEqual(health["fois_render_cache_bytes"], 8)
        self.assertEqual(health["fois_render_cache_evictions"], 1)

    def test_new_process_cache_starts_cold(self) -> None:
        first = FOISRenderCache()
        first.get_or_build("key", "g", lambda: b"page")
        restarted = FOISRenderCache()
        self.assertEqual(restarted.health()["fois_render_cache_entries"], 0)
        self.assertEqual(restarted.get_or_build("key", "g", lambda: b"page"), b"page")


if __name__ == "__main__":
    unittest.main()
