"""Durable personal intent controls; no live accounts, sources or providers."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from src.core.accounts import AccountStore
from src.core.accounts.personal_store import (
    MAX_DOCUMENT_BYTES, PersonalDocumentError, PersonalRevisionConflict,
    PersonalScopeUnavailable, encode_document, load_personal, save_personal,
)


def document(count: int = 3) -> dict:
    ids = [f"player:{index}" for index in range(1, count + 1)]
    return {"schema": 1, "baseline": {"generation": "market-generation-a", "ids": ids},
            "order": ids.copy(), "tiers": [], "preferences": {}, "mode": "neutral"}


class PersonalRankingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "accounts.sqlite3"
        self.store = AccountStore(self.path)
        for account_id in ("account-a", "account-b"):
            self.store.create_account(account_id, account_id, account_id, "fixture-hash", [])
            for league in ("100", "300"):
                self.store.upsert_membership(account_id, {"league_id": league, "season": "2026"},
                                             account_id, 1, "Fixture franchise", "active")

    def save(self, value=None, revision=0, *, account="account-a", league="100", roster=1):
        return save_personal(self.store, account, league, roster,
                             value or document(), expected_revision=revision)

    def load(self, *, account="account-a", league="100", roster=1):
        return load_personal(self.store, account, league, roster)

    def facts(self):
        with closing(self.store.connect()) as connection:
            return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1,2")]
                    for table in ("accounts", "account_league_memberships", "account_league_series",
                                  "account_league_series_seasons", "account_sessions", "account_personal_rankings")}

    def test_unchanged_reads_do_not_create_rows_or_write_files(self):
        before = self.facts()
        original_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
        for _ in range(20):
            self.assertIsNone(self.load())
        self.assertEqual(self.facts(), before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), original_hash)
        self.save()
        before = self.facts()
        original_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
        for _ in range(20):
            self.assertEqual(self.load()["revision"], 1)
        self.assertEqual(self.facts(), before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), original_hash)

    def test_full_order_and_sparse_intent_roundtrip_without_source_facts(self):
        value = document(1000)
        value["order"].reverse()
        value["tiers"] = [value["order"][0], value["order"][400]]
        value["preferences"] = {"player:1": {"target": True}, "pick:2028:1:4": {"protect": True}}
        result = self.save(value)
        self.assertEqual(result["revision"], 1)
        self.assertEqual(self.load(), result)
        self.assertEqual(result["order"], value["order"])
        self.assertNotIn("prices", result)
        before = self.facts()
        del before["account_personal_rankings"]
        changed = document(1000)
        changed["mode"] = "custom"
        result2 = self.save(changed, revision=1)
        self.assertEqual(result2["revision"], 2)
        self.assertEqual(result2["created_at"], result["created_at"])
        after = self.facts()
        del after["account_personal_rankings"]
        self.assertEqual(after, before)

    def test_separate_account_league_and_franchise_scopes(self):
        self.save()
        self.assertIsNone(self.load(account="account-b"))
        self.assertIsNone(self.load(league="300"))
        self.assertIsNone(self.load(roster=2))
        other = document()
        other["order"].reverse()
        self.save(other, account="account-b")
        self.save(other, league="300")
        self.assertEqual(self.load()["order"], document()["order"])
        self.assertEqual(self.load(account="account-b")["order"], other["order"])
        self.assertEqual(self.load(league="300")["order"], other["order"])

    def test_concurrent_edits_have_one_winner_and_no_partial_account_mutation(self):
        self.save()
        before = self.facts()
        barrier = threading.Barrier(2)

        def compete(mode):
            value = document()
            value["mode"] = mode
            barrier.wait(timeout=3)
            try:
                return self.save(value, revision=1)["revision"]
            except PersonalRevisionConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, ("neutral", "custom")))
        self.assertCountEqual(results, [2, "conflict"])
        after = self.facts()
        self.assertEqual(len(after["account_personal_rankings"]), 1)
        del before["account_personal_rankings"], after["account_personal_rankings"]
        self.assertEqual(after, before)

    def test_stale_create_and_update_leave_durable_state_unchanged(self):
        self.save()
        for revision in (0, 2, 100):
            before = self.facts()
            with self.assertRaises(PersonalRevisionConflict):
                self.save(revision=revision)
            self.assertEqual(self.facts(), before)

    def test_revoked_or_changed_membership_is_checked_at_commit(self):
        self.save()
        for field, value in (("status", "inactive"), ("roster_id", 2)):
            with self.store.transaction() as connection:
                connection.execute(f"UPDATE account_league_memberships SET {field}=? WHERE account_id=? AND league_id=?",
                                   (value, "account-a", "100"))
            before = self.facts()
            with self.assertRaises(PersonalScopeUnavailable):
                self.save(revision=1)
            self.assertEqual(self.facts(), before)
            with self.store.transaction() as connection:
                connection.execute("UPDATE account_league_memberships SET status='active',roster_id=1 WHERE account_id=? AND league_id=?",
                                   ("account-a", "100"))
        with self.assertRaises(PersonalScopeUnavailable):
            self.save(account="not-an-account")

    def test_commit_failure_rolls_back_and_later_retry_succeeds(self):
        with self.store.transaction() as connection:
            connection.execute("CREATE TRIGGER fixture_fail BEFORE INSERT ON account_personal_rankings BEGIN SELECT RAISE(ABORT,'fixture'); END")
        before = self.facts()
        with self.assertRaises(sqlite3.IntegrityError):
            self.save()
        self.assertEqual(self.facts(), before)
        with self.store.transaction() as connection:
            connection.execute("DROP TRIGGER fixture_fail")
        self.assertEqual(self.save()["revision"], 1)

    def test_session_revocation_expiry_and_foreign_identity_fail_at_commit(self):
        self.store.create_session(account_id="account-a", token="token-a", session_id="session-a",
                                  csrf_token="fixture-csrf", ttl_hours=1)
        self.store.create_session(account_id="account-b", token="token-b", session_id="session-b",
                                  csrf_token="fixture-csrf-b", ttl_hours=1)
        saved = save_personal(self.store, "account-a", "100", 1, document(),
                              expected_revision=0, expected_session_id="session-a")
        self.assertEqual(saved["revision"], 1)
        for change, session_id in (("revoked", "session-a"), ("expired", "session-a"),
                                   ("foreign", "session-b"), ("missing", "missing-session")):
            with self.subTest(change=change):
                with self.store.transaction() as connection:
                    connection.execute("UPDATE account_sessions SET revoked_at=NULL,expires_at='9999-01-01T00:00:00+00:00' WHERE session_id='session-a'")
                    if change == "revoked":
                        connection.execute("UPDATE account_sessions SET revoked_at='2020-01-01T00:00:00+00:00' WHERE session_id='session-a'")
                    elif change == "expired":
                        connection.execute("UPDATE account_sessions SET expires_at='2020-01-01T00:00:00+00:00' WHERE session_id='session-a'")
                before = self.facts()
                with self.assertRaises(PersonalScopeUnavailable):
                    save_personal(self.store, "account-a", "100", 1, document(),
                                  expected_revision=1, expected_session_id=session_id)
                self.assertEqual(self.facts(), before)
        for session_id in (True, 123, "", "a" * 257):
            with self.subTest(session_id=session_id), self.assertRaises(PersonalDocumentError):
                save_personal(self.store, "account-a", "100", 1, document(),
                              expected_revision=1, expected_session_id=session_id)

    def test_restart_can_preserve_unresolved_exact_preferences(self):
        old = document()
        old["preferences"] = {"pick:2028:1:4": {"protect": True}, "player:999": {"avoid": True}}
        self.save(old)
        new = document(4)
        new["baseline"]["generation"] = "market-generation-b"
        new["preferences"] = old["preferences"]
        result = self.save(new, revision=1)
        self.assertEqual(result["preferences"], old["preferences"])
        self.assertEqual(result["order"], new["baseline"]["ids"])

    def test_mutable_results_and_inputs_are_independent(self):
        value = document()
        saved = self.save(value)
        value["order"].reverse()
        saved["baseline"]["ids"].clear()
        first = self.load()
        first["order"].clear()
        self.assertEqual(self.load()["order"], document()["order"])

    def test_all_10000_ranked_assets_fit_without_truncation(self):
        value = document(10_000)
        encoded = encode_document(value)
        self.assertLess(len(encoded.encode()), MAX_DOCUMENT_BYTES)
        saved = self.save(value)
        self.assertEqual(len(saved["order"]), 10_000)
        self.assertEqual(self.load()["order"], value["order"])

    def test_over_budget_or_too_many_assets_fail_whole_document(self):
        self.save()
        for value in (document(10_001), document(10_000)):
            if len(value["order"]) == 10_000:
                value["preferences"] = {key: {"protect": True, "target": True} for key in value["order"]}
            before = self.facts()
            with self.assertRaises(PersonalDocumentError):
                self.save(value, revision=1)
            self.assertEqual(self.facts(), before)

    def test_invalid_types_identities_permutations_and_contradictions_fail_closed(self):
        variants = []
        for component in (1, True, None, 1.1, "player:", "pick:2028:1:unknown"):
            value = document()
            value["baseline"]["ids"][0] = component
            value["order"][0] = component
            variants.append(value)
        for change in (
            {"order": ["player:1", "player:1", "player:3"]},
            {"order": ["player:1"]}, {"tiers": ["player:999"]},
            {"tiers": ["player:1", "player:1"]}, {"schema": True},
            {"mode": "opponent"}, {"prices": {"player:1": 999}},
            {"preferences": {"player:1": {"target": True, "avoid": True}}},
            {"preferences": {"player:1": {"protect": 1}}},
            {"preferences": {"player:1": {"value": 200}}},
        ):
            variants.append({**document(), **change})
        for value in variants:
            with self.subTest(value=value), self.assertRaises(PersonalDocumentError):
                self.save(value)
        self.assertIsNone(self.load())
        for revision in (True, -1, None, 0.0):
            with self.assertRaises(PersonalDocumentError):
                self.save(revision=revision)

    def test_corrupt_persisted_document_is_not_admitted(self):
        self.save()
        with self.store.transaction() as connection:
            bad = document()
            bad["order"] = ["player:1"]
            connection.execute("UPDATE account_personal_rankings SET document_json=?", (json.dumps(bad),))
        with self.assertRaises(PersonalDocumentError):
            self.load()

    def test_restart_reopen_and_migration_are_idempotent(self):
        self.save()
        self.store = AccountStore(self.path)
        self.assertEqual(self.load()["revision"], 1)
        with closing(self.store.connect()) as connection:
            self.assertEqual([row[0] for row in connection.execute("SELECT version FROM account_schema_migrations ORDER BY version")], [1, 2, 3])
            self.assertEqual(connection.execute("SELECT count(*) FROM account_personal_rankings").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
