"""Approved optional contract: pure mathematics and disposable scoped HTTP controls."""

from copy import deepcopy
from contextlib import ExitStack
from itertools import combinations
import json
import random
import unittest
from unittest.mock import patch

from services.personal_rankings import (
    personal_values,
    valuation_method,
    PersonalRankingError,
)
from src.core.accounts.personal_store import (
    ABSOLUTE_METHOD,
    RELATIVE_METHOD,
    load_personal,
    encode_document,
    PersonalDocumentError,
)
from tests import test_personal_rankings as controls


def document(order, method=ABSOLUTE_METHOD):
    return {
        "schema": 2 if method == RELATIVE_METHOD else 1,
        "valuation_method": method,
        "order": list(order),
        "baseline": {"ids": list(order)},
    }


class RelativeNumericalTests(unittest.TestCase):
    def test_all_masks_preserve_old_exact_values_pool_and_monotonic_moves(self):
        order = [f"player:{i}" for i in range(7)]
        for count in range(7):
            for missing in combinations(order, count):
                rows = [
                    {"asset_id": k, "market_value": (0, 37, 37, 400, 600, 900, 1000)[i]}
                    for i, k in enumerate(order)
                    if k not in missing
                ]
                universe = {"rows": rows}
                old = personal_values(document(order), universe)
                doc = document(order, RELATIVE_METHOD)
                before = deepcopy(doc)
                new = personal_values(doc, universe)
                self.assertEqual(doc, before)
                self.assertEqual(set(new["values"]), {r["asset_id"] for r in rows})
                self.assertEqual(
                    sum(new["values"].values()), sum(r["market_value"] for r in rows)
                )
                for key, price in old["values"].items():
                    self.assertEqual(new["values"][key], price)
                for i, key in enumerate(order):
                    if key not in new["values"]:
                        continue
                    for j in range(i):
                        moved = order.copy()
                        moved.remove(key)
                        moved.insert(j, key)
                        after = personal_values(
                            document(moved, RELATIVE_METHOD), universe
                        )
                        self.assertGreaterEqual(
                            after["values"][key], new["values"][key]
                        )
                if not missing:
                    self.assertEqual(old["values"], new["values"])

    def test_missing_crossing_new_unsaved_and_exact_picks(self):
        a, u, b, p, q = (
            "player:a",
            "player:u",
            "player:b",
            "pick:2029:1:4",
            "pick:2029:1:5",
        )
        order = [a, u, p, b, q]
        universe = {
            "rows": [
                {"asset_id": k, "market_value": v}
                for k, v in ((a, 800), (b, 300), (p, 400), (q, 400))
            ]
        }
        values = personal_values(document(order, RELATIVE_METHOD), universe)["values"]
        for moved in ([u, a, p, b, q], [a, p, b, q, u]):
            self.assertEqual(
                personal_values(document(moved, RELATIVE_METHOD), universe)["values"],
                values,
            )
        self.assertNotIn(u, values)
        self.assertEqual(set(values), {a, b, p, q})
        universe["rows"].append({"asset_id": "player:new", "market_value": 1000})
        self.assertEqual(
            personal_values(document(order, RELATIVE_METHOD), universe)["values"],
            values,
        )
        self.assertFalse(
            personal_values(document([a, a], RELATIVE_METHOD), universe)["values"]
        )

    def test_disposable_628_589_39_cohort_and_quote_transitions(self):
        order = [f"player:{i}" for i in range(628)]
        absent = set(order[:38] + [order[515]])
        prices = (
            list(range(999, 523, -1))
            + [37] * 52
            + [36 - i * 35 / 60 for i in range(61)]
        )
        self.assertEqual(len(prices), 589)
        rows = [
            {"asset_id": k, "market_value": v}
            for k, v in zip((k for k in order if k not in absent), prices)
        ]
        u = {"rows": rows}
        old = personal_values(document(order), u)["values"]
        new = personal_values(document(order, RELATIVE_METHOD), u)["values"]
        self.assertEqual(
            (len(order), len(rows), len(absent), len(old), len(new)),
            (628, 589, 39, 12, 589),
        )
        self.assertEqual(sum(prices), sum(new.values()))
        self.assertTrue(all(new[k] == v for k, v in old.items()))
        rng = random.Random(2219)
        rng.shuffle(rows)
        self.assertEqual(
            personal_values(document(order, RELATIVE_METHOD), u)["values"], new
        )
        returned = {"rows": rows + [{"asset_id": order[0], "market_value": 500}]}
        changed = personal_values(document(order, RELATIVE_METHOD), returned)["values"]
        self.assertEqual(len(changed), 590)
        self.assertTrue(any(changed[k] != new[k] for k in new))
        self.assertEqual(
            personal_values(document(order, RELATIVE_METHOD), u)["values"], new
        )

    def test_unsupported_method_versions_fail_closed(self):
        for doc in (
            {"schema": 3},
            {"schema": 2, "valuation_method": "relative-v999"},
            {"schema": 1, "valuation_method": RELATIVE_METHOD},
        ):
            with self.assertRaises(PersonalRankingError):
                valuation_method(doc)


class RelativeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = controls.PersonalRankingsHTTPTests(
            "test_full_seed_matches_market_and_reads_create_no_rows"
        )
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.initialize()
        self.f.post("tiers", asset_id="player:2", tier_start=True)
        self.f.post(
            "preferences", asset_id="pick:2028:1:4", preferences={"protect": True}
        )
        self.f.post("preferences", asset_id="player:2", preferences={"target": True})
        self.f.post("reorder", asset_id="player:3", to_position=1)
        self.f.market.rows[1]["values"]["market_value"] = None
        self.f.market.generation = "Market-partial"

    def saved(self):
        return load_personal(self.f.store, self.f.account, "league-1", 1)

    def preview(self, method=RELATIVE_METHOD):
        r = self.f.post("method_preview", valuation_method=method)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("private", r.headers["cache-control"])
        self.assertIn("no-store", r.headers["cache-control"])
        return r.json()["method_preview"]

    def activate(self, method=RELATIVE_METHOD, preview=None, **extra):
        p = preview or self.preview(method)
        return self.f.post(
            "valuation_method",
            valuation_method=method,
            preview_token=p["preview_token"],
            confirmation="APPLY VALUATION METHOD",
            **extra,
        )

    def test_preview_readonly_optin_reversal_and_all_intent_preserved(self):
        before = self.saved()
        with self.f.store.connect() as c:
            facts = list(c.iterdump())
        p = self.preview()
        self.assertEqual(p["current"]["method"], ABSOLUTE_METHOD)
        self.assertGreater(
            p["proposed"]["personal_value_count"], p["current"]["personal_value_count"]
        )
        self.assertTrue(p["packages"])
        self.assertEqual(p["proposed"]["unpriced_count"], 1)
        with self.f.store.connect() as c:
            self.assertEqual(list(c.iterdump()), facts)
        r = self.activate(preview=p)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["method"], RELATIVE_METHOD)
        after = self.saved()
        for k in ("order", "baseline", "tiers", "preferences", "mode", "created_at"):
            self.assertEqual(after[k], before[k], k)
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertNotIn("market_value", json.dumps(after))
        self.assertNotIn("values", after["method_review"])
        for _ in range(3):
            self.f.state()
        self.assertEqual(self.saved(), after)
        reverse = self.activate(ABSOLUTE_METHOD)
        self.assertEqual(reverse.status_code, 200, reverse.text)
        self.assertEqual(reverse.json()["method"], ABSOLUTE_METHOD)
        self.assertEqual(self.saved()["order"], before["order"])
        from services.personal_rankings import build_universe

        self.assertEqual(
            personal_values(
                before,
                build_universe(
                    self.f.data, self.f.market, requested_ids=before["order"]
                ),
            )["values"],
            personal_values(
                self.saved(),
                build_universe(
                    self.f.data, self.f.market, requested_ids=before["order"]
                ),
            )["values"],
        )

    def test_stale_publication_revision_target_and_session_confirmation_denied(self):
        p = self.preview()
        original = self.saved()
        r = self.f.post(
            "valuation_method",
            valuation_method=RELATIVE_METHOD,
            preview_token=p["preview_token"],
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.saved(), original)
        self.f.market.generation += "-next"
        self.assertEqual(self.activate(preview=p).status_code, 409)
        p = self.preview()
        self.assertEqual(self.activate(ABSOLUTE_METHOD, preview=p).status_code, 409)
        self.f.post("tiers", asset_id="player:3", tier_start=True)
        self.assertEqual(self.activate(preview=p).status_code, 409)
        p = self.preview()
        self.f.use_account("account-b")
        self.f.initialize()
        self.assertEqual(self.activate(preview=p).status_code, 409)
        self.assertEqual(self.f.state()["method"], ABSOLUTE_METHOD)
        self.f.use_account("account-a")
        token, _ = self.f.tokens["account-a"]
        self.f.store.revoke_session(token)
        self.assertEqual(self.f.client.get("/api/my-dtos").status_code, 401)

    def test_publication_change_notice_no_automatic_writes_and_no_heavy_work(self):
        self.assertEqual(self.activate().status_code, 200)
        before = self.saved()
        targets = (
            "services.sleeper.sleeper_get",
            "services.trade_intelligence.generate_trade_workflow",
            "src.core.fois.service.FOISService.generate",
            "services.history.history_records",
            "src.core.trade_intelligence.lineup.optimal_legal_lineup",
            "src.core.asset_market.engine.AssetMarketCache.get",
        )
        with ExitStack() as stack:
            spies = [
                stack.enter_context(patch(t, side_effect=AssertionError(t)))
                for t in targets
            ]
            self.f.market.rows[1]["values"]["market_value"] = 600
            self.f.market.generation += "-returned"
            current = self.f.state()
            self.assertTrue(current["method_review"]["publication_changed"])
            self.assertEqual(current["method_review"]["added_count"], 1)
            self.assertEqual(self.saved(), before)
            p = self.preview()
            self.assertEqual(self.activate(preview=p).status_code, 200)
            self.assertFalse(self.f.state()["method_review"]["publication_changed"])
            for spy in spies:
                spy.assert_not_called()
        doc = deepcopy(self.saved())
        doc["valuation_method"] = "unknown-v9"
        with self.assertRaises(PersonalDocumentError):
            encode_document(
                {
                    k: v
                    for k, v in doc.items()
                    if k not in ("revision", "created_at", "updated_at")
                }
            )

    def test_anonymous_foreign_origin_and_legacy_default(self):
        self.assertEqual(self.f.state()["method"], ABSOLUTE_METHOD)
        self.f.client.cookies.clear()
        for command in ("method_preview", "valuation_method"):
            r = self.f.client.post("/api/my-dtos", json={"command": command})
            self.assertEqual(r.status_code, 401)
            self.assertNotIn("saved", r.text)
        self.f.use_account("account-a")
        r = self.f.client.post(
            "/api/my-dtos",
            json={},
            headers={"x-csrf-token": self.f.csrf, "origin": "https://foreign.test"},
        )
        self.assertEqual(r.status_code, 403)


