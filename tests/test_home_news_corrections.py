"""Canonical publication, normalization and actual Home HTTP race admission."""

import asyncio
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from routes.home import create_home_router
from services.home_trade_news import build_news, recent_candidates
from src.core.data_platform.provider_activation import (
    refresh_public_market,
    FANTASYCALC_URL,
)
from src.core.valuation import calibration, normalization
from tests import test_home_trade_news as fixtures
from tests.test_provider_activation import FixtureClient, FixtureResponse
from src.ui.home_trade_news import render_news


def published(values=(6300, 4656, 2700)):
    rows = [
        {"player": {"sleeperId": pid, "position": "WR"}, "value": value}
        for pid, value in zip(("13346", "13406"), values[:2])
    ]
    rows.append(
        {
            "player": {
                "sleeperId": "FP_2029_2",
                "position": "PICK",
                "name": "2029 2nd",
            },
            "value": values[2],
        }
    )
    market = asyncio.run(
        refresh_public_market(
            FixtureClient({FANTASYCALC_URL: FixtureResponse(json_value=rows)})
        )
    )
    normalization.prepare_market_normalization(market)
    return market


class HomeNewsCorrectionsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.data = fixtures.fixture(self.now)
        self.data["transactions"] = [fixtures.trade(self.now)]
        self.data["market_data"] = published()
        self.now = datetime.now(timezone.utc)

    def read(self):
        rows, limits = recent_candidates(self.data, now=self.now)
        return build_news(self.data, rows, limits, now=self.now)

    def test_real_publisher_interrupted_consumer_never_mixes_1138_1125(self):
        self.assertEqual(self.read()["cards"][0]["combined_total"], 1138)
        market = self.data["market_data"]
        original = calibration.normalize_cached_value
        refreshed = [False]

        def change_after_first_value(*args, **kwargs):
            result = original(*args, **kwargs)
            if not refreshed[0]:
                refreshed[0] = True
                market["providers"]["FantasyCalc"]["13346"]["value"] = 6000
                market["providers"]["FantasyCalc"]["13406"]["value"] = 4800
                normalization.prepare_market_normalization(market)
            return result

        with patch.object(
            calibration, "normalize_cached_value", change_after_first_value
        ):
            card = self.read()["cards"][0]
        self.assertIn(card["combined_total"], (1138, 1125, None))
        self.assertNotEqual(card["combined_total"], 1150)
        self.assertEqual(self.read()["cards"][0]["combined_total"], 1125)

    def test_http_refresh_during_read_cache_uses_captured_publication(self):
        app = FastAPI()
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=lambda title, body: HTMLResponse(body),
            )
        )
        original = calibration.normalize_cached_value
        new = published((6000, 4800, 2700))
        # Independent wall time at the real Home route, after source retrieval.
        changed = [False]

        def replace(*args, **kwargs):
            result = original(*args, **kwargs)
            if not changed[0]:
                changed[0] = True
                self.data["market_data"] = new
            return result

        with patch.object(calibration, "normalize_cached_value", replace):
            response = TestClient(app).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("received 100 more current Market", response.text)
        self.assertIn("received 88 more current Market", response.text)
        next_read = TestClient(app).get("/")
        self.assertIn("received 125 more current Market", next_read.text)
        self.assertNotEqual(response.text, next_read.text)

    def test_normalization_replaces_rows_atomically_without_touching_old_snapshot(self):
        market = self.data["market_data"]
        old_providers, old_picks = market["providers"], market["pick_quotes"]
        retained = copy.deepcopy(market)
        blocked, resume = Event(), Event()
        original = normalization.normalize_value

        def pause(*args, **kwargs):
            if not blocked.is_set():
                blocked.set()
                self.assertTrue(resume.wait(5))
            return original(*args, **kwargs)

        with patch.object(normalization, "normalize_value", pause):
            worker = Thread(
                target=normalization.prepare_market_normalization, args=(market,)
            )
            worker.start()
            try:
                self.assertTrue(blocked.wait(5))
                self.assertEqual(market, retained)
                self.assertEqual(self.read()["cards"][0]["combined_total"], 1138)
            finally:
                resume.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertIsNot(market["providers"], old_providers)
        self.assertIsNot(market["pick_quotes"], old_picks)
        self.assertEqual(old_providers, retained["providers"])
        self.assertEqual(old_picks, retained["pick_quotes"])

    def test_failed_normalization_keeps_all_original_references(self):
        before = copy.deepcopy(self.data["market_data"])
        original = normalization.normalize_value
        calls = [0]

        def fail(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise ValueError("interrupted preparation")
            return original(*args, **kwargs)

        with (
            patch.object(normalization, "normalize_value", fail),
            self.assertRaises(ValueError),
        ):
            normalization.prepare_market_normalization(self.data["market_data"])
        self.assertEqual(self.data["market_data"], before)
        self.assertEqual(self.read()["cards"][0]["combined_total"], 1138)

    def test_failed_provider_refresh_retains_prices_and_qualification(self):
        retained = copy.deepcopy(self.data["market_data"])
        retained["provider_status"]["FantasyCalc"]["last_refresh"] = (
            "2026-01-01T00:00:00+00:00"
        )
        untouched = copy.deepcopy(retained)
        failed = asyncio.run(refresh_public_market(FixtureClient({}), retained))
        normalization.prepare_market_normalization(failed)
        self.assertEqual(retained, untouched)
        self.data["market_data"] = failed
        card = self.read()["cards"][0]
        self.assertEqual(card["combined_total"], 1138)
        html = render_news(self.read())
        self.assertIn("Retained fallback", html)
        self.assertIn("cached_fallback", html)
        self.assertIn("Source observation", html)
        self.assertIn("Retrieval", html)

    def test_material_freshness_and_pick_fallback_survive_adapter(self):
        market = self.data["market_data"]
        market["provider_status"]["FantasyCalc"]["refresh_result"] = "cached_fallback"
        market["providers"]["FantasyCalc"]["13346"]["source_updated_at"] = (
            "2026-10-01T00:00:00+00:00"
        )
        card = self.read()["cards"][0]
        self.assertTrue(card["price_qualifications"])
        html = render_news(self.read())
        self.assertIn("Retained fallback", html)
        self.assertIn("2026-10-01", html)
        self.assertIn("Freshness", html)
        pick = next(
            a for s in card["sides"] for a in s["received"] if a["kind"] == "pick"
        )
        self.assertTrue(any("fallback" in q.lower() for q in pick["qualifications"]))

    def test_actual_eleven_asset_source_complete_preview_and_faab(self):
        source = json.loads(
            (
                Path(__file__).parent / "fixtures/home_news_recent_trades.json"
            ).read_text()
        )
        raw = source["transactions"][0]
        self.assertEqual(raw["transaction_id"], "1415021723840966656")
        self.data["transactions"] = [raw]
        self.data["teams"] += [
            {
                "roster_id": n,
                "team_name": f"Source roster {n}",
                "players": [],
                "picks_owned": [],
            }
            for n in range(4, 11)
        ]
        now = datetime.fromtimestamp(raw["status_updated"] / 1000, timezone.utc)
        rows, limits = recent_candidates(self.data, now=now)
        result = build_news(self.data, rows, limits, now=now)
        card = result["cards"][0]
        self.assertEqual(card["asset_count"], 11)
        html = render_news(result)
        self.assertIn("Complete Assets · 11 items", html)
        self.assertIn("news-complete-assets", html)
        for s in card["sides"]:
            for a in s["received"]:
                self.assertIn(a["identity"], html)
        self.assertEqual(
            sum(a["kind"] == "pick" for s in card["sides"] for a in s["received"]), 6
        )

    def test_six_card_sorting_never_uses_interrupted_total_or_league_context(self):
        self.data["transactions"] = [
            fixtures.trade(self.now, str(n), hours=n + 1) for n in range(9)
        ]
        old = self.read()
        self.assertEqual(len(old["cards"]), 6)
        self.assertTrue(all(c["combined_total"] == 1138 for c in old["cards"]))
        self.data["market_data"] = published((6000, 4800, 2700))
        self.now = datetime.now(timezone.utc)
        new = self.read()
        self.assertTrue(all(c["combined_total"] == 1125 for c in new["cards"]))
        self.assertEqual(
            [c["id"] for c in old["cards"]], [c["id"] for c in new["cards"]]
        )
        self.data["market_data"]["providers"]["FantasyCalc"]["13346"]["format"] = "1qb"
        unavailable = self.read()
        self.assertTrue(all(c["combined_total"] is None for c in unavailable["cards"]))
        self.assertNotIn("news-bar", render_news(unavailable))

    def test_unstable_capture_withholds_comparison_and_recovers(self):
        from services import home_trade_news as news

        captured = copy.deepcopy(self.data["market_data"])
        with patch.object(
            news, "capture_market_publication", return_value=(captured, False)
        ):
            card = self.read()["cards"][0]
        self.assertFalse(card["complete"])
        self.assertIsNone(card["combined_total"])
        self.assertTrue(
            all(s["total"] is None and s["known_total"] is None for s in card["sides"])
        )
        self.assertTrue(
            all(
                a["value"] is not None
                for side in card["sides"]
                for a in side["received"]
            )
        )
        self.assertEqual(self.read()["cards"][0]["combined_total"], 1138)

    def test_concurrent_source_change_cannot_overwrite_new_publication(self):
        market = self.data["market_data"]
        original = normalization.normalize_value
        changed = [False]

        def change(*args, **kwargs):
            result = original(*args, **kwargs)
            if not changed[0]:
                changed[0] = True
                market["providers"]["FantasyCalc"]["13406"]["value"] = 4800
            return result

        with (
            patch.object(normalization, "normalize_value", change),
            self.assertRaisesRegex(ValueError, "changed before"),
        ):
            normalization.prepare_market_normalization(market)
        self.assertEqual(market["providers"]["FantasyCalc"]["13406"]["value"], 4800)
        self.assertFalse(self.read()["cards"][0]["complete"])
        normalization.prepare_market_normalization(market)
        self.assertEqual(self.read()["cards"][0]["combined_total"], 1150)
        # 1150 is permitted ONLY after a completed supported 525/400/225
        # publication, never as an interrupted mixture of the old/new fixtures.
