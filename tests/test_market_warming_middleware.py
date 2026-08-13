"""Early Asset Market warming response contract."""
from __future__ import annotations

import threading
import unittest

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.platform.market_warming import (
    MARKET_WARMING_DETAIL,
    AssetMarketWarmingMiddleware,
)
from src.platform.observability import install_observability


class _Cache:
    def __init__(self, *, warming: bool = True) -> None:
        self.warming = warming
        self.calls = 0
        self.starts = 0
        self.lock = threading.Lock()

    def begin_warming_guard(self, *_args, start_background: bool = True) -> bool:
        with self.lock:
            self.calls += 1
        return self.warming

    def reconcile(self, *_args) -> bool:
        with self.lock:
            if self.warming and self.starts == 0:
                self.starts += 1
                return True
        return False


def _app(cache: _Cache) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        AssetMarketWarmingMiddleware,
        cache=cache, data_provider=lambda: {"cached": True}, state={},
        store=object(), league_id="league",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )
    install_observability(app)

    @app.api_route("/", methods=["GET", "HEAD", "POST"])
    @app.api_route("/market", methods=["GET", "HEAD", "POST"])
    @app.api_route("/api/market/assets", methods=["GET", "HEAD", "POST"])
    async def directory(limit: int = Query(50, ge=1)):
        return {"status": "ready", "limit": limit}

    @app.get("/api/market/assets/player:10213")
    @app.get("/api/market/search")
    @app.get("/api/market/health")
    async def unrelated():
        return {"status": "normal"}

    @app.get("/failed")
    async def failed():
        raise HTTPException(503, "market build failed")

    return app


class MarketWarmingMiddlewareTests(unittest.TestCase):
    def test_worker_is_scheduled_only_after_response_body_is_sent(self) -> None:
        cache = _Cache()
        app = _app(cache)
        events: list[str] = []
        original_reconcile = cache.reconcile

        def reconcile(*args) -> bool:
            events.append("worker")
            return original_reconcile(*args)

        cache.reconcile = reconcile  # type: ignore[method-assign]

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.body":
                events.append("body")

        import asyncio
        asyncio.run(app(
            {
                "type": "http", "asgi": {"version": "3.0"},
                "http_version": "1.1", "method": "GET", "scheme": "http",
                "path": "/api/market/assets", "raw_path": b"/api/market/assets",
                "query_string": b"limit=50", "root_path": "",
                "headers": [], "client": ("test", 1), "server": ("test", 80),
            },
            receive,
            send,
        ))
        self.assertEqual(events[-1], "worker")
        self.assertGreaterEqual(events.count("body"), 1)
        self.assertNotIn("worker", events[:-1])

    def test_exact_get_and_head_paths_return_compact_contract(self) -> None:
        cache = _Cache()
        client = TestClient(_app(cache))
        for path in ("/", "/market?sort=value", "/api/market/assets?limit=50"):
            response = client.get(path, headers={
                "Origin": "https://public.example", "X-Request-ID": "request-1",
                "X-DTOS-Diagnostics": "1",
            })
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": MARKET_WARMING_DETAIL})
            self.assertEqual(response.headers["retry-after"], "5")
            self.assertEqual(response.headers["access-control-allow-origin"], "*")
            self.assertEqual(response.headers["x-request-id"], "request-1")
            self.assertIn("x-dtos-request-duration", response.headers)
        head = client.head("/api/market/assets")
        self.assertEqual(head.status_code, 503)
        self.assertEqual(head.content, b"")

    def test_details_search_health_and_mutations_are_not_intercepted(self) -> None:
        cache = _Cache()
        client = TestClient(_app(cache))
        for path in (
            "/api/market/assets/player:10213", "/api/market/search",
            "/api/market/health",
        ):
            self.assertEqual(client.get(path).json(), {"status": "normal"})
        self.assertEqual(client.post("/market").status_code, 200)
        self.assertEqual(cache.calls, 0)

    def test_explicit_secondary_league_bypasses_default_market_guard(self) -> None:
        cache = _Cache()
        client = TestClient(_app(cache))
        response = client.get("/api/market/assets?league_id=secondary&limit=7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["limit"], 7)
        self.assertEqual(cache.calls, 0)

    def test_ready_generation_uses_normal_query_validation(self) -> None:
        cache = _Cache(warming=False)
        client = TestClient(_app(cache))
        self.assertEqual(client.get("/api/market/assets?limit=7").json()["limit"], 7)
        self.assertEqual(client.get("/api/market/assets?limit=bad").status_code, 422)

    def test_worker_failure_passes_through_instead_of_becoming_warming(self) -> None:
        cache = _Cache(warming=False)
        client = TestClient(_app(cache))
        response = client.get("/api/market/assets?limit=bad")
        self.assertEqual(response.status_code, 422)
        self.assertNotEqual(response.json().get("detail"), MARKET_WARMING_DETAIL)

    def test_concurrent_cold_requests_observe_one_single_flight_start(self) -> None:
        cache = _Cache()
        client = TestClient(_app(cache))
        statuses: list[int] = []

        def request() -> None:
            statuses.append(client.get("/api/market/assets").status_code)

        requests = [threading.Thread(target=request) for _ in range(12)]
        for thread in requests:
            thread.start()
        for thread in requests:
            thread.join()
        self.assertEqual(statuses, [503] * 12)
        self.assertEqual(cache.starts, 1)


if __name__ == "__main__":
    unittest.main()
