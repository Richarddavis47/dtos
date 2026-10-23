"""Bounded account-owned ranking intent, without copied Market/source facts.

The caller supplies canonically verified identities.  This boundary additionally
validates the entire representation and atomically checks scope and revision.
Reads never create a document, record a visit, or update account revisions.
"""
from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .store import AccountStore


MAX_RANKED_ASSETS = 10_000
MAX_DOCUMENT_BYTES = 512 * 1024
_PLAYER = re.compile(r"player:[A-Za-z0-9_-]{1,80}\Z")
_PICK = re.compile(r"pick:[1-9][0-9]{3}:[1-9][0-9]?:[1-9][0-9]{0,9}\Z")
_FIELDS = {"schema", "baseline", "order", "tiers", "preferences", "mode"}
_FLAG_FIELDS = {"target", "avoid", "protect"}
_BASELINE_FIELDS = {"generation", "ids", "source_generation", "source_semantic_generation"}


class PersonalDocumentError(ValueError):
    """Unsupported or over-budget user intent; nothing was persisted."""


class PersonalRevisionConflict(ValueError):
    """A newer explicit edit won; the stale write made no changes."""


class PersonalScopeUnavailable(ValueError):
    """The account no longer controls the requested league franchise."""


def _asset_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_PLAYER.fullmatch(value) or _PICK.fullmatch(value))


def _identity(account_id: str, league_id: str, roster_id: int) -> None:
    if (not isinstance(account_id, str) or not account_id or len(account_id) > 128
            or not isinstance(league_id, str) or not league_id or len(league_id) > 128
            or type(roster_id) is not int or roster_id <= 0):
        raise PersonalDocumentError("Use a valid account, league and franchise scope.")


