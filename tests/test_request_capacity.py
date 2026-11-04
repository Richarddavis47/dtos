from __future__ import annotations

import unittest

from src.platform.request_capacity import request_active, serving_request


class RequestCapacityTests(unittest.TestCase):
    def test_request_signal_is_nested_and_released(self):
        self.assertFalse(request_active())
        with serving_request():
            self.assertTrue(request_active())
            with serving_request():
                self.assertTrue(request_active())
            self.assertTrue(request_active())
        self.assertFalse(request_active())
