"""Exact prepared-offer selection, not a second evaluator or price engine."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from services.trade_for_acquisition import cost_evidence, select_offers
from services.trade_intelligence import _distinct_trade_for_offers
from src.core.trade_intelligence.market_balance import market_balance
from tests.test_batch5_trade_strategy import asset


def panel():
    assets = {
        key: asset(key, price, owner)
        for key, price, owner in (
            ("a", 400, 1),
            ("b", 250, 1),
            ("d", 100, 1),
            ("target", 600, 2),
            ("extra", 100, 2),
        )
    }
    for key, origin, price in [("2029-R1-1", 1, 200), ("2029-R1-3", 3, 150)]:
        assets[key] = replace(
            asset(key, price, 1),
            kind="pick",
            position=None,
            season=2029,
            round=1,
            original_roster_id=origin,
            current_owner_id=1,
        )
    return assets


def row(assets, sent, received=None, verdict="WORTH PURSUING"):
    received = received or ["target"]
    return {
        "proposal": {
            "active_roster_id": 1,
            "partner_roster_id": 2,
            "assets_sent": sent,
            "assets_received": received,
        },
        "evaluation": {
            "legal": True,
            "recommendation": verdict,
            "generated_trade_eligible": verdict == "WORTH PURSUING",
            "legality": {
                "execution_status": "NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER"
            },
            "dimensions": {
                "counterparty_plausibility": {"assessment": "PLAUSIBLE"},
                "confidence": {"assessment": "HIGH"},
            },
            "market_evidence": market_balance(
                tuple(assets[k] for k in sent), tuple(assets[k] for k in received)
            ),
        },
    }


def select(rows, assets):
    return select_offers(rows, assets, "target", _distinct_trade_for_offers)


class AcquisitionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.assets = panel()

    def test_distinct_cost_and_fit_retained_without_rewriting_evaluation(self):
        rows = [
            row(self.assets, ["a"]),
            row(self.assets, ["b"]),
            row(self.assets, ["d"]),
        ]
        before = deepcopy(rows)
        chosen = select(rows, self.assets)
        self.assertEqual(chosen[0]["acquisition_comparison"]["roles"], ["best_fit"])
        self.assertEqual(chosen[1]["proposal"]["assets_sent"], ["d"])
        self.assertEqual(chosen[1]["acquisition_comparison"]["roles"], ["lowest_cost"])
        self.assertEqual(chosen[1]["acquisition_comparison"]["cost"]["outgoing"], 100)
        self.assertEqual(chosen[0]["acquisition_comparison"]["cost"]["outgoing"], 400)
        self.assertEqual(rows, before)
        self.assertTrue(
            all(
                r["evaluation"]
                is rows[[x["proposal"] for x in rows].index(r["proposal"])][
                    "evaluation"
                ]
                for r in chosen
            )
        )

    def test_shape_pruning_cannot_hide_cheaper_same_shape(self):
        rows = [
            row(self.assets, ["a"]),
            row(self.assets, ["a", "b"]),
            row(self.assets, ["a", "b", "d"]),
            row(self.assets, ["d"]),
        ]
        self.assertIn(
            ["d"], [r["proposal"]["assets_sent"] for r in select(rows, self.assets)]
        )
        self.assertEqual(len(select(rows, self.assets)), 3)

    def test_equivalent_pick_dedup_cannot_hide_lower_exact_pick_cost(self):
        rows = [
            row(self.assets, ["a", "2029-R1-1"]),
            row(self.assets, ["a", "2029-R1-3"]),
        ]
        self.assertEqual(len(_distinct_trade_for_offers(rows, self.assets)), 1)
        chosen = select(rows, self.assets)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(chosen[1]["proposal"]["assets_sent"], ["a", "2029-R1-3"])
        self.assertEqual(chosen[1]["acquisition_comparison"]["cost"]["outgoing"], 550)

    def test_same_offer_gets_both_roles_once(self):
        chosen = select([row(self.assets, ["d"])], self.assets)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(
            chosen[0]["acquisition_comparison"]["roles"], ["best_fit", "lowest_cost"]
        )

    def test_cheaper_rejection_or_low_bilateral_support_cannot_win(self):
        for kind in ("rejected", "counterparty", "confidence", "capacity"):
            cheap = row(self.assets, ["d"], verdict="FAIR / OPTIONAL")
            if kind == "rejected":
                cheap["evaluation"]["recommendation"] = "REJECT"
            elif kind == "capacity":
                cheap["evaluation"]["legality"]["execution_status"] = (
                    "REQUIRES ROSTER RESOLUTION"
                )
            else:
                key = (
                    "counterparty_plausibility"
                    if kind == "counterparty"
                    else "confidence"
                )
                cheap["evaluation"]["dimensions"][key]["assessment"] = "LOW"
            with self.subTest(kind=kind):
                chosen = select([row(self.assets, ["a"]), cheap], self.assets)
                self.assertEqual(len(chosen), 1)
                self.assertEqual(
                    chosen[0]["acquisition_comparison"]["roles"],
                    ["best_fit", "lowest_cost"],
                )

    def test_fair_remains_optional_not_promoted(self):
        rows = [
            row(self.assets, ["a"]),
            row(self.assets, ["d"], verdict="FAIR / OPTIONAL"),
        ]
        self.assertEqual(
            select(rows, self.assets)[1]["evaluation"]["recommendation"],
            "FAIR / OPTIONAL",
        )
        self.assertFalse(
            select(rows, self.assets)[1]["evaluation"]["generated_trade_eligible"]
        )

    def test_extra_incoming_assets_separated_from_gross_and_net(self):
        chosen = select(
            [row(self.assets, ["a"], ["target", "extra"]), row(self.assets, ["d"])],
            self.assets,
        )
        cost = chosen[0]["acquisition_comparison"]["cost"]
        self.assertEqual(
            (cost["outgoing"], cost["incoming"], cost["net_received_minus_sent"]),
            (400, 700, 300),
        )
        self.assertEqual(cost["extra_received_asset_ids"], ["extra"])
        self.assertEqual(cost["extra_received_value"], 100)
        self.assertEqual(
            chosen[1]["acquisition_comparison"]["cost"]["extra_received_value"], 0
        )

    def test_missing_price_does_not_win_or_become_zero(self):
        rows = [row(self.assets, ["a"]), row(self.assets, ["d"])]
        assets = {**self.assets, "d": replace(self.assets["d"], trade_value=None)}
        chosen = select(rows, assets)
        self.assertEqual(
            chosen[0]["acquisition_comparison"]["roles"], ["best_fit", "lowest_cost"]
        )
        self.assertEqual(
            chosen[1]["acquisition_comparison"]["cost"]["availability"], "unknown"
        )

    def test_incompatible_units_or_partial_evidence_cannot_win(self):
        for change in (
            {"unit": "personal_rank_slot_value"},
            {"availability": "partial"},
        ):
            rows = [row(self.assets, ["a"]), row(self.assets, ["d"])]
            rows[1]["evaluation"]["market_evidence"].update(change)
            with self.subTest(change=change):
                self.assertEqual(
                    select(rows, self.assets)[1]["acquisition_comparison"]["roles"], []
                )

    def test_ties_use_existing_fit_order_without_rounding(self):
        assets = {**self.assets, "b": replace(self.assets["b"], trade_value=400)}
        rows = [row(assets, ["a"]), row(assets, ["b"])]
        chosen = select(rows, assets)
        self.assertEqual(chosen[0]["acquisition_comparison"]["lowest_cost_ties"], 2)
        self.assertEqual(chosen[1]["acquisition_comparison"]["roles"], [])
        assets["b"] = replace(assets["b"], trade_value=399.999999)
        self.assertEqual(
            select([row(assets, ["a"]), row(assets, ["b"])], assets)[1][
                "acquisition_comparison"
            ]["roles"],
            ["lowest_cost"],
        )

    def test_explicit_zero_supported(self):
        assets = {**self.assets, "d": replace(self.assets["d"], trade_value=0)}
        chosen = select([row(assets, ["a"]), row(assets, ["d"])], assets)
        self.assertEqual(chosen[1]["acquisition_comparison"]["cost"]["outgoing"], 0)
        self.assertEqual(chosen[1]["acquisition_comparison"]["roles"], ["lowest_cost"])

    def test_duplicate_wrong_owner_and_invalid_pick_stay_unknown(self):
        for sent in (["a", "a"], ["target"], ["2029-R1-3"]):
            assets = dict(self.assets)
            if sent == ["2029-R1-3"]:
                assets[sent[0]] = replace(assets[sent[0]], original_roster_id=None)
            r = row(assets, sent)
            self.assertEqual(
                cost_evidence(r, assets, "target")["availability"], "unknown"
            )

    def test_stale_pool_prices_do_not_reprice_retained_evaluation(self):
        r = row(self.assets, ["a"])
        assets = {**self.assets, "a": replace(self.assets["a"], trade_value=10)}
        self.assertEqual(cost_evidence(r, assets, "target")["availability"], "unknown")
        self.assertEqual(r["evaluation"]["market_evidence"]["sent"]["total"], 400)

    def test_custom_values_never_supply_neutral_cost(self):
        for method in ("absolute_slot_v1", "relative_priced_order_v1"):
            r = row(self.assets, ["a"])
            r["evaluation"].update(
                personalization={"mode": "custom", "method": method, "revision": 4},
                values={"sent": 10},
                personal_value_evidence={"sent": {"total": 10}},
            )
            self.assertEqual(
                select([r], self.assets)[0]["acquisition_comparison"]["cost"][
                    "outgoing"
                ],
                400,
            )

    def test_no_eligible_offers_is_empty_not_a_fabricated_tier(self):
        self.assertEqual(select([], self.assets), [])
        self.assertEqual(
            select([row(self.assets, ["d"], verdict="REJECT")], self.assets), []
        )

    def test_selection_is_pure_no_search_or_repair(self):
        r = row(self.assets, ["a"])
        with (
            patch(
                "services.trade_intelligence.generate_proposals",
                side_effect=AssertionError("search"),
            ),
            patch(
                "services.trade_intelligence.evaluate_trade_request",
                side_effect=AssertionError("evaluation"),
            ),
            patch(
                "services.trade_cheaper_repair.cheaper_phase",
                side_effect=AssertionError("repair"),
            ),
        ):
            self.assertEqual(len(select([r], self.assets)), 1)
