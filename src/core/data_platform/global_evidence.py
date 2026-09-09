"""Global, semantic-state storage for normalized public NFL evidence.

This is not a league archive. Callers supply approved normalized facts only;
league scoring and private franchise conclusions never enter this store.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import shutil
import zlib
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.platform.storage_gate import connect


FAMILIES = frozenset({"production", "usage", "contract", "schedule", "depth", "injury", "identity"})
_COMMON = frozenset({"game_id", "team", "opponent", "position", "season_type"})
_FIELDS = {
    "production": frozenset({"pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int",
        "rush_att", "rush_yd", "rush_td", "rec", "rec_yd", "rec_td", "rec_tgt",
        "rec_air_yd", "fumbles", "fumbles_lost", "pass_2pt", "rush_2pt", "rec_2pt",
        "target_share", "air_yards_share", "pass_fd", "rush_fd", "rec_fd", "pass_sack"}),
    "usage": frozenset({"offense_snaps", "offense_pct", "targets", "carries", "touches",
        "team_targets", "team_carries", "target_share", "carry_share", "routes", "route_participation"}),
    "contract": frozenset({"year_signed", "years", "value", "apy", "guaranteed", "is_active", "expires"}),
    "schedule": frozenset({"home_team", "away_team", "game_date", "kickoff", "game_type"}),
    "depth": frozenset({"depth_position", "depth_order", "role"}),
    "injury": frozenset({"status", "designation", "practice_status", "body_part"}),
    "identity": frozenset({"sleeper_id", "gsis_id", "pfr_id", "espn_id", "otc_id", "display_name"}),
}
_PRIVATE = frozenset({"league_id", "account_id", "franchise_id", "roster_id", "owner_id",
                      "cookie", "authorization", "token", "password", "secret"})


def utc(value: str) -> str:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Evidence timestamps require an explicit timezone.")
    return stamp.astimezone(timezone.utc).isoformat()


def _public(value: Any) -> None:
    if isinstance(value, dict):
        if any(str(key).casefold() in _PRIVATE for key in value):
            raise ValueError("Private fields cannot enter global evidence.")
        for item in value.values():
            _public(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _public(item)


@dataclass(frozen=True)
class GlobalFact:
    family: str
    subject_id: str
    provider: str
    source_record_id: str
    effective_at: str
    known_at: str | None
    values: dict[str, Any]
    season: int | None = None
    week: int | None = None
    method_version: str = "1"

    def canonical(self) -> bytes:
        if self.family not in FAMILIES or not all((self.subject_id, self.provider, self.source_record_id, self.method_version)):
            raise ValueError("A global fact requires supported family and source identity.")
        _public(self.values)
        if set(self.values) - (_FIELDS[self.family] | _COMMON):
            raise ValueError("Unapproved field in normalized global evidence.")
        if any(not isinstance(value, (str, int, float, bool, type(None))) for value in self.values.values()):
            raise ValueError("Global evidence values must be normalized scalar fields.")
        payload = asdict(self)
        payload["effective_at"] = utc(self.effective_at)
        payload["known_at"] = utc(self.known_at) if self.known_at else None
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(body) > 65536:
            raise ValueError("Global fact exceeds the bounded normalized-record contract.")
        return body


@dataclass(frozen=True)
class IngestionCheckpoint:
    key: str
    source_identity: str
    start: int
    offset: int
    complete: bool = False


class GlobalEvidenceStore:
    """Content-addressed states; unchanged replay performs zero durable writes.

    Each bounded publication is atomic. Meaningful corrections remain distinct
    states; historical queries filter both effective and knowledge boundaries.
    Unknown historical publication time is eligible only from first observation.
    """

    def __init__(self, path: Path, *, maximum_bytes: int = 256 * 1048576, reserve_bytes: int = 128 * 1048576,
                 readonly: bool = False):
        if maximum_bytes < 1048576 or reserve_bytes < 0:
            raise ValueError("Invalid global evidence storage admission budget.")
        self.maximum_bytes = maximum_bytes
        self.reserve_bytes = reserve_bytes
        self.path = Path(path)
        self.readonly = readonly
        if readonly:
            if not self.path.is_file():
                raise FileNotFoundError(self.path)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS global_facts(
                    fingerprint TEXT PRIMARY KEY, family TEXT NOT NULL,
                    subject_id TEXT NOT NULL, provider TEXT NOT NULL,
                    source_record_id TEXT NOT NULL, effective_at TEXT NOT NULL,
                    known_at TEXT NOT NULL, first_seen TEXT NOT NULL,
                    payload BLOB NOT NULL);
                CREATE INDEX IF NOT EXISTS global_fact_lookup
                ON global_facts(family,subject_id,provider,known_at,effective_at);
                CREATE TABLE IF NOT EXISTS global_fact_revisions(
                    fingerprint TEXT NOT NULL REFERENCES global_facts(fingerprint),
                    known_at TEXT NOT NULL, observed_at TEXT NOT NULL,
                    PRIMARY KEY(fingerprint,known_at,observed_at));
                CREATE TABLE IF NOT EXISTS global_ingestion(
                    key TEXT PRIMARY KEY, source_identity TEXT NOT NULL,
                    offset INTEGER NOT NULL, complete INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS global_source_checks(
                    key TEXT PRIMARY KEY, source_identity TEXT,
                    checked_at TEXT NOT NULL, status TEXT NOT NULL, details TEXT NOT NULL);
            """)
            columns = {row[1] for row in connection.execute('PRAGMA table_info(global_fact_revisions)')}
            for name, definition in (
                ('published', 'INTEGER NOT NULL DEFAULT 1'),
                ('publication_key', "TEXT NOT NULL DEFAULT ''"),
                ('publication_identity', "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in columns:
                    connection.execute(f'ALTER TABLE global_fact_revisions ADD COLUMN {name} {definition}')
            fact_columns = {row[1] for row in connection.execute('PRAGMA table_info(global_facts)')}
            if 'season' not in fact_columns:
                connection.execute('ALTER TABLE global_facts ADD COLUMN season INTEGER')
                # Existing candidate evidence is indexed losslessly, one bounded
                # record at a time. This initializer only runs in write workers.
                for row in connection.execute('SELECT fingerprint,payload FROM global_facts'):
                    season = json.loads(zlib.decompress(row['payload'])).get('season')
                    connection.execute('UPDATE global_facts SET season=? WHERE fingerprint=?',
                                       (season, row['fingerprint']))
            connection.execute('CREATE INDEX IF NOT EXISTS global_fact_season ON global_facts(family,season,subject_id)')

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        connection = connect(self.path, timeout=10, readonly=readonly)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        if not readonly:
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            connection.execute(f"PRAGMA max_page_count={self.maximum_bytes // page_size}")
        return connection

    def publish(self, facts: Iterable[GlobalFact], *, retrieved_at: str, max_records: int = 1000,
                checkpoint: IngestionCheckpoint | None = None) -> dict[str, int]:
        if self.readonly:
            raise PermissionError("Read-only global evidence cannot publish.")
        if not 1 <= max_records <= 1000:
            raise ValueError("Publication batch must contain at most 1000 facts.")
        seen = utc(retrieved_at)
        created = reused = observations = 0
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if checkpoint is not None:
                if not checkpoint.key or not checkpoint.source_identity or not 0 <= checkpoint.start <= checkpoint.offset:
                    raise ValueError("Invalid ingestion checkpoint.")
                prior = connection.execute("SELECT * FROM global_ingestion WHERE key=?", (checkpoint.key,)).fetchone()
                expected = prior["offset"] if prior and prior["source_identity"] == checkpoint.source_identity else 0
                if expected != checkpoint.start:
                    raise RuntimeError("Ingestion checkpoint advanced in another flight.")
                if prior and prior['source_identity'] != checkpoint.source_identity:
                    # Only abandoned, never-published staging records are discarded.
                    connection.execute('''DELETE FROM global_fact_revisions
                        WHERE published=0 AND publication_key=?''', (checkpoint.key,))
                    connection.execute('''DELETE FROM global_facts WHERE NOT EXISTS
                        (SELECT 1 FROM global_fact_revisions r WHERE r.fingerprint=global_facts.fingerprint)''')
            for count, fact in enumerate(facts, 1):
                if count > max_records:
                    raise ValueError("Publication exceeded bounded batch size.")
                body = fact.canonical()
                fingerprint = hashlib.sha256(body).hexdigest()
                head = connection.execute("""SELECT r.fingerprint FROM global_fact_revisions r
                    JOIN global_facts f ON f.fingerprint=r.fingerprint
                    WHERE f.family=? AND f.subject_id=? AND f.provider=? AND f.source_record_id=?
                    ORDER BY r.observed_at DESC,r.known_at DESC,r.fingerprint DESC LIMIT 1""",
                    (fact.family, fact.subject_id, fact.provider, fact.source_record_id)).fetchone()
                if head is not None and head[0] == fingerprint:
                    reused += 1
                    continue
                if observations == 0 and shutil.disk_usage(self.path.parent).free < self.reserve_bytes + max_records * 65536 * 2:
                    raise OSError("Insufficient disk admission for bounded global evidence publication.")
                exists = connection.execute("SELECT 1 FROM global_facts WHERE fingerprint=?", (fingerprint,)).fetchone()
                connection.execute('''INSERT OR IGNORE INTO global_facts
                    (fingerprint,family,subject_id,provider,source_record_id,effective_at,known_at,first_seen,payload,season)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                    fingerprint, fact.family, fact.subject_id, fact.provider,
                    fact.source_record_id, utc(fact.effective_at),
                    utc(fact.known_at) if fact.known_at else seen, seen, zlib.compress(body), fact.season,
                ))
                connection.execute('''INSERT OR IGNORE INTO global_fact_revisions
                    (fingerprint,known_at,observed_at,published,publication_key,publication_identity)
                    VALUES(?,?,?,?,?,?)''',
                    (fingerprint, utc(fact.known_at) if fact.known_at else seen, seen,
                     int(checkpoint is None), checkpoint.key if checkpoint else '',
                     checkpoint.source_identity if checkpoint else ''))
                observations += 1
                if exists:
                    reused += 1
                else:
                    created += 1
            if checkpoint is not None:
                if checkpoint.complete:
                    connection.execute('''UPDATE global_fact_revisions
                        SET published=1,publication_key='',publication_identity=''
                        WHERE published=0 AND publication_key=? AND publication_identity=?''',
                        (checkpoint.key, checkpoint.source_identity))
                connection.execute("""INSERT INTO global_ingestion VALUES(?,?,?,?)
                    ON CONFLICT(key) DO UPDATE SET source_identity=excluded.source_identity,
                    offset=excluded.offset,complete=excluded.complete""",
                    (checkpoint.key, checkpoint.source_identity, checkpoint.offset, int(checkpoint.complete)))
        return {"created": created, "reused": reused}

    def ingestion_checkpoint(self, key: str) -> dict[str, Any] | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute("SELECT * FROM global_ingestion WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None

    def record_source_check(self, key: str, *, source_identity: str | None,
                            checked_at: str, status: str, details: dict[str, Any]) -> None:
        """Replace one bounded freshness receipt, never append refresh snapshots."""
        if self.readonly:
            raise PermissionError("Read-only evidence cannot record source checks.")
        if status not in {'complete', 'partial', 'unavailable', 'failed'} or len(key) > 200:
            raise ValueError("Invalid source check.")
        allowed = {'records', 'source_rows', 'unresolved_rows', 'missing_game_times', 'source_bytes', 'reason'}
        if set(details) - allowed or any(not isinstance(v, (str, int, type(None))) for v in details.values()):
            raise ValueError("Unapproved source check detail.")
        body = json.dumps(details, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(body) > 2048 or (source_identity is not None and len(source_identity) > 200):
            raise ValueError("Source check exceeds bounded metadata contract.")
        stamp = utc(checked_at)
        with closing(self._connect()) as connection, connection:
            connection.execute('''INSERT INTO global_source_checks VALUES(?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET source_identity=excluded.source_identity,
                checked_at=excluded.checked_at,status=excluded.status,details=excluded.details
                WHERE global_source_checks.checked_at<=excluded.checked_at''',
                (key, source_identity, stamp, status, body))

    def source_check(self, key: str) -> dict[str, Any] | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute('SELECT * FROM global_source_checks WHERE key=?', (key,)).fetchone()
        return {**dict(row), 'details': json.loads(row['details'])} if row else None

    def read(self, family: str, subject_id: str | None, *, as_of: str, limit: int = 1000,
             season: int | None = None) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("Evidence read limit must be bounded.")
        if subject_id is None and (family != 'schedule' or season is None):
            raise ValueError('Family-wide reads require a bounded schedule season.')
        boundary = utc(as_of)
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute("""
                SELECT fingerprint,payload,known_at,first_seen FROM (
                    SELECT f.fingerprint,f.payload,r.known_at,r.observed_at AS first_seen,
                    ROW_NUMBER() OVER (
                        PARTITION BY f.provider,f.source_record_id
                        ORDER BY r.known_at DESC,r.observed_at DESC,f.fingerprint DESC
                    ) AS revision FROM global_facts f
                    JOIN global_fact_revisions r ON r.fingerprint=f.fingerprint
                    WHERE f.family=? AND (? IS NULL OR f.subject_id=?)
                    AND (? IS NULL OR f.season=?)
                    AND r.published=1
                    AND (f.effective_at<=? OR f.family='schedule') AND r.known_at<=?
                ) WHERE revision=1 ORDER BY known_at, fingerprint LIMIT ?
            """, (family, subject_id, subject_id, season, season, boundary, boundary, limit + 1)).fetchall()
        if len(rows) > limit:
            raise ValueError('Evidence result exceeds the requested bound; refusing silent truncation.')
        return [{**json.loads(zlib.decompress(row["payload"])),
                 "fingerprint": row["fingerprint"], "knowledge_boundary": row["known_at"],
                 "first_seen": row["first_seen"]} for row in rows]

    def counts(self) -> dict[str, int]:
        with closing(self._connect(readonly=True)) as connection:
            return {row[0]: row[1] for row in connection.execute(
                "SELECT family,COUNT(*) FROM global_facts GROUP BY family")}
