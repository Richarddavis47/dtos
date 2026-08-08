"""Regression contracts for durable Asset Market restart validation."""
from __future__ import annotations

import json
import unittest
from collections import deque
from unittest.mock import patch

from tools.validation.linux_market_cgroup_gate import (
    _identity,
    _normalized_headers,
    _restart_reuse,
)


DETAIL = "Asset Market generation is building safely in the background; retry shortly."


def _published(generation: str = "market-2") -> dict[str, object]:
    return {
        "application_version": "1.8.6", "application_build": 1806,
        "market_schema_version": "1.0", "league_id": "league-1",
        "historical_dataset_version": "history-1",
        "market_generation": generation, "brain_generation": "brain-1",
        "valuation_generation": "valuation-1", "assets": [],
    }


def _response(
    status: int, payload: dict[str, object], profile: dict[str, object],
    *, client_ms: float = 2.0, server_ms: float = 1.0,
):
    headers = {"retry-after": "5"} if status == 503 else {}
    return status, json.dumps(payload, separators=(",", ":")).encode(), headers, client_ms, server_ms, profile


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class RestartReuseValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = _published()
        self.body = json.dumps(self.payload, separators=(",", ":")).encode()
        self.identity = _identity(self.payload)
        self.warming_profile = {
            "market_construction_total": 0, "market_object_build_total": 0,
            "artifact_load_total": 0, "market_build_phase": "loading_artifact",
            "market_last_error": None,
        }
        self.ready_profile = {
            **self.warming_profile, "artifact_load_total": 1,
            "market_build_phase": "ready",
        }

    @staticmethod
    def _request(responses):
        queue = deque(responses)
        return lambda _path: queue.popleft()

    @staticmethod
    def _probe():
        return 200, b"{}", 1.0, 0.5

    @staticmethod
    def _load():
        return 0.25, 0.5, 0.75

    @staticmethod
    def _memory():
        return 1_073_741_824

    def test_successful_artifact_loading(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        result = _restart_reuse(
            self.identity, self.body, request=request, sleeper=lambda _seconds: None,
            event_probe=self._probe, load_observer=self._load,
            memory_observer=self._memory,
        )
        self.assertEqual(result["warming_attempts"], 1)
        self.assertEqual(result["artifact_loads"], 1)
        self.assertEqual(result["market_constructions"], 0)

    def test_timeout(self) -> None:
        clock = _Clock()
        response = _response(503, {"detail": DETAIL}, self.warming_profile)
        with self.assertRaisesRegex(AssertionError, "exceeded 60 seconds"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                clock=clock, sleeper=clock.sleep, event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_incompatible_artifact_identity(self) -> None:
        incompatible = _published("other-generation")
        response = _response(200, incompatible, self.ready_profile)
        with self.assertRaisesRegex(AssertionError, "identity mismatch"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_accidental_rebuild(self) -> None:
        profile = {**self.warming_profile, "market_construction_total": 1}
        response = _response(503, {"detail": DETAIL}, profile)
        with self.assertRaisesRegex(AssertionError, "reconstruction"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_load_failure(self) -> None:
        profile = {**self.warming_profile, "market_last_error": "invalid artifact"}
        response = _response(503, {"detail": DETAIL}, profile)
        with self.assertRaisesRegex(AssertionError, "load failed"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_injected_load_observer_supports_platform_without_getloadavg(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        with patch.object(
            __import__("os"), "getloadavg", side_effect=AssertionError("unavailable"),
            create=True,
        ):
            result = _restart_reuse(
                self.identity, self.body, request=request,
                sleeper=lambda _seconds: None, event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )
        self.assertEqual(result["warming_samples"][0]["runner_load"], [0.25, 0.5, 0.75])
        self.assertEqual(
            result["warming_samples"][0]["cgroup_memory_current"],
            1_073_741_824,
        )

    def test_injected_memory_observer_avoids_host_cgroup_access(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        with patch(
            "tools.validation.linux_market_cgroup_gate._cgroup",
            side_effect=AssertionError("host cgroup unavailable"),
        ):
            result = _restart_reuse(
                self.identity, self.body, request=request,
                sleeper=lambda _seconds: None, event_probe=self._probe,
                load_observer=self._load, memory_observer=self._memory,
            )
        self.assertEqual(
            result["warming_samples"][0]["cgroup_memory_current"],
            1_073_741_824,
        )

    def test_retry_header_normalization_is_case_insensitive(self) -> None:
        self.assertEqual(
            _normalized_headers([("rEtRy-AfTeR", "5")])["retry-after"], "5",
        )

    def test_duplicate_or_conflicting_retry_headers_fail(self) -> None:
        for values in (("5", "5"), ("5", "10")):
            with self.subTest(values=values):
                with self.assertRaisesRegex(AssertionError, "duplicate"):
                    _normalized_headers([
                        ("Retry-After", values[0]), ("retry-after", values[1]),
                    ])


if __name__ == "__main__":
    unittest.main()
