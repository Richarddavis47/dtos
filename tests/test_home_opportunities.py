"""Existing discovery -> bounded read -> actual authenticated HTTP presentation."""

from copy import deepcopy
import json
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.responses import HTMLResponse
from routes.home import create_home_router
from services import home_trade_opportunities as ideas
from services.trade_intelligence import evaluate_trade_request
from tests import test_trade_workspace_batch1 as boundary


def supported_row(
    data, sent="1-QB-0", receive="2-QB-0", label="WORTH PURSUING", partner=2
):
    # Actual asset producer/evaluator, with explicitly controlled assessment
    # admission facts for positive UI states. Not a real-league recommendation.
    row = evaluate_trade_request(
        data,
        {
            "active_roster_id": 1,
            "partner_roster_id": partner,
            "assets_sent": [sent],
            "assets_received": [receive],
            "workflow": "recommended",
        },
    )
    e = row["evaluation"]
    e.update(
        legal=True,
        recommendation=label,
        generated_trade_eligible=label in ("WORTH PURSUING", "SMASH ACCEPT"),
        dominant_reason="Supported legal-lineup upgrade.",
        major_drawback="Costs future flexibility.",
    )
    e["legality"] = {"execution_status": "NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER"}
    e["market_evidence"] = {"availability": "full"}
    e["recommendation_trace"] = {"rule_reasons": []}
    e["dimensions"].update(
        confidence={"assessment": "HIGH"},
        counterparty_plausibility={"assessment": "PLAUSIBLE"},
        strategic_fit={
            side: {
                "projection_coverage_complete": True,
                "production_evidence": {"mean_weekly_delta": 1},
            }
            for side in ("active", "partner")
        },
    )
    row["family_id"] = sent + receive
    return row