def encode_document(document: dict[str, Any]) -> str:
    """Validate complete rankings atomically; never truncate user intent.

    10,000 is an explicit identity bound, not a requirement to create that many
    rows.  The separate 512 KiB serialized bound also applies to preferences.
    Tiers are breaks *before* exact assets, not numeric valuation multipliers.
    """
    if not isinstance(document, dict) or set(document) - _FIELDS:
        raise PersonalDocumentError("Use the supported ranking intent fields only.")
    if type(document.get("schema", 1)) is not int or document.get("schema", 1) != 1:
        raise PersonalDocumentError("Unsupported personal rankings schema.")
    baseline = document.get("baseline")
    if (not isinstance(baseline, dict) or not {"generation", "ids"} <= set(baseline)
            or set(baseline) - _BASELINE_FIELDS
            or not isinstance(baseline.get("generation"), str)
            or not baseline["generation"] or len(baseline["generation"]) > 256):
        raise PersonalDocumentError("Use an identified canonical Market baseline.")
    for field in ("source_generation", "source_semantic_generation"):
        if field in baseline and (not isinstance(baseline[field], str)
                                  or not baseline[field] or len(baseline[field]) > 256):
            raise PersonalDocumentError("Use supported canonical baseline source identity.")
    ids = baseline["ids"]
    order = document.get("order")
    if (not isinstance(ids, list) or not 1 <= len(ids) <= MAX_RANKED_ASSETS
            or any(not _asset_id(value) for value in ids)
            or len(set(ids)) != len(ids)):
        raise PersonalDocumentError("Use a complete bounded universe of distinct exact assets.")
    if (not isinstance(order, list) or len(order) != len(ids)
            or any(not _asset_id(value) for value in order)
            or len(set(order)) != len(order) or set(order) != set(ids)):
        raise PersonalDocumentError("The saved order must contain every baseline asset exactly once.")
    tiers = document.get("tiers", [])
    if (not isinstance(tiers, list) or len(tiers) > len(ids)
            or any(not _asset_id(value) for value in tiers)
            or len(set(tiers)) != len(tiers) or not set(tiers) <= set(order)):
        raise PersonalDocumentError("Tier breaks must name distinct ranked assets.")
    preferences = document.get("preferences", {})
    if not isinstance(preferences, dict) or len(preferences) > MAX_RANKED_ASSETS:
        raise PersonalDocumentError("Use a bounded exact-asset preference map.")
    for key, flags in preferences.items():
        if (not _asset_id(key) or not isinstance(flags, dict) or not flags
                or set(flags) - _FLAG_FIELDS
                or any(type(value) is not bool for value in flags.values())
                or flags.get("target") is True and flags.get("avoid") is True):
            raise PersonalDocumentError("Use supported non-conflicting exact-asset preference flags.")
    if document.get("mode", "neutral") not in ("neutral", "custom"):
        raise PersonalDocumentError("Choose Neutral DTOS or Custom DTOS.")
    # A canonical roundtrip both bounds storage and separates caller-owned
    # mutable objects from the serialized document actually committed.
    normalized = {"schema": 1, "baseline": baseline, "order": order,
                  "tiers": tiers, "preferences": preferences,
                  "mode": document.get("mode", "neutral")}
    encoded = json.dumps(normalized, separators=(",", ":"), sort_keys=True, allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise PersonalDocumentError("Personal rankings exceed the 512 KiB saved-intent limit; no changes were saved.")
    return encoded


def _decode(row: Any) -> dict[str, Any]:
    value = json.loads(row["document_json"])
    # Corrupt persisted state must not become an authoritative custom model.
    encode_document(value)
    return {**value, "revision": row["revision"],
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


def load_personal(store: AccountStore, account_id: str, league_id: str,
                  roster_id: int) -> dict[str, Any] | None:
    _identity(account_id, league_id, roster_id)
    with closing(store.connect()) as connection:
        row = connection.execute(
            "SELECT document_json,revision,created_at,updated_at FROM account_personal_rankings "
            "WHERE account_id=? AND league_id=? AND roster_id=?",
            (account_id, league_id, roster_id),
        ).fetchone()
    return _decode(row) if row is not None else None


def save_personal(store: AccountStore, account_id: str, league_id: str,
                  roster_id: int, document: dict[str, Any], *,
                  expected_revision: int,
                  expected_session_id: str | None = None) -> dict[str, Any]:
    _identity(account_id, league_id, roster_id)
    if type(expected_revision) is not int or expected_revision < 0:
        raise PersonalDocumentError("Use the latest saved preference revision.")
    if expected_session_id is not None and (
            not isinstance(expected_session_id, str) or not expected_session_id
            or len(expected_session_id) > 256):
        raise PersonalDocumentError("Use a valid authenticated session identity.")
    encoded = encode_document(document)
    timestamp = datetime.now(timezone.utc).isoformat()
    with store.transaction() as connection:
        authorized = connection.execute(
            "SELECT 1 FROM accounts a JOIN account_league_memberships m ON m.account_id=a.account_id "
            "WHERE a.account_id=? AND a.status='active' AND m.league_id=? "
            "AND m.roster_id=? AND m.status='active'",
            (account_id, league_id, roster_id),
        ).fetchone()
        if authorized is None:
            raise PersonalScopeUnavailable("This account no longer controls that league franchise.")
        if expected_session_id is not None:
            # Authentication can change after request admission. Check within
            # this write transaction, using time after any admission wait.
            session = connection.execute(
                "SELECT 1 FROM account_sessions WHERE account_id=? AND session_id=? "
                "AND revoked_at IS NULL AND expires_at>?",
                (account_id, expected_session_id, datetime.now(timezone.utc).isoformat()),
            ).fetchone()
            if session is None:
                raise PersonalScopeUnavailable("Your session expired or was revoked. Sign in again before saving.")
        row = connection.execute(
            "SELECT revision,created_at FROM account_personal_rankings "
            "WHERE account_id=? AND league_id=? AND roster_id=?",
            (account_id, league_id, roster_id),
        ).fetchone()
        revision = row["revision"] if row else 0
        if revision != expected_revision:
            raise PersonalRevisionConflict("Saved rankings changed. Reload your latest preferences before editing.")
        created_at = row["created_at"] if row else timestamp
        connection.execute(
            "INSERT INTO account_personal_rankings "
            "(account_id,league_id,roster_id,document_json,revision,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(account_id,league_id,roster_id) DO UPDATE SET "
            "document_json=excluded.document_json,revision=excluded.revision,updated_at=excluded.updated_at",
            (account_id, league_id, roster_id, encoded, revision + 1, created_at, timestamp),
        )
    return {**json.loads(encoded), "revision": revision + 1,
            "created_at": created_at, "updated_at": timestamp}
