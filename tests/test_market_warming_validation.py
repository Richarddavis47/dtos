"""Canonical HTTP validation for the bounded Asset Market warming lifecycle."""
from __future__ import annotations

import json
import unittest
from collections import defaultdict, deque
from unittest.mock import patch

from tools.validation.smoke_http import (
    MARKET_WARMING_DETAIL,
    get,
    get_market_page,
    validate_asset_market_contract,
)


def _response(status: int, payload: object, *, elapsed: float = 0.1):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    headers = {"Retry-After": "5"} if status == 503 else {}
    return status, body, headers, elapsed


def _warming_health(
    *, error: str | None = None, build_active: bool = True,
    phase: str = "asset_market_build", build_count: int = 0,
    startup_state: str = "complete", startup_reason: str = "Canonical state ready.",
) -> dict:
    return {
        "status": "warming",
        "cache": {
            "build_active": build_active,
            "build_count": build_count,
            "last_error": error,
            "market_generation": None,
            "lifecycle": {
                "phase": phase,
                "market_build_allowed": startup_state == "complete" and phase not in {
                    "sleeper_sync", "provider_network", "valuation_intelligence",
                    "cache_persistence", "historical_import",
                },
                "startup_fence": {
                    "state": startup_state, "reason": startup_reason,
                },
            },
        },
    }


def _ready_health(*, build_count: int = 1) -> dict:
    return {
        "status": "ready",
        "cache": {
            "build_active": False, "build_count": build_count,
            "last_valid_model": True,
            "last_error": None, "market_generation": "generation-1",
            "lifecycle": {"phase": "idle", "market_build_allowed": True},
        },
    }


def _market_page(dataset: str = "generation-1") -> bytes:
    return (
        '<header data-dtos-component="page-header"><h1>Asset Market</h1>'
        '<a class="ds-action primary">Sync</a></header>'
        '<h2>Know the market.</h2>'
        '<form aria-label="Asset Market filters"></form>'
        '<table><caption>Canonical dynasty asset rankings</caption></table>'
        '<p>Values remain separate; unavailable evidence is never substituted.</p>'
        f'<p>Dataset <code>{dataset}</code></p>'
    ).encode()


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class _Requests:
    def __init__(self, **responses) -> None:
        self.responses = defaultdict(deque)
        for path, values in responses.items():
            self.responses[path.replace("_", "/")].extend(values)

    def __call__(self, _base_url: str, path: str):
        queue = self.responses[path]
        if not queue:
            raise AssertionError(f"unexpected request: {path}")
        if len(queue) == 1:
            return queue[0]
        return queue.popleft()


