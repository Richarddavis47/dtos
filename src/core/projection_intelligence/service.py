"""Persisted, immutable projection snapshots built outside request paths."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from config import PROJECTION_DATABASE_FILE
from src.core.projection_intelligence.sleeper_provider import (
    PARSER_VERSION, SOURCE_CLASSIFICATION, freshness_state, parse_projection_feed,
)
from src.core.projection_intelligence.scoring import fantasy_points
from src.core.projection_intelligence.consumer_registry import projection_consumer_health

PROJECTION_SCHEMA_VERSION = "2.0"
PROJECTION_MODEL_VERSION = "sleeper-canonical-weekly-1"
PROJECTION_CONTRACT_VERSION = "2"
PROJECTION_SEMANTIC_POLICY_VERSION = "2"
PROVIDER_CACHE_SEASONS = 6


def snapshot_compatibility(snapshot: Any) -> tuple[str, str]:
    """Classify persisted metadata against the running projection contract."""
    if not isinstance(snapshot, dict):
        return "corrupt", "Projection snapshot payload is not an object."
    if str(snapshot.get("schema_version") or "") != PROJECTION_SCHEMA_VERSION:
        return "incompatible_schema", "Persisted projection schema differs from the required schema."
    if str(snapshot.get("model_version") or "") != PROJECTION_MODEL_VERSION:
        return "incompatible_model", "Persisted projection model differs from the required model."
    if (
        str(snapshot.get("contract_version") or "") != PROJECTION_CONTRACT_VERSION
        or str(snapshot.get("semantic_policy_version") or "")
        != PROJECTION_SEMANTIC_POLICY_VERSION
    ):
        return "incompatible_contract", "Persisted projection contract differs from the required contract."
    return "compatible", "Persisted projection snapshot matches the running contract."


class ProjectionInputError(ValueError):
    """A sanitized canonical-player input contract violation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _projection_semantics(players: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Retain only fields that can change canonical weekly decisions."""
    fields = (
        "player_id", "position", "team", "opponent", "season", "week",
        "provider_id", "scoring_profile_id", "canonical_projection",
        "availability", "availability_state", "projection_confidence",
        "source_freshness", "sleeper_evidence_fingerprint",
    )
    return {
        player_id: {field: row.get(field) for field in fields}
        for player_id, row in sorted(players.items())
    }


def provider_registry() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "sleeper_projections", "provider_name": "Sleeper Projection",
            "evidence_family": "optional_external_projection",
            "supported_projection_types": ["weekly", "projected_statistics"],
            "availability_state": "canonical", "licensing_state": "undocumented",
            "source_classification": SOURCE_CLASSIFICATION,
            "reason": "Canonical weekly fantasy projection evidence, evaluated with the requested league scoring profile.",
        },
        {
            "provider_id": "dtos_forward_production", "provider_name": "DTOS Forward Production Model",
            "evidence_family": "internal_forward_model",
            "supported_projection_types": ["weekly", "rest_of_season", "season", "floor", "median", "ceiling", "role"],
            "availability_state": "legacy_non_canonical", "licensing_state": "first_party",
            "reason": "Retained for rollback and research only; disconnected from every canonical production consumer.",
        },
        {
            "provider_id": "licensed_external_projection", "provider_name": "Licensed External Projection Provider",
            "evidence_family": "independent_projection", "supported_projection_types": ["weekly", "rest_of_season", "season"],
            "availability_state": "credentials_required", "licensing_state": "license_required",
            "reason": "Disabled until an approved licensed provider and credentials are configured.",
        },
    ]


class ProjectionService:
    def __init__(
        self,
        database_file: Path | None = None,
        *,
        league_id: str | None = None,
        scoring_profile_id: str | None = None,
    ) -> None:
        self._database_file = database_file or Path(PROJECTION_DATABASE_FILE)
        self._league_id = str(league_id) if league_id is not None else None
        self._scoring_profile_id = scoring_profile_id
        self._lock = threading.RLock()
        self._snapshot: dict[str, Any] | None = None
        self._generation_state = "pending"
        self._last_error_type: str | None = None
        self._last_error_message: str | None = None
        self._last_error_at: str | None = None
        self._last_success_at: str | None = None
        self._normalization: dict[str, Any] = {}
        self._generations = 0
        self._external_requests = 0
        self._external_bytes = 0
        self._external_failures = 0
        self._external_semantic_changes = 0
        self._external_no_change_refreshes = 0
        self._projection_refreshes = 0
        self._external_state = "Unavailable"
        self._external_last_attempt: str | None = None
        self._external_last_success: str | None = None
        self._external_fingerprint: str | None = None
        self._refreshing = False
        self._external_transport: dict[str, Any] = {}
        self._snapshot_restores = 0
        self._compatible_restores = 0
        self._incompatible_restores = 0
        self._restore_failures = 0
        self._upgrade_triggered_generations = 0
        self._provider_triggered_generations = 0
        self._failed_generations = 0
        self._durable_publications = 0
        self._compatibility = "missing"
        self._compatibility_reason = "No durable projection snapshot is available."
        self._restored_snapshot_identity: dict[str, Any] = {}
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self._database_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_file, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS projection_snapshots (snapshot_id TEXT PRIMARY KEY, league_id TEXT NOT NULL, season INTEGER NOT NULL, week INTEGER, generated_at TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS projection_actuals (snapshot_id TEXT NOT NULL, player_id TEXT NOT NULL, actual_points REAL NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(snapshot_id, player_id))")
            connection.execute("CREATE TABLE IF NOT EXISTS sleeper_projection_snapshots (fingerprint TEXT PRIMARY KEY, season INTEGER NOT NULL, week INTEGER NOT NULL, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.commit()
            if self._league_id is None:
                row = connection.execute(
                    "SELECT payload FROM projection_snapshots ORDER BY generated_at DESC LIMIT 1"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT payload FROM projection_snapshots WHERE league_id=? ORDER BY generated_at DESC LIMIT 1",
                    (self._league_id,),
                ).fetchone()
            external = connection.execute("SELECT fingerprint, retrieved_at FROM sleeper_projection_snapshots ORDER BY retrieved_at DESC LIMIT 1").fetchone()
        try:
            if row:
                restored = json.loads(row["payload"])
                self._snapshot_restores = 1
                self._restored_snapshot_identity = {
                    "schema_version": restored.get("schema_version"),
                    "model_version": restored.get("model_version"),
                    "contract_version": restored.get("contract_version"),
                    "semantic_policy_version": restored.get("semantic_policy_version"),
                    "snapshot_id": restored.get("projection_snapshot_id"),
                    "generated_at": restored.get("generated_at"),
                }
                self._compatibility, self._compatibility_reason = snapshot_compatibility(restored)
                self._restored_snapshot_identity["compatibility"] = self._compatibility
                self._restored_snapshot_identity["compatibility_reason"] = self._compatibility_reason
                if self._compatibility == "compatible":
                    self._snapshot = restored
                    self._generation_state = "ready"
                    self._last_success_at = restored.get("generated_at")
                    self._compatible_restores = 1
                else:
                    self._snapshot = None
                    self._generation_state = "warming"
                    self._incompatible_restores = 1
            if external:
                self._external_fingerprint = external["fingerprint"]
                self._external_last_success = external["retrieved_at"]
                self._external_state = freshness_state(external["retrieved_at"])
        except (TypeError, ValueError, json.JSONDecodeError):
            self._snapshot = None
            self._generation_state = "warming"
            self._restore_failures += 1
            self._compatibility = "corrupt"
            self._compatibility_reason = "Durable projection snapshot could not be decoded."

    def restore_into(self, data: dict[str, Any]) -> bool:
        """Publish the durable canonical snapshot into cached application state."""
        with self._lock:
            snapshot = self._snapshot
        if snapshot is None:
            return False
        snapshot_league = str(snapshot.get("league_id") or "")
        requested_league = str((data.get("league") or {}).get("league_id") or "")
        if requested_league and snapshot_league != requested_league:
            return False
        data["projection_intelligence"] = snapshot
        return True

    def _external_snapshot(
        self, *, season: int | None = None, week: int | None = None,
    ) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            if season is not None and week is not None:
                row = connection.execute(
                    "SELECT payload FROM sleeper_projection_snapshots WHERE season=? AND week=? "
                    "ORDER BY retrieved_at DESC LIMIT 1", (season, week),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT payload FROM sleeper_projection_snapshots ORDER BY retrieved_at DESC LIMIT 1"
                ).fetchone()
        return json.loads(row["payload"]) if row else None

    def begin_external_refresh(self) -> bool:
        """Claim the single-flight refresh slot."""
        with self._lock:
            if self._refreshing:
                return False
            self._refreshing = True
            self._external_last_attempt = _now()
            self._external_requests += 1
            return True

    def cached_weeks(self, season: int) -> tuple[int, ...]:
        """Return the bounded durable provider-week inventory without decoding payloads."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT week FROM sleeper_projection_snapshots "
                "WHERE season=? AND week BETWEEN 1 AND 18 ORDER BY week", (int(season),),
            ).fetchall()
        return tuple(int(row["week"]) for row in rows)

    def cache_sleeper_week(
        self, payload: Any, *, scoring: dict[str, Any], season: int, week: int,
    ) -> dict[str, Any]:
        """Persist one disposable provider week without publishing active state."""
        with self._lock:
            self._external_requests += 1
        rows, fingerprint, report = parse_projection_feed(
            payload, season=int(season), week=int(week), scoring=scoring,
        )
        snapshot = {
            "provider_id": "sleeper_projections", "source_classification": SOURCE_CLASSIFICATION,
            "parser_version": PARSER_VERSION, "season": int(season), "week": int(week),
            "retrieved_at": _now(), "semantic_fingerprint": fingerprint,
            "players": rows, "normalization": report,
        }
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO sleeper_projection_snapshots VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(fingerprint) DO UPDATE SET retrieved_at=excluded.retrieved_at, payload=excluded.payload",
                (fingerprint, int(season), int(week), snapshot["retrieved_at"],
                 json.dumps(snapshot, sort_keys=True, separators=(",", ":"))),
            )
            self._prune_provider_cache(connection)
            connection.commit()
        return {"week": int(week), "players": len(rows), "semantic_fingerprint": fingerprint}

    @staticmethod
    def _prune_provider_cache(connection: sqlite3.Connection) -> None:
        """Bound disposable evidence to one observation per week for six seasons."""
        connection.execute(
            "DELETE FROM sleeper_projection_snapshots WHERE fingerprint NOT IN ("
            "SELECT fingerprint FROM (SELECT fingerprint, ROW_NUMBER() OVER ("
            "PARTITION BY season, week ORDER BY retrieved_at DESC, fingerprint DESC"
            ") AS ordinal FROM sleeper_projection_snapshots) WHERE ordinal=1)"
        )
        seasons = connection.execute(
            "SELECT DISTINCT season FROM sleeper_projection_snapshots ORDER BY season DESC"
        ).fetchall()
        expired = [int(row["season"]) for row in seasons[PROVIDER_CACHE_SEASONS:]]
        if expired:
            connection.executemany(
                "DELETE FROM sleeper_projection_snapshots WHERE season=?",
                ((season,) for season in expired),
            )

    def fail_external_refresh(
        self, exc: Exception, *, transport_details: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._refreshing = False
            self._external_failures += 1
            self._external_state = "Stale" if self._external_fingerprint else "Unavailable"
            self._last_error_type = type(exc).__name__
            self._last_error_message = (
                str(exc) if isinstance(exc, (ProjectionInputError, ValueError, RuntimeError))
                else "Sleeper projection synchronization failed."
            )
            self._last_error_at = _now()
            if transport_details is not None:
                self._external_transport = dict(transport_details)

    def ingest_sleeper(
        self, payload: Any, *, data: dict[str, Any], league_id: str, season: int, week: int,
        response_bytes: int = 0,
        transport_details: dict[str, Any] | None = None,
    ) -> bool:
        """Persist immutable external evidence and regenerate only on semantic change."""
        scoring = data.get("scoring_settings") or (data.get("league") or {}).get("scoring_settings") or {}
        retrieved_at = _now()
        try:
            with self._lock:
                self._projection_refreshes += 1
            rows, fingerprint, report = parse_projection_feed(
                payload, season=season, week=week, scoring=scoring,
            )
            changed = fingerprint != self._external_fingerprint
            snapshot = {
                "provider_id": "sleeper_projections", "source_classification": SOURCE_CLASSIFICATION,
                "parser_version": PARSER_VERSION, "season": season, "week": week,
                "retrieved_at": retrieved_at, "semantic_fingerprint": fingerprint,
                "players": rows, "normalization": report,
            }
            with closing(self._connect()) as connection:
                connection.execute(
                    "INSERT INTO sleeper_projection_snapshots VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(fingerprint) DO UPDATE SET retrieved_at=excluded.retrieved_at, payload=excluded.payload",
                    (fingerprint, season, week, retrieved_at, json.dumps(snapshot, sort_keys=True, separators=(",", ":"))),
                )
                self._prune_provider_cache(connection)
                connection.commit()
            with self._lock:
                self._refreshing = False
                self._external_bytes += max(0, response_bytes)
                self._external_fingerprint = fingerprint
                self._external_last_success = retrieved_at
                self._external_state = "Fresh"
                self._external_transport = dict(transport_details or {})
                self._last_error_type = self._last_error_message = self._last_error_at = None
                if changed:
                    self._external_semantic_changes += 1
                else:
                    self._external_no_change_refreshes += 1
            upgrade_required = self._snapshot is None
            # Re-evaluate bounded canonical status on every background sync.
            # Stable semantics reuse the immutable snapshot ID and cause no
            # downstream Brain/Market invalidation.
            self.generate(
                data, league_id,
                trigger=(
                    "provider_change" if changed else
                    "model_upgrade" if upgrade_required else "canonical"
                ),
            )
            return changed
        except Exception as exc:
            self.fail_external_refresh(exc)
            raise

    @staticmethod
    def _players(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Normalize mapping or sequence containers into unique player rows."""
        found: dict[str, dict[str, Any]] = {}
        malformed = 0
        conflicts: list[str] = []
        duplicates = 0
        container = data.get("players")
        source_items: list[tuple[str | None, Any]]
        if container is None:
            source_items = []
            container_type = "absent"
        elif isinstance(container, dict):
            source_items = [(str(key), value) for key, value in container.items()]
            container_type = "mapping"
        elif isinstance(container, (list, tuple)):
            source_items = [(None, value) for value in container]
            container_type = "sequence"
        else:
            raise ProjectionInputError(
                "Projection player container must be a mapping or sequence."
            )
        for mapping_key, value in source_items:
            if not isinstance(value, dict):
                malformed += 1
                continue
            payload_id = str(value.get("id") or value.get("player_id") or "")
            player_id = payload_id or str(mapping_key or "")
            if mapping_key and payload_id and mapping_key != payload_id:
                conflicts.append(mapping_key)
                continue
            if not player_id:
                malformed += 1
                continue
            row = dict(value)
            row.setdefault("id", player_id)
            if player_id in found:
                duplicates += 1
            found[player_id] = {**found.get(player_id, {}), **row}
        for team in data.get("teams") or []:
            for player in team.get("players") or []:
                if not isinstance(player, dict):
                    malformed += 1
                    continue
                player_id = str(player.get("id") or player.get("player_id") or "")
                if player_id:
                    if player_id in found:
                        duplicates += 1
                    found[player_id] = {**found.get(player_id, {}), **player}
        if conflicts:
            raise ProjectionInputError(
                "Projection player mapping contained conflicting canonical identities."
            )
        if source_items and not found:
            raise ProjectionInputError(
                "Projection player container contained no valid player objects."
            )
        universe = data.get("relevant_player_universe") or {}
        allowed = {str(value) for value in universe.get("member_ids") or ()}
        if allowed:
            found = {key: value for key, value in found.items() if key in allowed}
        rostered = {
            str(player.get("id") or player.get("player_id"))
            for team in data.get("teams") or []
            for player in team.get("players") or []
            if isinstance(player, dict) and (player.get("id") or player.get("player_id"))
        }
        report = {
            "container_type": container_type,
            "source_records": len(source_items),
            "normalized_players": len(found),
            "malformed_records": malformed,
            "duplicate_references": duplicates,
            "identity_conflicts": len(conflicts),
            "rostered_players": len(rostered & set(found)),
            "free_agent_players": len(set(found) - rostered),
        }
        return [found[key] for key in sorted(found)], report

    @staticmethod
    def _availability(player: dict[str, Any], evidence: dict[str, Any] | None) -> str:
        status = str(
            player.get("injury_status") or player.get("status") or "unknown"
        ).strip().casefold()
        if status in {"out", "ir", "pup", "suspended", "inactive", "retired"}:
            return status
        if status in {"questionable", "doubtful", "active"}:
            return status
        if not str(player.get("team") or player.get("nfl_team") or "").strip():
            return "unsigned"
        if evidence is None:
            return "unavailable"
        return "unknown" if status in {"", "none"} else status

    @classmethod
    def _canonical_projection(
        cls, player: dict[str, Any], evidence: dict[str, Any] | None,
        *, season: int, week: int | None, scoring_profile_id: str,
        sleeper_freshness: str, evidence_fingerprint: str | None,
    ) -> dict[str, Any]:
        player_id = str(player.get("id") or player.get("player_id"))
        value = (evidence or {}).get("league_projection")
        projected = round(float(value), 2) if value is not None else None
        availability = cls._availability(player, evidence)
        state = "projected_zero" if projected == 0 else "projected" if projected is not None else "unavailable"
        confidence = (
            90 if projected is not None and sleeper_freshness == "Fresh" else
            70 if projected is not None and sleeper_freshness == "Aging" else
            45 if projected is not None else 0
        )
        return {
            "player_id": player_id,
            "position": str(player.get("position") or (evidence or {}).get("position") or "").upper(),
            "team": player.get("team") or player.get("nfl_team") or (evidence or {}).get("team"),
            "opponent": (evidence or {}).get("opponent"),
            "season": season, "week": week,
            "provider": "Sleeper", "provider_id": "sleeper_projections",
            "scoring_profile_id": scoring_profile_id,
            "canonical_projection": projected,
            "weekly_projected_points": projected,
            "weekly_median": projected,
            "expected_points_per_game": projected,
            "sleeper_projection": projected,
            # Compatibility aliases are read-only mirrors of the canonical value;
            # they are not independent DTOS forecasts.
            "dtos_projection": projected,
            "calibrated_dtos_projection": projected,
            "raw_dtos_projection": None,
            "projection_confidence": confidence,
            "projection_coverage": "available" if projected is not None else "unavailable",
            "availability": availability,
            "availability_state": state,
            "status": state,
            "sleeper_zero_state": "numeric_zero" if projected == 0 else "projected" if projected is not None else "missing",
            "source_timestamp": (evidence or {}).get("source_updated_at"),
            "source_freshness": sleeper_freshness,
            "sleeper_freshness": sleeper_freshness,
            "sleeper_evidence_fingerprint": evidence_fingerprint,
            "sources": ["sleeper_projections"],
            "legacy_projection_state": "non_canonical",
            "limitations": [] if projected is not None else ["Sleeper projection evidence is unavailable; DTOS does not fabricate a fallback."],
        }

    def generate(
        self, data: dict[str, Any], league_id: str, *, trigger: str = "canonical",
    ) -> dict[str, Any]:
        with self._lock:
            self._generation_state = "generating"
            if trigger == "model_upgrade":
                self._upgrade_triggered_generations += 1
            elif trigger == "provider_change":
                self._provider_triggered_generations += 1
        try:
            snapshot, normalization, published = self._generate(data, league_id)
        except Exception as exc:
            with self._lock:
                self._generation_state = "stale" if self._snapshot else "failed"
                self._failed_generations += 1
                self._last_error_type = type(exc).__name__
                self._last_error_message = (
                    str(exc) if isinstance(exc, ProjectionInputError)
                    else "Projection generation failed while processing canonical player data."
                )
                self._last_error_at = _now()
            raise
        with self._lock:
            self._snapshot = snapshot
            data["projection_intelligence"] = snapshot
            self._normalization = normalization
            self._generation_state = "ready"
            self._last_error_type = None
            self._last_error_message = None
            self._last_error_at = None
            self._last_success_at = snapshot.get("generated_at")
            self._generations += 1
            self._compatibility, self._compatibility_reason = snapshot_compatibility(snapshot)
            if published:
                self._durable_publications += 1
        return snapshot

    def _generate(
        self, data: dict[str, Any], league_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        league = data.get("league") or {}
        scoring = data.get("scoring_settings") or league.get("scoring_settings") or {}
        season = int(data.get("season") or league.get("season") or datetime.now().year)
        week_value = data.get("week") or data.get("leg")
        week = int(week_value) if week_value not in (None, "") else None
        players, normalization = self._players(data)
        external_snapshot = self._external_snapshot(season=season, week=week)
        external_players = (
            (external_snapshot or {}).get("players") or {}
            if (external_snapshot or {}).get("season") == season and (external_snapshot or {}).get("week") == week
            else {}
        )
        scoring_profile_id = self._scoring_profile_id or _digest(scoring)
        projections = {}
        sleeper_freshness = freshness_state((external_snapshot or {}).get("retrieved_at"))
        for player in players:
            player_id = str(player.get("id") or player.get("player_id"))
            evidence = external_players.get(player_id)
            if evidence is not None:
                evidence = {
                    **evidence,
                    "league_projection": fantasy_points(
                        evidence.get("projected_stats") or {}, scoring,
                        str(evidence.get("position") or player.get("position") or ""),
                    ),
                }
            projections[player_id] = self._canonical_projection(
                player, evidence, season=season, week=week,
                scoring_profile_id=scoring_profile_id,
                sleeper_freshness=sleeper_freshness,
                evidence_fingerprint=(external_snapshot or {}).get("semantic_fingerprint"),
            )
        identity = {
            "league_id": league_id, "season": season, "week": week,
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "model_version": PROJECTION_MODEL_VERSION,
            "contract_version": PROJECTION_CONTRACT_VERSION,
            "semantic_policy_version": PROJECTION_SEMANTIC_POLICY_VERSION,
            "scoring_profile_id": scoring_profile_id,
            "players": _projection_semantics(projections),
        }
        snapshot_id = _digest(identity)
        generated_at = _now()
        for projection in projections.values():
            projection["projection_snapshot_id"] = snapshot_id
            projection["generated_at"] = generated_at
        snapshot = {
            "schema_version": PROJECTION_SCHEMA_VERSION, "model_version": PROJECTION_MODEL_VERSION,
            "contract_version": PROJECTION_CONTRACT_VERSION,
            "semantic_policy_version": PROJECTION_SEMANTIC_POLICY_VERSION,
            "league_id": league_id, "season": season, "week": week, "generated_at": generated_at,
            "projection_snapshot_id": snapshot_id, "players": projections,
            "providers": provider_registry(), "scoring_settings": scoring,
            "scoring_profile_id": scoring_profile_id,
            "canonical_provider": "Sleeper",
            "legacy_production_projection_consumers": 0,
            "consumer_migration": projection_consumer_health(),
            "sleeper_evidence_snapshot_id": (external_snapshot or {}).get("semantic_fingerprint"),
        }
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection:
            existing = connection.execute("SELECT payload FROM projection_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
            existing_snapshot = None
            if existing:
                try:
                    candidate = json.loads(existing["payload"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    candidate = None
                if snapshot_compatibility(candidate)[0] == "compatible":
                    existing_snapshot = candidate
            published = existing_snapshot is None
            if existing_snapshot is not None:
                snapshot = existing_snapshot
            elif existing:
                connection.execute(
                    "UPDATE projection_snapshots SET league_id=?, season=?, week=?, generated_at=?, payload=? WHERE snapshot_id=?",
                    (league_id, season, week, generated_at, payload, snapshot_id),
                )
                connection.commit()
            else:
                connection.execute("INSERT INTO projection_snapshots VALUES (?, ?, ?, ?, ?, ?)", (snapshot_id, league_id, season, week, generated_at, payload))
                connection.commit()
        return snapshot, normalization, published

    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            return self._snapshot

    def player(self, player_id: str) -> dict[str, Any] | None:
        snapshot = self.snapshot()
        return (snapshot.get("players") or {}).get(str(player_id)) if snapshot else None

    def week_snapshot(self, week: int) -> dict[str, Any] | None:
        """Return a durable canonical week without provider access."""
        if not 1 <= int(week) <= 18:
            return None
        snapshot = self.snapshot()
        if snapshot and int(snapshot.get("week") or 0) == int(week):
            return snapshot
        league_id = self._league_id or str((snapshot or {}).get("league_id") or "")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM projection_snapshots WHERE league_id=? AND week=? "
                "ORDER BY generated_at DESC LIMIT 1", (league_id, int(week)),
            ).fetchone()
        if row:
            candidate = json.loads(row["payload"])
            if snapshot_compatibility(candidate)[0] == "compatible":
                return candidate
        if not snapshot:
            return None
        season = int(snapshot.get("season") or 0)
        external = self._external_snapshot(season=season, week=int(week))
        if not external:
            return None
        scoring = snapshot.get("scoring_settings") or {}
        scoring_profile_id = str(snapshot.get("scoring_profile_id") or _digest(scoring))
        source_players = snapshot.get("players") or {}
        evidence_players = external.get("players") or {}
        freshness = freshness_state(external.get("retrieved_at"))
        players: dict[str, Any] = {}
        for player_id, prior in source_players.items():
            evidence = evidence_players.get(player_id)
            if evidence is not None:
                evidence = {**evidence, "league_projection": fantasy_points(
                    evidence.get("projected_stats") or {}, scoring,
                    str(evidence.get("position") or prior.get("position") or ""),
                )}
            players[player_id] = self._canonical_projection(
                prior, evidence, season=season, week=int(week),
                scoring_profile_id=scoring_profile_id, sleeper_freshness=freshness,
                evidence_fingerprint=external.get("semantic_fingerprint"),
            )
        identity = {
            "league_id": league_id, "season": season, "week": int(week),
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "model_version": PROJECTION_MODEL_VERSION,
            "contract_version": PROJECTION_CONTRACT_VERSION,
            "semantic_policy_version": PROJECTION_SEMANTIC_POLICY_VERSION,
            "scoring_profile_id": scoring_profile_id,
            "players": _projection_semantics(players),
        }
        snapshot_id = _digest(identity)
        generated_at = str(external.get("retrieved_at") or _now())
        for projection in players.values():
            projection["projection_snapshot_id"] = snapshot_id
            projection["generated_at"] = generated_at
        return {
            **{key: snapshot.get(key) for key in (
                "schema_version", "model_version", "contract_version",
                "semantic_policy_version", "league_id", "scoring_settings",
                "scoring_profile_id", "canonical_provider",
                "legacy_production_projection_consumers",
            )},
            "season": season, "week": int(week), "generated_at": generated_at,
            "projection_snapshot_id": snapshot_id, "players": players,
            "sleeper_evidence_snapshot_id": external.get("semantic_fingerprint"),
        }

    def record_actual(self, snapshot_id: str, player_id: str, actual_points: float) -> None:
        with closing(self._connect()) as connection:
            connection.execute("INSERT OR IGNORE INTO projection_actuals VALUES (?, ?, ?, ?)", (snapshot_id, str(player_id), float(actual_points), _now()))
            connection.commit()

    def accuracy(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT a.actual_points, s.payload, a.player_id FROM projection_actuals a JOIN projection_snapshots s ON s.snapshot_id=a.snapshot_id").fetchall()
        errors: list[float] = []
        by_position: dict[str, list[float]] = {}
        by_week: dict[str, list[float]] = {}
        availability_misses = 0
        for row in rows:
            snapshot = json.loads(row["payload"])
            projection = (snapshot.get("players") or {}).get(row["player_id"]) or {}
            expected = projection.get("weekly_projected_points")
            if expected is not None:
                error = float(expected) - float(row["actual_points"])
                errors.append(error)
                by_position.setdefault(str(projection.get("position") or "Other"), []).append(error)
                by_week.setdefault(str(snapshot.get("week") or "unknown"), []).append(error)
            elif float(row["actual_points"]) != 0:
                availability_misses += 1
        def summarize(values: list[float]) -> float:
            return round(mean(abs(item) for item in values), 3)
        return {
            "samples": len(errors),
            "mae": summarize(errors) if errors else None,
            "median_absolute_error": round(median(abs(item) for item in errors), 3) if errors else None,
            "bias": round(mean(errors), 3) if errors else None,
            "rmse": round(mean(item * item for item in errors) ** .5, 3) if errors else None,
            "positional_mae": {key: summarize(values) for key, values in sorted(by_position.items())},
            "week_mae": {key: summarize(values) for key, values in sorted(by_week.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 99)},
            "availability_status_misses": availability_misses,
            "research_only": True,
        }

    def storage(self) -> dict[str, Any]:
        """Return bounded category counts and bytes without exposing local paths."""
        with closing(self._connect()) as connection:
            counts = {
                "raw_shared_provider_rows": int(connection.execute(
                    "SELECT COUNT(*) FROM sleeper_projection_snapshots"
                ).fetchone()[0]),
                "derived_scoring_profile_rows": int(connection.execute(
                    "SELECT COUNT(*) FROM projection_snapshots"
                ).fetchone()[0]),
                "actual_evaluation_rows": int(connection.execute(
                    "SELECT COUNT(*) FROM projection_actuals"
                ).fetchone()[0]),
            }
            payload_bytes = {
                "raw_shared_provider_bytes": int(connection.execute(
                    "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM sleeper_projection_snapshots"
                ).fetchone()[0]),
                "derived_scoring_profile_bytes": int(connection.execute(
                    "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM projection_snapshots"
                ).fetchone()[0]),
            }
        return {
            **counts, **payload_bytes,
            "database_bytes": self._database_file.stat().st_size if self._database_file.exists() else 0,
            "provider_cache_retention": {
                "seasons": PROVIDER_CACHE_SEASONS,
                "weeks_per_season": 18,
                "maximum_week_snapshots": PROVIDER_CACHE_SEASONS * 18,
                "classification": "disposable_provider_cache",
            },
            "legacy_projection_bytes": 0,
        }

    def health(self, *, include_accuracy: bool = True) -> dict[str, Any]:
        snapshot = self.snapshot()
        players = (snapshot or {}).get("players") or {}
        by_position: dict[str, int] = {}
        fallback_by_position: dict[str, int] = {}
        value_counts: dict[str, int] = {}
        available = 0
        for projection in players.values():
            available += projection.get("weekly_projected_points") is not None
            position = str(projection.get("position") or "Other")
            if projection.get("weekly_projected_points") is not None:
                by_position[position] = by_position.get(position, 0) + 1
                value = f"{float(projection['weekly_projected_points']):.2f}"
                value_counts[value] = value_counts.get(value, 0) + 1
            if projection.get("weekly_projected_points") is None:
                fallback_by_position[position] = fallback_by_position.get(position, 0) + 1
        state_counts: dict[str, int] = {}
        state_by_position: dict[str, dict[str, int]] = {}
        for row in players.values():
            state = str(row.get("availability_state") or "unavailable")
            position = str(row.get("position") or "Other")
            state_counts[state] = state_counts.get(state, 0) + 1
            position_states = state_by_position.setdefault(position, {})
            position_states[state] = position_states.get(state, 0) + 1
        player_specific = sum(
            state_counts.get(state, 0)
            for state in ("projected", "projected_zero")
        )
        externally_calibrated_fallbacks = sum(
            False
            for row in players.values()
        )
        projected = max(1, available)
        sleeper_differences = [
            abs(float(row["canonical_projection"]) - float(row["sleeper_projection"]))
            for row in players.values()
            if row.get("canonical_projection") is not None and row.get("sleeper_projection") is not None
        ]
        return {
            "status": self._generation_state, "generation_state": self._generation_state,
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "application_projection_schema": PROJECTION_SCHEMA_VERSION,
            "application_projection_model": PROJECTION_MODEL_VERSION,
            "application_projection_contract": PROJECTION_CONTRACT_VERSION,
            "application_projection_semantic_policy": PROJECTION_SEMANTIC_POLICY_VERSION,
            "active_snapshot_schema": (snapshot or {}).get("schema_version"),
            "active_snapshot_model": (snapshot or {}).get("model_version"),
            "active_snapshot_contract": (snapshot or {}).get("contract_version"),
            "active_snapshot_semantic_policy": (snapshot or {}).get("semantic_policy_version"),
            "active_snapshot_id": (snapshot or {}).get("projection_snapshot_id"),
            "active_snapshot_generated_at": (snapshot or {}).get("generated_at"),
            "compatibility": self._compatibility,
            "compatibility_reason": self._compatibility_reason,
            "restored_snapshot": dict(self._restored_snapshot_identity),
            "snapshot_id": (snapshot or {}).get("projection_snapshot_id"), "generated_at": (snapshot or {}).get("generated_at"),
            "canonical_provider": "Sleeper",
            "scoring_profile_id": (snapshot or {}).get("scoring_profile_id"),
            "legacy_production_projection_consumers": 0,
            "consumer_migration": projection_consumer_health(),
            "players": len(players), "projected_players": available, "coverage": round(available / len(players) * 100, 2) if players else 0,
            "generations": self._generations, "external_requests": self._external_requests,
            "snapshot_restores": self._snapshot_restores,
            "compatible_restores": self._compatible_restores,
            "incompatible_restores": self._incompatible_restores,
            "restore_failures": self._restore_failures,
            "upgrade_triggered_generations": self._upgrade_triggered_generations,
            "provider_triggered_generations": self._provider_triggered_generations,
            "failed_generations": self._failed_generations,
            "durable_publications": self._durable_publications,
            "external_bytes": self._external_bytes,
            "external_failures": self._external_failures,
            "external_semantic_changes": self._external_semantic_changes,
            "projection_refreshes": self._projection_refreshes,
            "projection_semantic_changes": self._external_semantic_changes,
            "projection_no_change_refreshes": self._external_no_change_refreshes,
            "projection_semantic_digest": (snapshot or {}).get(
                "projection_snapshot_id"
            ),
            "external_provider": {
                "status": self._external_state,
                "classification": SOURCE_CLASSIFICATION,
                "refreshing": self._refreshing,
                "last_attempt": self._external_last_attempt,
                "last_success": self._external_last_success,
                "semantic_fingerprint": self._external_fingerprint,
                "parser_version": PARSER_VERSION,
                "transport": dict(self._external_transport),
                "cached_weeks": list(self.cached_weeks(int((snapshot or {}).get("season") or datetime.now().year))),
            },
            "last_error_type": self._last_error_type,
            "last_error_message": self._last_error_message,
            "last_error_at": self._last_error_at,
            "last_success_at": self._last_success_at,
            "normalization": dict(self._normalization),
            "eligible_players": len(players),
            "skipped_players": self._normalization.get("malformed_records", 0),
            "stale_projections": 0 if self._generation_state == "ready" else len(players),
            "accuracy": self.accuracy() if include_accuracy else None,
            "providers": provider_registry(),
            "storage": self.storage(),
            "position_coverage": by_position,
            "projection_quality": {
                "player_specific_players": player_specific,
                "player_specific_rate": round(player_specific / projected * 100, 2),
                "externally_calibrated_fallback_players": externally_calibrated_fallbacks,
                "baseline_fallback_players": sum(fallback_by_position.values()),
                "baseline_fallback_rate": round(sum(fallback_by_position.values()) / projected * 100, 2),
                "fallback_by_position": fallback_by_position,
                "raw_projection_states": state_counts,
                "raw_projection_states_by_position": state_by_position,
                "missing_projection_players": len(players) - available,
                "unique_projection_values": len(value_counts),
                "repeated_value_concentration": round(sum(count for count in value_counts.values() if count > 1) / projected * 100, 2),
                "most_repeated_values": [
                    {"value": float(value), "count": count}
                    for value, count in sorted(value_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
                    if count > 1
                ],
                "mean_absolute_sleeper_difference": round(mean(sleeper_differences), 3) if sleeper_differences else None,
                "median_absolute_sleeper_difference": round(median(sleeper_differences), 3) if sleeper_differences else None,
                "meaningful_disagreements": sum(value >= 5 for value in sleeper_differences),
                "large_disagreements": sum(value >= 8 for value in sleeper_differences),
                "extreme_disagreements": sum(value >= 12 for value in sleeper_differences),
            },
        }


projection_service = ProjectionService()
