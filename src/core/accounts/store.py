"""Transactional SQLite account storage with no provider or market payloads."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import AccountContext, LeagueMembership

ACCOUNT_SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS account_schema_migrations(
  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts(
  account_id TEXT PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
  display_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  active_league_id TEXT
);
CREATE TABLE IF NOT EXISTS account_credentials(
  account_id TEXT PRIMARY KEY REFERENCES accounts(account_id) ON DELETE CASCADE,
  password_hash TEXT NOT NULL, recovery_hashes TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sleeper_identities(
  account_id TEXT PRIMARY KEY REFERENCES accounts(account_id) ON DELETE CASCADE,
  sleeper_user_id TEXT NOT NULL UNIQUE, sleeper_username TEXT,
  display_name TEXT, link_state TEXT NOT NULL,
  linked_at TEXT NOT NULL, last_resolved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_league_memberships(
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  league_id TEXT NOT NULL, sleeper_user_id TEXT NOT NULL,
  roster_id INTEGER, status TEXT NOT NULL, mapping_source TEXT NOT NULL,
  league_name TEXT, franchise_name TEXT, season INTEGER,
  created_at TEXT NOT NULL, last_verified_at TEXT NOT NULL,
  PRIMARY KEY(account_id, league_id)
);
CREATE INDEX IF NOT EXISTS account_membership_league ON account_league_memberships(league_id);
CREATE TABLE IF NOT EXISTS account_league_series(
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  series_id TEXT NOT NULL, current_league_id TEXT NOT NULL,
  league_name TEXT, current_season INTEGER,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY(account_id,series_id)
);
CREATE INDEX IF NOT EXISTS account_series_current ON account_league_series(account_id,current_league_id);
CREATE TABLE IF NOT EXISTS account_league_series_seasons(
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  series_id TEXT NOT NULL, league_id TEXT NOT NULL, season INTEGER,
  previous_league_id TEXT, roster_id INTEGER, franchise_name TEXT,
  created_at TEXT NOT NULL, last_verified_at TEXT NOT NULL,
  PRIMARY KEY(account_id,league_id)
);
CREATE INDEX IF NOT EXISTS account_series_seasons ON account_league_series_seasons(account_id,series_id,season);
CREATE TABLE IF NOT EXISTS account_sessions(
  session_digest TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE,
  account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
  csrf_token TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL, revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS account_sessions_account ON account_sessions(account_id);
CREATE TABLE IF NOT EXISTS account_auth_audit(
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
  account_id TEXT, event_type TEXT NOT NULL, result TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '{}'
);
"""


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.transaction() as connection:
            connection.executescript(SCHEMA)
            for version in range(1, ACCOUNT_SCHEMA_VERSION + 1):
                connection.execute(
                    "INSERT OR IGNORE INTO account_schema_migrations(version,applied_at) VALUES(?,?)",
                    (version, _now()),
                )

    def account_by_username(self, username: str) -> sqlite3.Row | None:
        with closing(self.connect()) as connection:
            return connection.execute(
                "SELECT a.*,c.password_hash,c.recovery_hashes FROM accounts a JOIN account_credentials c USING(account_id) WHERE a.username=? AND a.status='active'",
                (username.strip(),),
            ).fetchone()

    def recent_auth_failures(self, event_type: str, client_digest: str, *, minutes: int = 15) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        with closing(self.connect()) as connection:
            return int(connection.execute(
                "SELECT count(*) FROM account_auth_audit WHERE event_type=? AND result='failure' AND detail=? AND occurred_at>=?",
                (event_type, json.dumps({"client": client_digest}, separators=(",", ":")), cutoff),
            ).fetchone()[0])

    def record_auth_result(self, account_id: str | None, event_type: str, result: str, client_digest: str) -> None:
        detail = json.dumps({"client": client_digest}, separators=(",", ":"))
        with self.transaction() as connection:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            connection.execute("DELETE FROM account_auth_audit WHERE occurred_at<?", (cutoff,))
            connection.execute(
                "INSERT INTO account_auth_audit(occurred_at,account_id,event_type,result,detail) VALUES(?,?,?,?,?)",
                (_now(), account_id, event_type, result, detail),
            )

    def create_account(self, account_id: str, username: str, display_name: str, password_hash: str, recovery_hashes: list[str]) -> None:
        timestamp = _now()
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO accounts(account_id,username,display_name,created_at,updated_at) VALUES(?,?,?,?,?)",
                (account_id, username.strip(), display_name.strip(), timestamp, timestamp),
            )
            connection.execute(
                "INSERT INTO account_credentials(account_id,password_hash,recovery_hashes,updated_at) VALUES(?,?,?,?)",
                (account_id, password_hash, json.dumps(recovery_hashes), timestamp),
            )

    def create_session(self, *, account_id: str, token: str, session_id: str, csrf_token: str, ttl_hours: int) -> None:
        timestamp = datetime.now(timezone.utc)
        with self.transaction() as connection:
            connection.execute(
                "DELETE FROM account_sessions WHERE expires_at<=? OR (revoked_at IS NOT NULL AND revoked_at<=?)",
                (timestamp.isoformat(), (timestamp - timedelta(days=30)).isoformat()),
            )
            connection.execute(
                "INSERT INTO account_sessions(session_digest,session_id,account_id,csrf_token,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?,?,?)",
                (_token_digest(token), session_id, account_id, csrf_token, timestamp.isoformat(), (timestamp + timedelta(hours=ttl_hours)).isoformat(), timestamp.isoformat()),
            )

    def revoke_session(self, token: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE account_sessions SET revoked_at=? WHERE session_digest=? AND revoked_at IS NULL",
                (_now(), _token_digest(token)),
            )

    def recover_account(self, username: str, recovery_digest: str, password_hash: str, replacement_hashes: list[str]) -> str | None:
        """Consume one recovery code, rotate credentials, and revoke every session atomically."""
        timestamp = _now()
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT a.account_id,c.recovery_hashes FROM accounts a
                JOIN account_credentials c USING(account_id)
                WHERE a.username=? AND a.status='active'""",
                (username.strip(),),
            ).fetchone()
            if row is None:
                return None
            stored = json.loads(row["recovery_hashes"] or "[]")
            matched = next((value for value in stored if hmac.compare_digest(value, recovery_digest)), None)
            if matched is None:
                return None
            account_id = str(row["account_id"])
            connection.execute(
                "UPDATE account_credentials SET password_hash=?,recovery_hashes=?,updated_at=? WHERE account_id=?",
                (password_hash, json.dumps(replacement_hashes), timestamp, account_id),
            )
            connection.execute(
                "UPDATE account_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                (timestamp, account_id),
            )
            connection.execute(
                "INSERT INTO account_auth_audit(occurred_at,account_id,event_type,result) VALUES(?,?,?,?)",
                (timestamp, account_id, "credential_recovery", "success"),
            )
            return account_id

    def context_for_session(self, token: str) -> AccountContext | None:
        now = _now()
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT s.session_id,s.csrf_token,a.account_id,a.username,a.display_name,a.active_league_id,
                i.sleeper_user_id,i.sleeper_username,i.link_state
                FROM account_sessions s JOIN accounts a USING(account_id)
                LEFT JOIN sleeper_identities i USING(account_id)
                WHERE s.session_digest=? AND s.revoked_at IS NULL AND s.expires_at>? AND a.status='active'""",
                (_token_digest(token), now),
            ).fetchone()
            if row is None:
                return None
            membership_row = None
            if row["active_league_id"]:
                membership_row = connection.execute(
                    "SELECT * FROM account_league_memberships WHERE account_id=? AND league_id=? AND status='active'",
                    (row["account_id"], row["active_league_id"]),
                ).fetchone()
            membership = LeagueMembership(**{
                key: membership_row[key] for key in (
                    "account_id", "league_id", "sleeper_user_id", "roster_id",
                    "status", "mapping_source", "league_name", "franchise_name", "season",
                )
            }) if membership_row else None
            return AccountContext(
                account_id=row["account_id"], username=row["username"], display_name=row["display_name"],
                sleeper_user_id=row["sleeper_user_id"], sleeper_username=row["sleeper_username"],
                sleeper_link_state=row["link_state"], active_league_id=row["active_league_id"] if membership else None,
                membership=membership, csrf_token=row["csrf_token"], session_id=row["session_id"],
            )

    def verify_csrf(self, token: str, submitted: str) -> bool:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT csrf_token FROM account_sessions WHERE session_digest=? AND revoked_at IS NULL AND expires_at>?",
                (_token_digest(token), _now()),
            ).fetchone()
        return bool(row and hmac.compare_digest(row["csrf_token"], submitted))

    def link_sleeper(self, account_id: str, *, sleeper_user_id: str, username: str | None, display_name: str | None) -> None:
        timestamp = _now()
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO sleeper_identities(account_id,sleeper_user_id,sleeper_username,display_name,link_state,linked_at,last_resolved_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET sleeper_user_id=excluded.sleeper_user_id,
                sleeper_username=excluded.sleeper_username,display_name=excluded.display_name,link_state='resolved',last_resolved_at=excluded.last_resolved_at""",
                (account_id, sleeper_user_id, username, display_name, "resolved", timestamp, timestamp),
            )

    def upsert_membership(self, account_id: str, league: dict[str, Any], sleeper_user_id: str, roster_id: int | None, franchise_name: str | None, status: str) -> None:
        timestamp = _now()
        league_id = str(league.get("league_id") or "")
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO account_league_memberships(account_id,league_id,sleeper_user_id,roster_id,status,mapping_source,league_name,franchise_name,season,created_at,last_verified_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(account_id,league_id) DO UPDATE SET sleeper_user_id=excluded.sleeper_user_id,
                roster_id=excluded.roster_id,status=excluded.status,mapping_source=excluded.mapping_source,league_name=excluded.league_name,
                franchise_name=excluded.franchise_name,season=excluded.season,last_verified_at=excluded.last_verified_at""",
                (account_id, league_id, sleeper_user_id, roster_id, status, "sleeper_roster_association", league.get("name"), franchise_name, int(league.get("season") or 0) or None, timestamp, timestamp),
            )

    def upsert_series(
        self, account_id: str, *, series_id: str, current_league: dict[str, Any],
        seasons: tuple[dict[str, Any], ...], roster_id: int | None,
        franchise_name: str | None,
    ) -> None:
        """Persist a series and its season identities without loading runtimes."""
        timestamp = _now()
        current_id = str(current_league.get("league_id") or "")
        current_season = int(current_league.get("season") or 0) or None
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO account_league_series(account_id,series_id,current_league_id,league_name,current_season,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(account_id,series_id) DO UPDATE SET
                current_league_id=excluded.current_league_id,league_name=excluded.league_name,
                current_season=excluded.current_season,updated_at=excluded.updated_at""",
                (account_id, series_id, current_id, current_league.get("name"), current_season, timestamp, timestamp),
            )
            for row in seasons:
                league_id = str(row.get("league_id") or "")
                if not league_id:
                    continue
                season = int(row.get("season") or 0) or None
                is_current = league_id == current_id
                connection.execute(
                    """INSERT INTO account_league_series_seasons(account_id,series_id,league_id,season,previous_league_id,roster_id,franchise_name,created_at,last_verified_at)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(account_id,league_id) DO UPDATE SET
                    series_id=excluded.series_id,season=excluded.season,previous_league_id=excluded.previous_league_id,
                    roster_id=CASE WHEN excluded.roster_id IS NOT NULL THEN excluded.roster_id ELSE account_league_series_seasons.roster_id END,
                    franchise_name=CASE WHEN excluded.franchise_name IS NOT NULL THEN excluded.franchise_name ELSE account_league_series_seasons.franchise_name END,
                    last_verified_at=excluded.last_verified_at""",
                    (account_id, series_id, league_id, season, row.get("previous_league_id"), roster_id if is_current else None, franchise_name if is_current else None, timestamp, timestamp),
                )

    def series(self, account_id: str) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """SELECT s.*,m.roster_id,m.franchise_name,m.status,
                (SELECT count(*) FROM account_league_series_seasons x WHERE x.account_id=s.account_id AND x.series_id=s.series_id) AS season_count
                FROM account_league_series s LEFT JOIN account_league_memberships m
                ON m.account_id=s.account_id AND m.league_id=s.current_league_id
                WHERE s.account_id=? ORDER BY s.current_season DESC,s.league_name,s.series_id""",
                (account_id,),
            ).fetchall()
            represented = {
                str(row["league_id"])
                for row in connection.execute(
                    "SELECT league_id FROM account_league_series_seasons WHERE account_id=?",
                    (account_id,),
                ).fetchall()
            }
            fallbacks = connection.execute(
                "SELECT * FROM account_league_memberships WHERE account_id=? AND status='active' ORDER BY season DESC,league_name,league_id",
                (account_id,),
            ).fetchall()
        result = [dict(row) for row in rows]
        result.extend({
            "account_id": row["account_id"], "series_id": row["league_id"],
            "current_league_id": row["league_id"], "league_name": row["league_name"],
            "current_season": row["season"], "roster_id": row["roster_id"],
            "franchise_name": row["franchise_name"], "status": row["status"],
            "season_count": 1,
        } for row in fallbacks if str(row["league_id"]) not in represented)
        return sorted(result, key=lambda row: (-(int(row.get("current_season") or 0)), str(row.get("league_name") or ""), str(row["series_id"])))

    def series_seasons(self, account_id: str, series_id: str) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM account_league_series_seasons WHERE account_id=? AND series_id=? ORDER BY season DESC,league_id",
                (account_id, series_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def memberships(self, account_id: str) -> list[LeagueMembership]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM account_league_memberships WHERE account_id=? ORDER BY season DESC,league_name,league_id",
                (account_id,),
            ).fetchall()
        return [LeagueMembership(**{key: row[key] for key in LeagueMembership.__dataclass_fields__}) for row in rows]

    def activate(self, account_id: str, league_id: str) -> LeagueMembership | None:
        with self.transaction() as connection:
            historical = connection.execute(
                """SELECT 1 FROM account_league_series_seasons x
                JOIN account_league_series s ON s.account_id=x.account_id AND s.series_id=x.series_id
                WHERE x.account_id=? AND x.league_id=? AND s.current_league_id<>x.league_id""",
                (account_id, league_id),
            ).fetchone()
            if historical is not None:
                return None
            row = connection.execute(
                "SELECT * FROM account_league_memberships WHERE account_id=? AND league_id=? AND status='active' AND roster_id IS NOT NULL",
                (account_id, league_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute("UPDATE accounts SET active_league_id=?,updated_at=? WHERE account_id=?", (league_id, _now(), account_id))
        return LeagueMembership(**{key: row[key] for key in LeagueMembership.__dataclass_fields__})

    def health(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            counts = {
                name: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for name, table in (("accounts", "accounts"), ("sleeper_links", "sleeper_identities"), ("memberships", "account_league_memberships"), ("league_series", "account_league_series"), ("season_references", "account_league_series_seasons"), ("active_sessions", "account_sessions WHERE revoked_at IS NULL AND expires_at > datetime('now')"))
            }
        return {"status": "healthy", "schema_version": ACCOUNT_SCHEMA_VERSION, "counts": counts, "bytes": self.path.stat().st_size if self.path.exists() else 0}