class RelativeTradeHTTPTests(unittest.TestCase):
    def test_all_workflows_share_selected_method_neutral_independence_and_missing_safety(
        self,
    ):
        from tests import test_personal_rankings_recovery_trade as recovery

        f = recovery.PersonalRankingsRecoveryTradeTests(
            "test_priced_inactive_player_remains_usable_across_all_custom_workflows"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        editor = f.editor
        neutral_before = f.fixture.trade("neutral").json()["evaluation"]
        f.make_one_price_unavailable()
        before = f.document()

        def select(method):
            preview = editor.post("method_preview", valuation_method=method)
            self.assertEqual(preview.status_code, 200, preview.text)
            activated = editor.post(
                "valuation_method",
                valuation_method=method,
                preview_token=preview.json()["method_preview"]["preview_token"],
                confirmation="APPLY VALUATION METHOD",
            )
            self.assertEqual(activated.status_code, 200, activated.text)

        select(RELATIVE_METHOD)
        source_data = deepcopy(editor.data)
        boot = editor.client.get("/api/trades/workspace").json()["personalization"]
        self.assertEqual(boot["method"], RELATIVE_METHOD)
        self.assertTrue(boot["available"])
        self.assertNotIn("b", boot["values"])
        for endpoint, fields in f.operations:
            with self.subTest(endpoint=endpoint, workflow=fields.get("workflow")):
                r = f.fixture.trade("custom", endpoint=endpoint, **fields)
                self.assertEqual(r.status_code, 200, r.text)
                for result in r.json().get("results", []):
                    e = result.get("evaluation") or {}
                    if e.get("personalization"):
                        self.assertEqual(
                            e["personalization"]["method"], RELATIVE_METHOD
                        )
        custom = f.fixture.trade("custom").json()["evaluation"]
        self.assertEqual(custom["personalization"]["method"], RELATIVE_METHOD)
        neutral_after = f.fixture.trade("neutral").json()["evaluation"]
        for key in (
            "market_evidence",
            "lineup_impact",
            "multi_horizon_impact",
            "counterparty_summary",
        ):
            self.assertEqual(custom[key], neutral_after[key], key)
        for key in ("market_evidence", "lineup_impact", "recommendation"):
            self.assertEqual(neutral_before[key], neutral_after[key], key)
        rejected = f.fixture.trade("custom", assets_sent=["b"])
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(
            rejected.json()["detail"]["code"], "personal_evidence_unavailable"
        )
        self.assertEqual(editor.data, source_data)
        for key in ("order", "baseline", "tiers", "preferences", "mode"):
            self.assertEqual(f.document()[key], before[key])
        select(ABSOLUTE_METHOD)
        self.assertEqual(editor.state()["method"], ABSOLUTE_METHOD)
