from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import _market_query, create_market_router
from src.ui.render_cache import GenerationRenderCache


class GenerationRenderCacheTests(unittest.TestCase):
    def test_exact_bytes_reused_and_generation_isolated(self) -> None:
        cache = GenerationRenderCache("test", max_entries=2, max_bytes=64)
        calls = 0

        def build(value: bytes) -> bytes:
            nonlocal calls
            calls += 1
            return value

        self.assertEqual(cache.get_or_build(("g1",), "g1", lambda: build(b"one")), b"one")
        self.assertEqual(cache.get_or_build(("g1",), "g1", lambda: build(b"bad")), b"one")
        self.assertEqual(cache.get_or_build(("g2",), "g2", lambda: build(b"two")), b"two")
        self.assertEqual(calls, 2)
        self.assertEqual(cache.health()["test_render_cache_hits"], 1)

    def test_singleflight_and_lru_bounds(self) -> None:
        cache = GenerationRenderCache("test", max_entries=2, max_bytes=32)
        gate = threading.Event()
        calls = 0

        def build() -> bytes:
            nonlocal calls
            calls += 1
            gate.wait(1)
            return b"shared"

        results: list[bytes] = []
        threads = [threading.Thread(target=lambda: results.append(
            cache.get_or_build(("same",), "g1", build)
        )) for _ in range(3)]
        for thread in threads:
            thread.start()
        time.sleep(0.02)
        gate.set()
        for thread in threads:
            thread.join(1)
        self.assertEqual(results, [b"shared"] * 3)
        self.assertEqual(calls, 1)
        cache.get_or_build(("two",), "g1", lambda: b"2")
        cache.get_or_build(("three",), "g1", lambda: b"3")
        health = cache.health()
        self.assertEqual(health["test_render_cache_entries"], 2)
        self.assertEqual(health["test_render_cache_evictions"], 1)


class _Market:
    def __init__(self, generation: str = "generation-1") -> None:
        self.semantic_generation = generation
        self.generated_at = generation
        self.dataset_version = "dataset-1"
        self.brain_generation = "brain-1"
        self.data = {"valuation_intelligence": {"generated_at": "valuation-1"}}
        self.directory_calls = 0
        self.assets = []

    def directory(self, **kwargs):
        self.directory_calls += 1
        return {"total": len(self.assets), "assets": self.assets, "variant": kwargs}

    def search(self, _q, _limit):
        self.directory_calls += 1
        return {"count": 0, "results": []}

    def detail(self, _selected, _front_office):
        return None

    def trending(self):
        return {"unavailable_reason": "No observations."}


class _Cache:
    def __init__(self, market: _Market) -> None:
        self.market = market

    def get(self, *_args, **_kwargs):
        return self.market

    def health(self):
        return {"status": "ready"}

    def reconcile(self, *_args):
        return None


class MarketRenderedRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.market = _Market()
        self.cache = _Cache(self.market)
        self.state = {
            "data": {"league": {"name": "Cache League"}},
            "last_sync": "stable-sync", "last_error": None,
        }
        self.home_cache = GenerationRenderCache("home", max_entries=8)
        self.market_cache = GenerationRenderCache("market", max_entries=24)
        self.home_body_cache = GenerationRenderCache("home_body", max_entries=8)
        self.market_body_cache = GenerationRenderCache("market_body", max_entries=24)
        self.patches = (
            patch("routes.market.asset_market_cache", self.cache),
            patch("routes.market.home_render_cache", self.home_cache),
            patch("routes.market.market_render_cache", self.market_cache),
            patch("routes.market.home_body_render_cache", self.home_body_cache),
            patch("routes.market.market_body_render_cache", self.market_body_cache),
        )
        for item in self.patches:
            item.start()
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.state["data"], state=self.state,
            league_id="league-a", page=lambda title, body: HTMLResponse(
                f"{title}|{self.state['last_sync']}|{body}"
            ),
        ))
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        for item in reversed(self.patches):
            item.stop()

    def test_market_has_one_exact_generation_cache(self) -> None:
        market = self.client.get("/market")
        self.assertEqual(market.content, self.client.get("/market").content)
        self.assertEqual(self.market.directory_calls, 1)
        self.assertEqual(self.home_cache.health()["home_render_cache_entries"], 0)
        self.assertEqual(self.market_cache.health()["market_render_cache_hits"], 1)

    def test_query_and_generation_changes_cannot_collide(self) -> None:
        default = self.client.get("/market").content
        filtered = self.client.get("/market?position=QB&sort=intrinsic").content
        self.assertNotEqual(
            self.market_cache.health()["market_render_cache_entries"], 1,
        )
        self.assertNotEqual(default, b"")
        self.assertNotEqual(filtered, b"")
        self.market.semantic_generation = "generation-2"
        self.client.get("/market")
        self.assertEqual(self.market.directory_calls, 3)

    def test_chrome_state_change_invalidates_without_personalization(self) -> None:
        before = self.client.get("/market").content
        self.state["last_sync"] = "new-sync"
        after = self.client.get("/market").content
        self.assertNotEqual(before, after)
        self.assertEqual(self.market.directory_calls, 1)
        self.assertEqual(
            self.market_body_cache.health()["market_body_render_cache_hits"], 1,
        )

    def test_health_exposes_bounded_render_telemetry(self) -> None:
        self.client.get("/market")
        response = self.client.get("/api/market/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["render_caches"]
        self.assertEqual(payload["home"]["home_render_cache_entries"], 0)
        self.assertEqual(payload["market"]["market_render_cache_entries"], 1)
        self.assertEqual(
            payload["home_body"]["home_body_render_cache_entries"], 0,
        )
        self.assertEqual(
            payload["market_body"]["market_body_render_cache_entries"], 1,
        )

    def test_optional_front_office_is_omitted_from_market_query(self) -> None:
        query = _market_query(selected="player:4984", front_office=None)
        self.assertEqual(query, "selected=player%3A4984")
        self.assertNotIn("front_office=", query)

    def test_explicit_front_office_is_preserved_with_selected_asset(self) -> None:
        query = _market_query(selected="player:4984", front_office=2)
        self.assertEqual(query, "selected=player%3A4984&front_office=2")

    def test_market_asset_links_never_emit_empty_front_office(self) -> None:
        self.market.assets = [
            {
                "asset_id": asset_id,
                "display_name": label,
                "asset_type": "player",
                "position": position,
                "nfl_team": "NFL",
                "rank": index,
                "values": {},
                "owner": {},
            }
            for index, (asset_id, label, position) in enumerate((
                ("player:4984", "Josh Allen", "QB"),
                ("player:7564", "Ja'Marr Chase", "WR"),
                ("player:9509", "Bijan Robinson", "RB"),
                ("player:9221", "Jahmyr Gibbs", "RB"),
                ("player:te-1", "Representative Tight End", "TE"),
            ), start=1)
        ]
        response = self.client.get("/market")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("front_office=", response.text)
        for asset_id, _label, _position in (
            ("player:4984", "Josh Allen", "QB"),
            ("player:7564", "Ja'Marr Chase", "WR"),
            ("player:9509", "Bijan Robinson", "RB"),
            ("player:9221", "Jahmyr Gibbs", "RB"),
            ("player:te-1", "Representative Tight End", "TE"),
        ):
            selected = asset_id.replace(":", "%3A")
            self.assertIn(f"selected={selected}", response.text)

    def test_market_filter_form_preserves_only_legitimate_context(self) -> None:
        missing = self.client.get("/market")
        self.assertNotIn('name="front_office"', missing.text)
        selected = self.client.get("/market?front_office=2")
        self.assertIn(
            '<input type="hidden" name="front_office" value="2">',
            selected.text,
        )

    def test_empty_front_office_remains_invalid_at_route_boundary(self) -> None:
        response = self.client.get("/market?front_office=")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