class MarketWarmingValidationTests(unittest.TestCase):
    def test_valid_warming_response_eventually_requires_page_contract(self) -> None:
        request = _Requests(**{
            "_market": [
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(200, _market_page()),
            ],
            "_api_market_health": [_response(200, _warming_health())],
        })
        clock = _Clock()
        body = get_market_page(
            "http://dtos", "/market", request=request, sleeper=clock.sleep, clock=clock,
        )
        self.assertEqual(validate_asset_market_contract(body, "/market"), "generation-1")

    def test_warming_exceeding_deadline_fails(self) -> None:
        request = _Requests(**{
            "_market": [_response(503, {"detail": MARKET_WARMING_DETAIL})],
            "_api_market_health": [_response(200, _warming_health())],
        })
        clock = _Clock()
        with patch("tools.validation.smoke_http.MARKET_WARMING_DEADLINE_SECONDS", 1.0):
            with self.assertRaisesRegex(AssertionError, "exceeded 60s"):
                get_market_page(
                    "http://dtos", "/market", request=request,
                    sleeper=clock.sleep, clock=clock,
                )

    def test_market_build_failure_during_polling_fails_immediately(self) -> None:
        request = _Requests(**{
            "_market": [_response(503, {"detail": MARKET_WARMING_DETAIL})],
            "_api_market_health": [
                _response(200, _warming_health(error="memory safety refusal")),
            ],
        })
        with self.assertRaisesRegex(AssertionError, "build failed"):
            get_market_page("http://dtos", "/market", request=request)

    def test_unrelated_503_is_not_retried(self) -> None:
        request = _Requests(**{
            "_market": [_response(503, {"detail": "Storage unavailable"})],
        })
        with self.assertRaisesRegex(AssertionError, "unrelated or malformed"):
            get_market_page("http://dtos", "/market", request=request)

    def test_malformed_warming_response_is_not_retried(self) -> None:
        request = _Requests(**{"_market": [_response(503, b"not-json")]})
        with self.assertRaisesRegex(AssertionError, "malformed"):
            get_market_page("http://dtos", "/market", request=request)

    def test_readiness_503_uses_strict_non_retrying_get(self) -> None:
        with patch(
            "tools.validation.smoke_http._request",
            return_value=_response(503, {"detail": "Initial sync running"}),
        ):
            with self.assertRaisesRegex(AssertionError, "expected HTTP 200"):
                get("http://dtos", "/health/ready")

    def test_eventual_page_missing_market_contract_fails(self) -> None:
        request = _Requests(**{
            "_market": [
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(200, b"<html>not the market</html>"),
            ],
            "_api_market_health": [_response(200, _warming_health())],
        })
        clock = _Clock()
        body = get_market_page(
            "http://dtos", "/market", request=request, sleeper=clock.sleep, clock=clock,
        )
        with self.assertRaisesRegex(AssertionError, "page header"):
            validate_asset_market_contract(body, "/market")

    def test_registered_lifecycle_blocker_transitions_to_one_build(self) -> None:
        request = _Requests(**{
            "_market": [
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(200, _market_page()),
            ],
            "_api_market_health": [
                _response(200, _warming_health(
                    build_active=False, phase="historical_import", build_count=4,
                )),
                _response(200, _warming_health(
                    build_active=True, phase="asset_market_build", build_count=4,
                )),
                _response(200, _ready_health(build_count=5)),
            ],
        })
        clock = _Clock()
        body = get_market_page(
            "http://dtos", "/market", request=request,
            sleeper=clock.sleep, clock=clock,
        )
        self.assertEqual(validate_asset_market_contract(body, "/market"), "generation-1")

    def test_idle_warming_without_active_build_fails(self) -> None:
        request = _Requests(**{
            "_market": [_response(503, {"detail": MARKET_WARMING_DETAIL})],
            "_api_market_health": [
                _response(200, _warming_health(
                    build_active=False, phase="idle",
                )),
            ],
        })
        with self.assertRaisesRegex(AssertionError, "stale Asset Market warming"):
            get_market_page("http://dtos", "/market", request=request)

    def test_running_startup_fence_is_a_bounded_registered_blocker(self) -> None:
        request = _Requests(**{
            "_market": [
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(200, _market_page()),
            ],
            "_api_market_health": [
                _response(200, _warming_health(
                    build_active=False, phase="idle", startup_state="running",
                    startup_reason="Synchronizing canonical state.",
                )),
                _response(200, _warming_health(
                    build_active=True, phase="asset_market_build",
                )),
                _response(200, _ready_health(build_count=1)),
            ],
        })
        clock = _Clock()
        body = get_market_page(
            "http://dtos", "/market", request=request,
            sleeper=clock.sleep, clock=clock,
        )
        self.assertEqual(validate_asset_market_contract(body, "/market"), "generation-1")

    def test_failed_startup_fence_fails_immediately(self) -> None:
        request = _Requests(**{
            "_market": [_response(503, {"detail": MARKET_WARMING_DETAIL})],
            "_api_market_health": [_response(200, _warming_health(
                build_active=False, phase="idle", startup_state="failed",
                startup_reason="Canonical synchronization failed.",
            ))],
        })
        with self.assertRaisesRegex(AssertionError, "startup fence failed"):
            get_market_page("http://dtos", "/market", request=request)

    def test_market_build_cannot_overlap_registered_blocker(self) -> None:
        request = _Requests(**{
            "_market": [_response(503, {"detail": MARKET_WARMING_DETAIL})],
            "_api_market_health": [
                _response(200, _warming_health(
                    build_active=True, phase="sleeper_sync",
                )),
            ],
        })
        with self.assertRaisesRegex(AssertionError, "overlaps lifecycle blocker"):
            get_market_page("http://dtos", "/market", request=request)

    def test_response_started_before_atomic_publication_accepts_ready_health(self) -> None:
        request = _Requests(**{
            "_market": [
                _response(503, {"detail": MARKET_WARMING_DETAIL}),
                _response(200, _market_page()),
            ],
            "_api_market_health": [_response(200, _ready_health())],
        })
        body = get_market_page("http://dtos", "/market", request=request)
        self.assertEqual(validate_asset_market_contract(body, "/market"), "generation-1")


if __name__ == "__main__":
    unittest.main()