class HomeOpportunityTests(unittest.TestCase):
    def setUp(self):
        self.f = boundary.AuthenticatedTradeBoundaryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.client, self.data = self.f.client, self.f.data
        with ideas._lock:
            ideas._entries.clear()
        self.client.app.include_router(
            create_home_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: self.data,
                page=lambda title, body: HTMLResponse(body),
            )
        )
        self.meta = self.client.get(
            "/api/trades/home-opportunities?front_office=1"
        ).json()
        self.payload = {
            "workflow": "recommended",
            "active_roster_id": 1,
            "partner_roster_id": 0,
            "workspace_context": self.meta["workspace_context"],
        }

    def publish(self, rows=None, exploratory=None, **extra):
        result = {
            "workflow": "recommended",
            "results": rows or [],
            "exploratory_results": exploratory or [],
            "result_state": "COMPLETE",
            "quiet_state": "No supported alternative in this bounded search.",
        }
        with patch(
            "routes.trades.generate_trade_workflow", return_value=result
        ) as producer:
            r = self.client.post(
                "/api/trades/generate",
                json={**self.payload, **extra},
                headers={"X-CSRF-Token": self.f.csrf},
            )
        self.assertEqual(r.status_code, 200, r.text)
        producer.assert_called_once()
        return self.client.get("/api/trades/home-opportunities?front_office=1").json()

    def test_navigation_never_discovers_and_actual_producer_empty_is_retained(self):
        with patch(
            "routes.trades.generate_trade_workflow",
            side_effect=AssertionError("hidden discovery"),
        ):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(
                self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                    "state"
                ],
                "NOT SEARCHED",
            )
        r = self.client.post(
            "/api/trades/generate",
            json=self.payload,
            headers={"X-CSRF-Token": self.f.csrf},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "retained"
            ]
        )

    def test_recommended_and_unfavorable_exploratory_keep_labels(self):
        row = supported_row(self.data)
        bad = supported_row(self.data, "1-RB-2", "3-RB-2", "NOT WORTH IT", 3)
        result = self.publish([row], [bad])
        self.assertEqual(result["count"], 2)
        self.assertIn("RECOMMENDED TRADE", result["html"])
        self.assertIn("not endorsed", result["html"])
        self.assertIn("NOT WORTH IT", result["html"])
        self.assertIn("Costs future flexibility", result["html"])
        self.assertIn("You send:", result["html"])
        self.assertIn("You receive:", result["html"])

    def test_invalid_missing_and_protected_never_padded(self):
        good = supported_row(self.data)
        invalid = deepcopy(good)
        invalid["evaluation"]["legal"] = False
        missing = deepcopy(good)
        missing["evaluation"]["market_evidence"]["availability"] = "partial"
        self.assertEqual(self.publish([invalid, missing])["count"], 0)
        result = self.publish([good], protected_assets=["1-QB-0"])
        self.assertEqual(result["count"], 0)
        guarded = self.client.get(
            "/api/trades/home-opportunities",
            params={"front_office": 1, "protected": json.dumps(["1-QB-0"])},
        ).json()
        self.assertEqual(guarded["count"], 0)

    def test_cap_families_no_padding_and_exact_acquired_pick(self):
        rows = [
            supported_row(self.data, f"1-{pos}-{i}", f"2-{pos}-{i}")
            for i, pos in enumerate(("QB", "QB", "RB", "RB", "RB", "WR"))
        ]
        rows.append(deepcopy(rows[0]))
        result = self.publish(rows)
        self.assertEqual(result["count"], 4)
        self.assertIn("Show more opportunities", result["html"])
        self.assertEqual(self.publish([rows[0], deepcopy(rows[0])])["count"], 1)
        acquired = self.data["teams"][1]["picks_owned"].pop(0)
        acquired["current_owner_id"] = 1
        self.data["teams"][0]["picks_owned"].append(acquired)
        from services.trade_intelligence import build_trade_workspace

        workspace = build_trade_workspace(self.data, 1)
        pick = next(
            a
            for a in workspace["pools"][1]
            if a.kind == "pick" and a.original_roster_id == 2
        )
        from datetime import datetime, timezone
        from src.core.valuation.config import NORMALIZATION_VERSION

        self.data["market_data"]["pick_quotes"] = {
            "FantasyCalc": [
                {
                    "provider": "FantasyCalc",
                    "market_format": "fc:12:2qb:ppr",
                    "year": 2027,
                    "round": 1,
                    "pick_type": "generic_round",
                    "availability": "current",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "value": 2400,
                    "confidence": 80,
                    "normalization_reference": {
                        "provider": "FantasyCalc",
                        "raw_value": 2400,
                        "normalized_value": 200,
                        "version": NORMALIZATION_VERSION,
                        "generation": "pick-fixture",
                        "method": "provider_range_linear",
                    },
                }
            ]
        }
        row = supported_row(self.data, pick.asset_id)
        result = self.publish([row])
        self.assertEqual(result["count"], 1)
        import re

        token = re.search(r"home_offer=([a-f0-9]+)", result["html"])[1]
        cached = self.client.get(
            "/api/trades/home-opportunities", params={"front_office": 1, "offer": token}
        ).json()
        self.assertEqual(cached["proposal"]["assets_sent"], [pick.asset_id])
        self.assertEqual(
            cached["proposal_presentation"]["send"][0]["original_franchise"], 2
        )

    def test_source_changes_not_offer_identity_invalidate(self):
        first = supported_row(self.data)
        second = supported_row(self.data, "1-RB-2", "2-RB-2")
        result = self.publish([first, second])
        self.assertEqual(result["count"], 2)
        source = result["source_identity"]
        self.data["market_data"]["retrieved_at"] = "another retrieval only"
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "source_identity"
            ],
            source,
        )
        self.data["market_data"]["providers"]["FantasyCalc"]["1-QB-0"]["value"] += 1
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "count"
            ],
            0,
        )
        self.publish([first])
        self.data["teams"][0]["players"].pop()
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "count"
            ],
            0,
        )

    def test_scope_authorization_tokens_generation_and_bounds(self):
        result = self.publish([supported_row(self.data)])
        import re

        row = {"home_offer": re.search(r"home_offer=([a-f0-9]+)", result["html"])[1]}
        self.assertEqual(
            self.client.get(
                "/api/trades/home-opportunities",
                params={"front_office": 1, "offer": row["home_offer"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=2").json()[
                "workspace_context"
            ]["roster_id"],
            1,
        )
        self.assertEqual(
            self.client.get(
                "/api/trades/home-opportunities?front_office=1&offer=foreign"
            ).status_code,
            410,
        )
        self.assertEqual(
            self.client.get(
                "/api/trades/home-opportunities?front_office=1&protected={}"
            ).status_code,
            422,
        )
        self.data["league"]["league_id"] = "foreign"
        self.assertEqual(
            self.client.get(
                "/api/trades/home-opportunities?front_office=1"
            ).status_code,
            422,
        )
        self.data["league"]["league_id"] = "league-1"
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "count"
            ],
            result["count"],
        )
        for i in range(30):
            ideas.publish(
                ("other-binding" + str(i), "source", "", (), ()),
                {"results": []},
                self.payload,
            )
        self.assertLessEqual(ideas.health()["entries"], 24)
        self.assertLessEqual(ideas.health()["bytes"], 2097152)

    def test_projection_strategy_and_cross_league_invalidation(self):
        from types import SimpleNamespace

        snapshot = {"league_id": "league-1", "projection_snapshot_id": "one"}
        reader = SimpleNamespace(snapshot=lambda: snapshot)
        with patch(
            "services.trade_intelligence._trade_projection_service", return_value=reader
        ):
            key = ideas.cache_key(self.data, 1, "")
            snapshot["projection_snapshot_id"] = "two"
            self.assertNotEqual(ideas.cache_key(self.data, 1, ""), key)
            snapshot["projection_snapshot_id"] = "one"
            self.assertEqual(ideas.cache_key(self.data, 1, ""), key)
            self.assertNotEqual(ideas.cache_key(self.data, 1, "REBUILD"), key)
        self.publish([supported_row(self.data)])
        old = self.client.get("/api/trades/home-opportunities?front_office=1").json()
        self.f.store.upsert_membership(
            self.f.account_id,
            {"league_id": "league-2", "season": "2026", "name": "Separate"},
            "fixture-user",
            1,
            "Separate Franchise",
            "active",
        )
        self.f.store.activate(self.f.account_id, "league-2")
        self.data["league"]["league_id"] = "league-2"
        new = self.client.get("/api/trades/home-opportunities?front_office=1").json()
        self.assertEqual(new["count"], 0)
        self.assertNotEqual(
            old["workspace_context"]["binding"], new["workspace_context"]["binding"]
        )
        self.f.store.activate(self.f.account_id, "league-1")
        self.data["league"]["league_id"] = "league-1"
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "count"
            ],
            1,
        )

    def test_interrupted_publication_never_publishes_a_home_offer(self):
        row = supported_row(self.data)

        def changed(*args):
            self.data["market_data"]["providers"]["FantasyCalc"]["1-QB-0"]["value"] += 1
            return {"results": [row], "result_state": "COMPLETE"}

        with patch("routes.trades.generate_trade_workflow", side_effect=changed):
            r = self.client.post(
                "/api/trades/generate",
                json=self.payload,
                headers={"X-CSRF-Token": self.f.csrf},
            )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "canonical_evidence_changed")
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "count"
            ],
            0,
        )

    def test_publication_between_capture_and_key_cannot_relabel_old_offer(self):
        from src.core.valuation import normalization

        row = supported_row(self.data)
        original = normalization.capture_market_publication
        changed = [False]

        def refresh_after_capture(market):
            result = original(market)
            if not changed[0]:
                changed[0] = True
                self.data["market_data"]["providers"]["FantasyCalc"]["1-QB-0"][
                    "value"
                ] += 1
            return result

        with (
            patch.object(
                normalization,
                "capture_market_publication",
                side_effect=refresh_after_capture,
            ),
            patch(
                "routes.trades.generate_trade_workflow",
                return_value={"results": [row], "result_state": "COMPLETE"},
            ),
        ):
            response = self.client.post(
                "/api/trades/generate",
                json=self.payload,
                headers={"X-CSRF-Token": self.f.csrf},
            )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            response.json()["detail"]["code"], "canonical_evidence_changed"
        )
        self.assertEqual(
            self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                "count"
            ],
            0,
        )

    def test_ttl_busy_slot_and_bounded_performance(self):
        from time import perf_counter
        from statistics import median
        from pathlib import Path

        with ideas.search_slot("first"):
            with self.assertRaisesRegex(ValueError, "still completing"):
                with ideas.search_slot("second"):
                    pass
        self.publish([supported_row(self.data)])
        with patch("services.home_trade_opportunities.monotonic", return_value=10**12):
            self.assertEqual(ideas.health()["entries"], 0)
        timings = {}
        for name, url in [
            ("home", "/"),
            ("cached_opportunities", "/api/trades/home-opportunities?front_office=1"),
        ]:
            values = []
            for _ in range(21):
                started = perf_counter()
                self.assertEqual(self.client.get(url).status_code, 200)
                values.append((perf_counter() - started) * 1000)
            timings[name] = {
                "first_ms": values[0],
                "warm_median_ms": median(values[1:]),
            }
        started = perf_counter()
        response = self.client.post(
            "/api/trades/generate",
            json=self.payload,
            headers={"X-CSRF-Token": self.f.csrf},
        )
        self.assertEqual(response.status_code, 200, response.text)
        timings["actual_bounded_discovery"] = {
            "ms": (perf_counter() - started) * 1000,
            "count": response.json()["count"],
            "coverage": "controlled fixture with unavailable canonical projections; not a live cold-search SLA",
        }
        folder = Path(".validation/home-opportunities")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "service-performance.json").write_text(json.dumps(timings, indent=2))

    def test_no_durable_growth_repeat_and_home_order(self):
        self.publish([supported_row(self.data)])
        from pathlib import Path
        from hashlib import sha256

        def hashes():
            return {
                str(p): sha256(p.read_bytes()).hexdigest()
                for p in Path(self.f.folder.name).rglob("*")
                if p.is_file()
            }

        self.client.get("/")
        self.client.get("/api/trades/home-opportunities?front_office=1")
        before = hashes()
        for _ in range(20):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(
                self.client.get("/api/trades/home-opportunities?front_office=1").json()[
                    "count"
                ],
                1,
            )
        self.assertEqual(hashes(), before)
        html = self.client.get("/").text
        self.assertLess(html.index("Open My Team"), html.index("League Trade News"))
        self.assertLess(
            html.index("League Trade News"), html.index('id="home-opportunities"')
        )


if __name__ == "__main__":
    unittest.main()
