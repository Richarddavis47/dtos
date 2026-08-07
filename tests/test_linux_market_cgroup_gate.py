"""Regression contracts for durable Asset Market restart validation."""
from __future__ import annotations

import json
import unittest
from collections import deque

from tools.validation.linux_market_cgroup_gate import _identity, _restart_reuse


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
    headers = {"Retry-After": "5"} if status == 503 else {}
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

    def test_successful_artifact_loading(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        result = _restart_reuse(
            self.identity, self.body, request=request, sleeper=lambda _seconds: None,
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
                clock=clock, sleeper=clock.sleep,
            )

    def test_incompatible_artifact_identity(self) -> None:
        incompatible = _published("other-generation")
        response = _response(200, incompatible, self.ready_profile)
        with self.assertRaisesRegex(AssertionError, "identity mismatch"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
            )

    def test_accidental_rebuild(self) -> None:
        profile = {**self.warming_profile, "market_construction_total": 1}
        response = _response(503, {"detail": DETAIL}, profile)
        with self.assertRaisesRegex(AssertionError, "reconstruction"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
            )

    def test_load_failure(self) -> None:
        profile = {**self.warming_profile, "market_last_error": "invalid artifact"}
        response = _response(503, {"detail": DETAIL}, profile)
        with self.assertRaisesRegex(AssertionError, "load failed"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
            )


if __name__ == "__main__":
    unittest.main()
