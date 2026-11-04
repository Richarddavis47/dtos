"""Actual prepared-source, canonical Market, Home and historical route tests."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from services.home_trade_news import (
    recent_candidates,
    build_news,
    completion_clock,
    news_identity,
)
from src.core.valuation.normalization import prepare_market_normalization
from src.core.valuation.calibration import cached_market_facts
from src.ui.home_trade_news import render_news
from routes.home import create_home_router
from routes.historical_assets import create_historical_assets_router
from tests import test_trade_timeline as timeline_fixture

DAY, ARK = timeline_fixture.DAY, timeline_fixture.ARK


def fixture(now=None):
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat()
    data = {
        "league": {"league_id": DAY, "season": "2026", "name": "Day Traders"},
        "week": 6,
        "teams": [
            {
                "roster_id": n,
                "team_name": name,
                "players": [],
                "picks_owned": [],
                "wins": 2,
                "losses": 3,
            }
            for n, name in [
                (1, "Chase Bank"),
                (2, "Week3 is a bigger joke"),
                (3, "Third franchise"),
            ]
        ],
        "players": {
            "13346": {"full_name": "Denzel Boston", "position": "WR"},
            "13406": {"full_name": "De’Zhaun Stribling", "position": "WR"},
        },
        "market_data": {
            "generation": "fixture-shared-publication",
            "generated_at": stamp,
            "providers": {
                "FantasyCalc": {
                    pid: {
                        "value": v,
                        "confidence": 80,
                        "retrieved_at": stamp,
                        "format": "dynasty_2qb",
                    }
                    for pid, v in [("13346", 6000), ("13406", 4500)]
                }
            },
            "pick_quotes": {
                "FantasyCalc": [
                    {
                        "provider": "FantasyCalc",
                        "year": 2029,
                        "round": 2,
                        "pick_type": "generic_round",
                        "market_format": "fc:12:2qb:ppr",
                        "availability": "current",
                        "retrieved_at": stamp,
                        "confidence": 80,
                        "value": 3000,
                    }
                ]
            },
        },
        "transactions": [],
        "season_transactions": {},
    }
    data["teams"][1]["picks_owned"] = [
        {"year": 2029, "round": 2, "original_roster_id": 1, "current_owner_id": 2}
    ]
    prepare_market_normalization(data["market_data"])
    return data


def trade(now, identity="one", hours=1, **fields):
    clock = now - timedelta(hours=hours)
    return {
        "transaction_id": identity,
        "type": "trade",
        "status": "complete",
        "status_updated": int(clock.timestamp() * 1000),
        "created": int((clock - timedelta(minutes=5)).timestamp() * 1000),
        "roster_ids": [1, 2],
        "adds": {"13346": 1, "13406": 2},
        "drops": {"13346": 2, "13406": 1},
        "draft_picks": [
            {
                "season": "2029",
                "round": 2,
                "roster_id": 1,
                "previous_owner_id": 1,
                "owner_id": 2,
            }
        ],
        **fields,
    }


def model(data, now):
    rows, limits = recent_candidates(data, now=now)
    return build_news(data, rows, limits, now=now)


class HomeTradeNewsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.data = fixture(self.now)

    def test_actual_three_team_source_faab_players_and_five_picks(self):
        facts = json.loads(
            (Path(__file__).parent / "fixtures/trade_faab_source.json").read_text()
        )
        raw = next(
            r
            for rows in facts["transactions"].values()
            for r in rows
            if r["transaction_id"] == "965057520920260608"
        )
        now = datetime.fromtimestamp(
            raw["status_updated"] / 1000, timezone.utc
        ) + timedelta(hours=1)
        users = {u["user_id"]: u for u in facts["users"]}
        data = {
            "league": facts["league"],
            "players": facts["player_identities"],
            "transactions": [raw],
            "teams": [
                {
                    "roster_id": r["roster_id"],
                    "team_name": (
                        users.get(r["owner_id"], {}).get("metadata") or {}
                    ).get("team_name")
                    or users.get(r["owner_id"], {}).get("display_name"),
                    "players": [],
                    "picks_owned": [],
                }
                for r in facts["rosters"]
            ],
        }
        card = model(data, now)["cards"][0]
        received = [a for side in card["sides"] for a in side["received"]]
        self.assertEqual(sum(a["kind"] == "player" for a in received), 3)
        self.assertEqual(sum(a["kind"] == "pick" for a in received), 5)
        faab = [a for a in received if a["kind"] == "faab"]
        self.assertEqual(len(faab), 1)
        self.assertEqual(
            (faab[0]["source_id"], faab[0]["destination_id"], faab[0]["label"]),
            ("3", "6", "100 FAAB"),
        )
        self.assertIsNone(card["combined_total"])
        self.assertEqual(len(card["sides"]), 3)
        rendered = render_news(model(data, now))
        self.assertIn("Complete Assets · 9 items", rendered)
        self.assertEqual(rendered.count('data-news-asset="faab:3:6:100.0"'), 1)
        self.assertNotIn('class="news-bar"', rendered)

    def test_completion_only_supported_clock_and_168_hour_boundary(self):
        cases = [
            ({}, True),
            ({"status": "pending"}, False),
            ({"type": "waiver"}, False),
            ({"status_updated": None}, False),
            ({"created": None, "status_updated": None}, False),
            ({"status_updated": "bad"}, False),
            (
                {
                    "status_updated": int(
                        (self.now + timedelta(seconds=1)).timestamp() * 1000
                    )
                },
                False,
            ),
            ({"league_id": ARK}, False),
            ({"status_updated": 0}, False),
        ]
        for changes, admitted in cases:
            self.data["transactions"] = [trade(self.now, **changes)]
            self.assertEqual(
                bool(model(self.data, self.now)["cards"]), admitted, changes
            )
        self.data["transactions"] = [
            trade(self.now, "boundary", hours=168),
            trade(self.now, "inside", hours=168 - 1 / 3600),
        ]
        self.assertEqual(
            [c["id"] for c in model(self.data, self.now)["cards"]], ["inside"]
        )
        self.assertIsNone(
            completion_clock(
                trade(
                    self.now,
                    status_updated="2026-01-01",
                    created="2026-02-01T00:00:00Z",
                ),
                self.now,
            )[0]
        )

    def test_completion_clock_compares_subsecond_instants_numerically(self):
        base = int((self.now - timedelta(hours=1)).timestamp() * 1000)
        for created, updated, accepted in [
            (base, base + 100, True),
            (base + 100, base, False),
            (base, base, True),
        ]:
            self.data["transactions"] = [
                trade(self.now, created=created, status_updated=updated)
            ]
            result = model(self.data, self.now)
            self.assertEqual(bool(result["cards"]), accepted)

    def test_current_batch_prices_exact_direction_and_shared_reference(self):
        self.data["transactions"] = [trade(self.now)]
        card = model(self.data, self.now)["cards"][0]
        self.assertTrue(card["complete"])
        side = {s["roster_id"]: s for s in card["sides"]}
        self.assertEqual(side["1"]["received"][0]["label"], "Denzel Boston")
        self.assertEqual(
            [a["identity"] for a in side["2"]["received"]],
            ["player:13406", "PICK-2029-R2-ORIG1"],
        )
        facts = cached_market_facts(self.data["market_data"], ["13346", "13406"])
        self.assertEqual(side["1"]["total"], facts["13346"].value)
        self.assertEqual(side["2"]["total"], facts["13406"].value + 250)
        text = render_news(model(self.data, self.now), viewer=1)
        self.assertIn("Current values, not trade-date grades.", text)
        self.assertIn("received 125 more current Market points", text)
        self.assertNotIn('<details class="news-evaluation" open', text)
        self.assertNotIn("guaranteed winner", text)

    def test_six_cap_ties_unique_assets_partial_preserved_not_zero(self):
        self.data["transactions"] = [
            trade(self.now, str(n), hours=n + 1) for n in range(8)
        ]
        self.data["transactions"].append(
            trade(
                self.now,
                "partial",
                adds={"missing": 1},
                drops={"missing": 2},
                draft_picks=[],
            )
        )
        m = model(self.data, self.now)
        self.assertEqual(len(m["cards"]), 6)
        self.assertEqual(
            [c["id"] for c in m["cards"]], ["0", "1", "2", "3", "4", "partial"]
        )
        partial = m["cards"][-1]
        self.assertIsNone(partial["combined_total"])
        self.assertIsNone(partial["sides"][0]["total"])
        self.assertIsNone(partial["sides"][0]["received"][0]["value"])
        self.data["season_transactions"] = {
            "5": self.data["transactions"],
            "6": self.data["transactions"],
        }
        self.assertEqual(model(self.data, self.now)["eligible_count"], 9)
        self.data["transactions"][0]["draft_picks"] *= 2
        self.assertEqual(
            len(model(self.data, self.now)["cards"][0]["sides"][1]["received"]), 2
        )

    def test_exact_pick_current_range_contract_and_warm_home_no_growth(self):
        self.data["transactions"] = [trade(self.now)]
        pick = self.data["teams"][1]["picks_owned"][0]
        pick["range_evidence"] = {
            "league_id": DAY,
            "original_roster_id": 1,
            "year": 2029,
            "reference": "prepared-supported-interval",
            "generation": "source-range-1",
            "earliest_slot": 1,
            "latest_slot": 2,
            "league_size": 10,
            "draft_order_rules_supported": True,
            "data_complete": True,
            "concept": "draft_order_interval",
            "season_stage": "postseason",
        }
        quote = copy.deepcopy(self.data["market_data"]["pick_quotes"]["FantasyCalc"][0])
        quote.update(pick_type="projected_range", range="EARLY", value=4800)
        self.data["market_data"]["pick_quotes"]["FantasyCalc"].append(quote)
        prepare_market_normalization(self.data["market_data"])
        card = model(self.data, self.now)["cards"][0]
        self.assertEqual(card["sides"][1]["received"][1]["value"], 400)
        self.assertTrue(card["complete"])
        from config import METADATA_DATABASE_FILE

        root = Path(METADATA_DATABASE_FILE).parent
        app = FastAPI()
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=lambda t, b: HTMLResponse(b),
            )
        )
        client = TestClient(app)
        self.assertEqual(client.get("/").status_code, 200)

        def files():
            return {
                str(p): (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in root.rglob("*")
                if p.is_file()
            }

        before = files()
        for _ in range(10):
            self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(files(), before)

    def test_warm_home_pick_quote_expiry_inside_same_minute(self):
        self.now = self.now.replace(second=0)
        self.data = fixture(self.now)
        self.data["transactions"] = [trade(self.now)]
        quote = self.data["market_data"]["pick_quotes"]["FantasyCalc"][0]
        quote["retrieved_at"] = (
            self.now - timedelta(hours=48) + timedelta(seconds=10)
        ).isoformat()
        app = FastAPI()
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=lambda t, b: HTMLResponse(b),
            )
        )
        client = TestClient(app)
        with patch("routes.home.datetime") as clock:
            clock.now.return_value = self.now + timedelta(seconds=9)
            self.assertIn('class="news-bar"', client.get("/").text)
            clock.now.return_value = self.now + timedelta(seconds=11)
            html = client.get("/").text
            self.assertNotIn('class="news-bar"', html)
            self.assertIn("Market advantage unavailable", html)

    def test_value_order_and_stable_identity_tie(self):
        self.data["transactions"] = [
            trade(self.now, "z"),
            trade(self.now, "a"),
            trade(self.now, "small", draft_picks=[]),
        ]
        self.assertEqual(
            [c["id"] for c in model(self.data, self.now)["cards"]], ["a", "z", "small"]
        )

    def test_incompatible_normalization_context_withholds_totals_not_values(self):
        self.data["transactions"] = [trade(self.now)]
        self.data["market_data"]["pick_quotes"]["FantasyCalc"][0][
            "normalization_reference"
        ]["generation"] = "foreign-population"
        m = model(self.data, self.now)
        card = m["cards"][0]
        self.assertFalse(card["complete"])
        self.assertIsNone(card["combined_total"])
        self.assertEqual(card["sides"][1]["received"][1]["value"], 250)
        html = render_news(m)
        self.assertNotIn('class="news-bar"', html)
        self.assertIn("Market advantage unavailable", html)
        self.data["market_data"]["providers"]["FantasyCalc"]["13346"]["format"] = (
            "redraft"
        )
        self.assertIsNone(
            model(self.data, self.now)["cards"][0]["sides"][0]["received"][0]["value"]
        )

    def test_genuine_zero_prices_and_directed_multi_party_faab_once(self):
        self.data["transactions"] = [
            trade(
                self.now,
                roster_ids=[1, 2, 3],
                waiver_budget=[{"sender": 3, "receiver": 1, "amount": 100}] * 2
                + [{"sender": 2, "receiver": 3, "amount": 0}],
            )
        ]
        m = model(self.data, self.now)
        self.assertEqual(len(m["cards"][0]["sides"]), 3)
        html = render_news(m)
        self.assertEqual(
            html.count("100 FAAB"), 2
        )  # Received row + disclosed cost; single directed consideration.
        self.assertEqual(
            sum(
                a["kind"] == "faab"
                for s in m["cards"][0]["sides"]
                for a in s["received"]
            ),
            2,
        )
        self.assertNotIn('class="news-bar"', html)
        self.assertIn("0 FAAB", html)
        for row in self.data["market_data"]["providers"]["FantasyCalc"].values():
            row["value"] = 0
        self.data["transactions"] = [trade(self.now, draft_picks=[])]
        prepare_market_normalization(self.data["market_data"])
        c = model(self.data, self.now)["cards"][0]
        self.assertTrue(c["complete"])
        self.assertEqual(c["combined_total"], 0)

    def test_warm_home_expiry_new_source_publication_quiet_and_league_isolation(self):
        self.data["transactions"] = [
            trade(self.now, "expires", hours=167),
            trade(self.now, "stays"),
        ]
        app = FastAPI()
        app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=lambda t, b: HTMLResponse(b),
            )
        )
        client = TestClient(app)
        with patch("routes.home.datetime") as clock:
            clock.now.return_value = self.now
            first = client.get("/").text
            self.assertIn('data-news-trade="expires"', first)
            clock.now.return_value = self.now + timedelta(hours=1)
            second = client.get("/").text
            self.assertNotIn('data-news-trade="expires"', second)
            self.assertIn('data-news-trade="stays"', second)
            self.data["transactions"].append(trade(self.now, "new"))
            self.assertIn('data-news-trade="new"', client.get("/").text)
            self.data["league"]["league_id"] = ARK
            self.data["transactions"] = []
            self.assertIn("No completed league trades", client.get("/").text)
            self.data["league"]["league_id"] = DAY
            self.data["transactions"] = [trade(self.now)]
            self.assertIn('data-news-trade="one"', client.get("/").text)
        self.assertLess(first.index("League Trade News"), first.index("<h2>Standings"))

    def test_missing_bucket_independent_trade_and_freshness_identity(self):
        self.data["transactions"] = [trade(self.now)]
        self.data["season_transactions"] = {"5": None, "6": []}
        before = news_identity(
            self.data, recent_candidates(self.data, now=self.now)[0], self.now
        )
        m = model(self.data, self.now)
        self.assertEqual(m["eligible_count"], 1)
        self.assertIn("unavailable", " ".join(m["limitations"]))
        self.data["market_data"]["generation"] = "new"
        after = news_identity(
            self.data, recent_candidates(self.data, now=self.now)[0], self.now
        )
        self.assertNotEqual(before, after)

    def test_real_boston_source_and_canonical_publisher_historical_home_return_no_growth(
        self,
    ):
        f = timeline_fixture.TradeTimelineTests()
        f.setUp()
        self.addCleanup(f.tearDown)
        f.load()
        data = f.data[DAY]
        source = next(
            t
            for bucket in f.sources[0]["transactions"].values()
            for t in bucket
            if t["transaction_id"] == "1414718106177122304"
        )
        now = datetime.fromtimestamp(
            source["status_updated"] / 1000, timezone.utc
        ) + timedelta(hours=1)
        data["transactions"] = [copy.deepcopy(source)]
        data["season_transactions"] = {"6": [copy.deepcopy(source)]}
        f.store.update_current(DAY, data)
        news = model(data, now)
        card = news["cards"][0]
        recipients = {
            a["destination_id"]: a["label"]
            for s in card["sides"]
            for a in s["received"]
            if a["kind"] == "player"
        }
        self.assertIn("Boston", " ".join(recipients.values()))
        boston = next(
            a
            for s in card["sides"]
            for a in s["received"]
            if a.get("player_id") == "13346"
        )
        self.assertEqual(boston["destination_id"], "1")
        app = FastAPI()
        app.include_router(
            create_historical_assets_router(
                league_id=DAY,
                require_data=lambda: data,
                page=lambda t, b: HTMLResponse(b),
            )
        )

        def files():
            return {
                str(p): (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in Path(f.temp.name).rglob("*")
                if p.is_file()
            }

        with (
            patch("routes.historical_assets.historical_store", f.store),
            patch(
                "src.core.intelligence_memory.intelligence_checkpoint_store", f.memory
            ),
        ):
            client = TestClient(app)
            response = client.get("/trades/history/1414718106177122304?from_home=1")
            self.assertEqual(response.status_code, 200)
            self.assertIn('href="/">← Back to Home', response.text)
            before = files()
            for _ in range(10):
                self.assertEqual(
                    client.get(
                        "/trades/history/1414718106177122304?from_home=1"
                    ).status_code,
                    200,
                )
                model(data, now)
            self.assertEqual(files(), before)
