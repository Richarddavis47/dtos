"""Exact ownership deltas, without capital-policy or projection substitutions."""

from copy import deepcopy
from types import SimpleNamespace as N
import unittest

from services.trade_capital_inventory import capital_record, inventory_baseline
import json


def fixture():
    picks = [
        dict(
            season=2029,
            round=r,
            original_roster_id=o,
            current_owner_id=1 if o in (1, 3) else 2,
        )
        for r in (1, 2)
        for o in (1, 2, 3)
    ]
    return dict(
        league=dict(league_id="league", season="2026", settings=dict(draft_rounds=2)),
        pick_ledger=picks,
        traded_picks=[
            dict(season="2029", round=r, roster_id=3, owner_id=1) for r in (1, 2)
        ],
        teams=[
            dict(
                roster_id=o,
                team_name=f"Franchise {o}",
                picks_owned=[p for p in picks if p["current_owner_id"] == o],
            )
            for o in (1, 2, 3)
        ],
    )


def asset(original, owner, round_number=1):
    return N(
        kind="pick",
        season=2029,
        round=round_number,
        original_roster_id=original,
        current_owner_id=owner,
        source_roster_id=owner,
        asset_id=f"2029-R{round_number}-{original}",
    )


def record(data, sent=(), received=()):
    return capital_record(
        inventory_baseline(data, 1),
        N(
            active_roster_id=1,
            partner_roster_id=2,
            assets_sent=sent,
            assets_received=received,
        ),
    )


def decode(r):
    return json.loads("".join(r["parts"]))


class CapitalInventoryTests(unittest.TestCase):
    def test_exact_same_round_originals_and_native_inventory(self):
        data = fixture()
        saved = deepcopy(data)
        row = decode(record(data, [asset(1, 1)], [asset(2, 2)]))
        self.assertTrue(row["complete"])
        self.assertIn([2029, 1, 1], row["before"])
        self.assertIn([2029, 1, 3], row["before"])
        self.assertEqual(row["sent"], [[2029, 1, 1]])
        self.assertEqual(row["received"], [[2029, 1, 2]])
        self.assertEqual(data, saved)

    def test_player_only_is_not_missing_inventory(self):
        row = decode(record(fixture(), [N(kind="player")], [N(kind="player")]))
        self.assertTrue(row["complete"])
        self.assertEqual(row["sent"], [])
        self.assertEqual(row["received"], [])

    def test_missing_native_inventory_keeps_exact_movements_not_totals(self):
        data = fixture()
        data.pop("traded_picks")
        row = decode(record(data, [asset(1, 1)], [asset(2, 2)]))
        self.assertFalse(row["complete"])
        self.assertEqual(row["sent"], [[2029, 1, 1]])
        self.assertIn("unknown", row["reason"])

    def test_duplicate_conflict_bad_round_cross_league_rejected(self):
        for mode in ("duplicate", "conflict", "round", "league"):
            data = fixture()
            if mode == "duplicate":
                data["pick_ledger"].append(dict(data["pick_ledger"][0]))
            if mode == "conflict":
                data["pick_ledger"][0]["current_owner_id"] = 2
            if mode == "round":
                data["pick_ledger"][0]["round"] = 3
            if mode == "league":
                data["pick_ledger"][0]["league_id"] = "other"
            with self.subTest(mode=mode):
                row = decode(record(data, [asset(1, 1)]))
                self.assertFalse(row["complete"])
                self.assertTrue(row["invalid"])
                self.assertEqual(row["sent"], [])

    def test_partial_grid_never_supplies_zero(self):
        data = fixture()
        data["pick_ledger"].pop()
        data["teams"][0]["picks_owned"].pop()
        self.assertFalse(decode(record(data))["complete"])

    def test_incorrect_exchange_owner_and_duplicates_rejected(self):
        for sent in ([asset(2, 1)], [asset(1, 1), asset(1, 1)]):
            row = decode(record(fixture(), sent))
            self.assertFalse(row["complete"])
            self.assertTrue(row["invalid"])

    def test_recorded_baseline_survives_ownership_and_league_changes(self):
        data = fixture()
        prior = record(data, [asset(1, 1)])
        old = deepcopy(prior)
        data["pick_ledger"][0]["current_owner_id"] = 2
        self.assertNotEqual(
            decode(record(data))["generation"], decode(old)["generation"]
        )
        data["league"]["league_id"] = "other"
        self.assertEqual(prior, old)

    def test_observed_zero_and_round_configuration(self):
        row = decode(
            capital_record(
                inventory_baseline(fixture(), 3),
                N(
                    active_roster_id=3,
                    partner_roster_id=2,
                    assets_sent=(),
                    assets_received=(),
                ),
            )
        )
        self.assertTrue(row["complete"])
        self.assertEqual(row["before"], [])
        self.assertEqual(row["rounds"], 2)
        self.assertEqual(row["seasons"], [2029])

    def test_native_scope_ambiguity_and_duplicate_roster_are_rejected(self):
        for change in ("league", "season", "roster"):
            data = fixture()
            if change == "league":
                data["traded_picks"][0]["league_id"] = "other"
            if change == "season":
                data["traded_picks"][0]["year"] = 2030
            if change == "roster":
                data["teams"].append(deepcopy(data["teams"][0]))
            with self.subTest(change=change):
                self.assertTrue(decode(record(data))["invalid"])

    def test_bounded_unicode_and_legacy_missing_rounds(self):
        data = fixture()
        data["teams"][0]["team_name"] = "Manager \U0001f3c8"
        self.assertEqual(decode(record(data))["names"]["1"], "Manager \U0001f3c8")
        data["league"]["settings"].pop("draft_rounds")
        row = decode(record(data, [asset(1, 1)]))
        self.assertFalse(row["complete"])
        self.assertEqual(row["sent"], [[2029, 1, 1]])


class CapitalHTTPTests(unittest.TestCase):
    def test_actual_prepared_route_keeps_capital_when_projections_missing(self):
        from tests.test_trade_workspace_batch1 import AuthenticatedTradeBoundaryTests

        helper = AuthenticatedTradeBoundaryTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        data = helper.data
        data["league"].update(season="2026", settings=dict(draft_rounds=4))
        data["pick_ledger"] = [p for t in data["teams"] for p in t["picks_owned"]]
        response = helper._post()
        self.assertEqual(response.status_code, 200, response.text)
        evaluation = response.json()["evaluation"]
        self.assertTrue(decode(evaluation["draft_capital_record"])["complete"])
        self.assertIsNone(evaluation.get("recommendation"))
