"""Actual account storage, authorization and Trade HTTP; disposable preferences."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import unittest

from routes.accounts import create_accounts_router
from src.core.accounts import AccountService, AccountStore
from src.core.accounts.goal_store import GoalSaveError, save_goal
from tests import test_trade_workspace_batch1 as controls


def evidence(name, value):
    if os.getenv("DTOS_STRATEGY_STATE_EVIDENCE"):
        root = Path(os.environ["DTOS_STRATEGY_STATE_EVIDENCE"])
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2))


class StrategyStateHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = controls.AuthenticatedTradeBoundaryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.service = AccountService(self.f.store)
        self.f.client.app.include_router(
            create_accounts_router(service=self.service, runtime_manager=None)
        )
        self.token = self.f.client.cookies.get("dtos_session")

    def form(self, strategy="REBUILD", revision=0):
        ctx = self.f.client.get("/api/trades/workspace").json()["workspace_context"]
        return dict(
            strategy=strategy,
            expected_revision=str(revision),
            league_id=ctx["league_id"],
            roster_id=str(ctx["roster_id"]),
            csrf_token=self.f.csrf,
            strategy_scope=ctx["strategy_scope"],
        )

    def post(self, values):
        return self.f.client.post(
            "/account/franchise-goal", data=values, follow_redirects=False
        )

    def rows(self):
        with closing(self.f.store.connect()) as c:
            return [dict(x) for x in c.execute("SELECT * FROM account_franchise_goals")]

    def test_trade_requests_do_not_save_a_franchise_goal(self):
        before = deepcopy(self.f.data)
        for strategy in ("WIN NOW", "RETOOL", "REBUILD"):
            w = self.f.client.get("/api/trades/workspace").json()
            r = self.f.client.post(
                "/api/trades/evaluate",
                json={
                    **self.f.payload,
                    "strategy": strategy,
                    "workspace_context": w["workspace_context"],
                },
                headers={"X-CSRF-Token": self.f.csrf},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.rows(), [])
            self.assertIsNone(
                self.f.store.context_for_session(self.token).franchise_goal
            )
        self.assertEqual(self.f.data, before)

    def test_only_explicit_save_persists_across_new_sessions_and_reopen(self):
        self.assertEqual(self.rows(), [])
        for revision, strategy in enumerate(("WIN NOW", "RETOOL", "REBUILD", ""), 0):
            response = self.post(self.form(strategy, revision))
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "/teams/1?goal_saved=1")
            self.assertIn("no-store", response.headers["cache-control"])
            reopened = AccountStore(self.f.store.path)
            self.assertEqual(
                reopened.context_for_session(self.token).franchise_goal, strategy
            )
            token, _ = self.service.new_session(self.f.account_id)
            self.assertEqual(
                reopened.context_for_session(token).franchise_goal, strategy
            )
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["revision"], 4)
        evidence(
            "explicit-save",
            {
                "reopened_and_new_session": True,
                "rows": self.rows(),
                "analytical_rows_added": 0,
            },
        )

    def test_stale_save_and_bad_inputs_leave_newer_goal_unchanged(self):
        form = self.form()
        self.assertEqual(self.post(form).status_code, 303)
        saved = self.rows()
        self.assertEqual(self.post(form).status_code, 409)
        for fields, status in (
            ({"strategy": "guaranteed winner", "expected_revision": "1"}, 422),
            ({"csrf_token": "wrong"}, 403),
            ({"roster_id": "2"}, 403),
            ({"league_id": "foreign"}, 403),
            ({"strategy_scope": "foreign-session"}, 403),
            ({"account_id": "foreign"}, 403),
        ):
            self.assertEqual(self.post(dict(form, **fields)).status_code, status)
            self.assertEqual(self.rows(), saved)

    def test_owner_transition_and_revoked_or_expired_session_fail_closed(self):
        account = self.f.store.context_for_session(self.token)
        self.f.store.upsert_membership(
            self.f.account_id,
            {"league_id": "league-1"},
            "fixture-user",
            2,
            "Other franchise",
            "active",
        )
        with self.assertRaises(GoalSaveError):
            save_goal(self.f.store, account, "REBUILD", 0)
        self.assertEqual(self.rows(), [])
        self.f.store.revoke_session(self.token)
        self.assertEqual(self.post(dict(strategy="REBUILD")).status_code, 401)
        with self.assertRaises(GoalSaveError):
            save_goal(self.f.store, account, "REBUILD", 0)
        token, _ = self.service.new_session(self.f.account_id)
        account = self.f.store.context_for_session(token)
        with self.f.store.transaction() as c:
            c.execute(
                "UPDATE account_sessions SET expires_at='2000-01-01' WHERE session_id=?",
                (account.session_id,),
            )
        with self.assertRaises(GoalSaveError):
            save_goal(self.f.store, account, "WIN NOW", 0)

    def test_two_accounts_and_two_leagues_have_independent_goals(self):
        first = self.f.store.context_for_session(self.token)
        save_goal(self.f.store, first, "REBUILD", 0)
        other, _ = self.service.create_account(
            "other", "Other", "disposable test password"
        )
        self.f.store.upsert_membership(
            other, {"league_id": "league-1"}, "other-user", 2, "Other team", "active"
        )
        self.f.store.activate(other, "league-1")
        token, _ = self.service.new_session(other)
        save_goal(self.f.store, self.f.store.context_for_session(token), "WIN NOW", 0)
        self.f.store.upsert_membership(
            self.f.account_id,
            {"league_id": "league-2"},
            "fixture-user",
            1,
            "Second league",
            "active",
        )
        self.f.store.activate(self.f.account_id, "league-2")
        save_goal(
            self.f.store, self.f.store.context_for_session(self.token), "RETOOL", 0
        )
        self.f.store.activate(self.f.account_id, "league-1")
        self.assertEqual(
            self.f.store.context_for_session(self.token).franchise_goal, "REBUILD"
        )
        self.assertEqual(
            self.f.store.context_for_session(token).franchise_goal, "WIN NOW"
        )
        self.assertEqual(len(self.rows()), 3)

    def test_legacy_cookie_is_preserved_without_automatic_import_or_rank_write(self):
        ctx = self.f.client.get("/api/trades/workspace").json()["workspace_context"]
        cookie = (
            base64.urlsafe_b64encode(
                json.dumps(
                    dict(scope=ctx["strategy_scope"], rows=[["league-1:1", "REBUILD"]])
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
        self.f.client.cookies.set("dtos_strategy", cookie)
        self.f.client.get("/api/trades/workspace")
        self.assertEqual(self.f.client.cookies.get("dtos_strategy"), cookie)
        self.assertEqual(self.rows(), [])
        with closing(self.f.store.connect()) as c:
            self.assertEqual(
                c.execute("SELECT count(*) FROM account_personal_rankings").fetchone()[
                    0
                ],
                0,
            )
        self.assertEqual(self.post(self.form("")).status_code, 303)
        new = self.f.client.get("/api/trades/workspace").json()["workspace_context"]
        self.assertEqual(new["franchise_goal"], "")
        self.assertEqual(new["franchise_goal_revision"], 1)
        self.assertEqual(
            new["binding"], ctx["binding"]
        )  # Goal saves never reset active Trade work.

    def test_concurrent_explicit_saves_keep_one_revision_and_bounded_storage(self):
        account = self.f.store.context_for_session(self.token)

        def attempt(strategy):
            try:
                return save_goal(self.f.store, account, strategy, 0)
            except GoalSaveError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ("WIN NOW", "REBUILD")))
        self.assertCountEqual(results, [1, "goal_revision_changed"])
        self.assertEqual(len(self.rows()), 1)
        with self.f.store.transaction() as c:
            c.executemany(
                "INSERT INTO account_franchise_goals VALUES(?,?,?,?,?,?)",
                [
                    (self.f.account_id, f"other-{i}", 1, "RETOOL", 1, "2026-01-01")
                    for i in range(63)
                ],
            )
        self.assertEqual(len(self.rows()), 64)
        save_goal(self.f.store, self.f.store.context_for_session(self.token), "", 1)
        self.f.store.upsert_membership(
            self.f.account_id,
            {"league_id": "new-league"},
            "fixture-user",
            1,
            "New team",
            "active",
        )
        self.f.store.activate(self.f.account_id, "new-league")
        with self.assertRaises(GoalSaveError) as caught:
            save_goal(
                self.f.store, self.f.store.context_for_session(self.token), "REBUILD", 0
            )
        self.assertEqual(caught.exception.code, "goal_limit")
        self.assertEqual(len(self.rows()), 64)

    def test_anonymous_cross_origin_and_oversized_posts_are_denied(self):
        self.assertEqual(
            self.f.client.post(
                "/account/franchise-goal",
                data=self.form(),
                headers={"Origin": "https://foreign.test"},
            ).status_code,
            422,
        )
        self.assertEqual(
            self.f.client.post(
                "/account/franchise-goal",
                content="x" * 4097,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ).status_code,
            422,
        )
        self.f.client.cookies.clear()
        r = self.f.client.post("/account/franchise-goal", data={"strategy": "REBUILD"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.rows(), [])
