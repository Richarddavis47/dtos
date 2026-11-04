"""Expired disposable graphs must not accumulate across completed page reads."""
import threading
import unittest
import weakref
from unittest.mock import Mock, patch

from src.core.intelligence.cache import IntelligenceCache


class Payload:
    pass


class CacheExpiryTests(unittest.TestCase):
    def test_exact_ttl_boundary_and_one_graph_per_pass(self):
        cache = IntelligenceCache(default_ttl=60)
        with patch("src.core.intelligence.cache.monotonic", return_value=0):
            first = cache.get_or_create("first", Payload)
            second = cache.get_or_create("second", Payload)
            live = cache.get_or_create("live", Payload, ttl=120)
        first_ref, second_ref = weakref.ref(first), weakref.ref(second)
        del first, second
        with patch("src.core.intelligence.cache.monotonic", return_value=59.999):
            self.assertFalse(cache.expire_one())
            self.assertIsNotNone(first_ref())
        with patch("src.core.intelligence.cache.monotonic", return_value=60):
            self.assertTrue(cache.expire_one())
            self.assertIsNone(first_ref())
            self.assertIsNotNone(second_ref())
            self.assertTrue(cache.expire_one())
            self.assertIsNone(second_ref())
            self.assertFalse(cache.expire_one())
            factory = Mock(side_effect=AssertionError("Fresh entry was evicted"))
            self.assertIs(cache.get_or_create("live", factory), live)
            factory.assert_not_called()
        self.assertEqual(cache.default_ttl, 60)
        self.assertEqual(cache.invalidations, 2)

    def test_caller_held_result_survives_and_expired_lookup_rebuilds_normally(self):
        cache = IntelligenceCache(default_ttl=1)
        with patch("src.core.intelligence.cache.monotonic", return_value=0):
            result = cache.get_or_create("key", lambda: {"score": 42})
        with patch("src.core.intelligence.cache.monotonic", return_value=1):
            self.assertTrue(cache.expire_one())
            self.assertEqual(result, {"score": 42})
            factory = Mock(return_value={"score": 42})
            rebuilt = cache.get_or_create("key", factory)
            factory.assert_called_once_with()
            self.assertEqual(result, rebuilt)
            self.assertIsNot(result, rebuilt)

    def test_busy_factory_lock_is_not_waited_on(self):
        cache = IntelligenceCache(default_ttl=0)
        cache.get_or_create("expired", Payload)
        outcomes = []
        with cache._lock:
            worker = threading.Thread(target=lambda: outcomes.append(cache.expire_one()))
            worker.start()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
        self.assertEqual(outcomes, [False])
        self.assertTrue(cache.expire_one())
