"""Persisted, immutable projection snapshots built outside request paths."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from config import CACHE_FILE
from src.core.projection_intelligence.sleeper_provider import (
    PARSER_VERSION, SOURCE_CLASSIFICATION, freshness_state, parse_projection_feed,
)

PROJECTION_SCHEMA_VERSION = "1.1"
PROJECTION_MODEL_VERSION = "dtos-forward-production-2"


class ProjectionInputError(ValueError):
    """A sanitized canonical-player input contract violation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def provider_registry() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "sleeper_projections", "provider_name": "Sleeper Projection",
            "evidence_family": "optional_external_projection",
            "supported_projection_types": ["weekly", "projected_statistics"],
            "availability_state": "optional", "licensing_state": "undocumented",
            "source_classification": SOURCE_CLASSIFICATION,
            "reason": "Undocumented source; DTOS remains fully functional without it.",
        },
        {
            "provider_id": "dtos_forward_production", "provider_name": "DTOS Forward Production Model",
            "evidence_family": "internal_forward_model",
            "supported_projection_types": ["weekly", "rest_of_season", "season", "floor", "median", "ceiling", "role"],
            "availability_state": "enabled", "licensing_state": "first_party",
            "reason": "Deterministic model from cached canonical DTOS evidence; not a Sleeper projection.",
        },
        {
            "provider_id": "licensed_external_projection", "provider_name": "Licensed External Projection Provider",
            "evidence_family": "independent_projection", "supported_projection_types": ["weekly", "rest_of_season", "season"],
            "availability_state": "credentials_required", "licensing_state": "license_required",
            "reason": "Disabled until an approved licensed provider and credentials are configured.",
        },
    ]


class ProjectionService:
    def __init__(self, database_file: Path | None = None) -> None:
        self._database_file = database_file or Path(CACHE_FILE).with_name("dtos_projections.sqlite3")
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
        self._external_state = "Unavailable"
        self._external_last_attempt: str | None = None
        self._external_last_success: str | None = None
        self._external_fingerprint: str | None = None
        self._refreshing = False
        self._external_transport: dict[str, Any] = {}
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
            row = connection.execute("SELECT payload FROM projection_snapshots ORDER BY generated_at DESC LIMIT 1").fetchone()
            external = connection.execute("SELECT fingerprint, retrieved_at FROM sleeper_projection_snapshots ORDER BY retrieved_at DESC LIMIT 1").fetchone()
        if row:
            self._snapshot = json.loads(row["payload"])
            self._generation_state = "ready"
            self._last_success_at = self._snapshot.get("generated_at")
        if external:
            self._external_fingerprint = external["fingerprint"]
            self._external_last_success = external["retrieved_at"]
            self._external_state = freshness_state(external["retrieved_at"])

    def _external_snapshot(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
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
                    "INSERT OR IGNORE INTO sleeper_projection_snapshots VALUES (?, ?, ?, ?, ?)",
                    (fingerprint, season, week, retrieved_at, json.dumps(snapshot, sort_keys=True, separators=(",", ":"))),
                )
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
            if changed:
                self.generate(data, league_id)
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
    def _project(player: dict[str, Any], scoring: dict[str, Any], season: int, week: int | None) -> dict[str, Any]:
        player_id = str(player.get("id") or player.get("player_id"))
        position = str(player.get("position") or "").upper()
        bye = player.get("bye_week") == week and week is not None
        availability = str(player.get("injury_status") or player.get("status") or "active").casefold()
        unavailable = availability in {"out", "ir", "pup", "suspended", "inactive"}
        recent = [float(value) for value in (player.get("fantasy_points_history") or player.get("recent_points") or []) if value is not None]
        season_average = player.get("season_average") or player.get("fantasy_points_per_game")
        base = float(season_average) if season_average is not None else (mean(recent[-5:]) if recent else {"QB": 16, "RB": 10, "WR": 9.5, "TE": 7}.get(position, 5))
        reception = float(scoring.get("rec") or 0)
        te_premium = float(scoring.get("bonus_rec_te") or scoring.get("rec_te") or 0) if position == "TE" else 0
        pass_td = float(scoring.get("pass_td") or 4)
        multiplier = 1 + ((reception - .5) * .10 if position != "QB" else (pass_td - 4) * .05) + te_premium * .06
        median = None if bye else max(0.0, base * multiplier * (0 if unavailable else .72 if availability in {"doubtful", "questionable"} else 1))
        spread = max(3.0, (pstdev(recent[-5:]) if len(recent[-5:]) > 1 else (median or 0) * .35))
        confidence = max(20, min(82, 42 + len(recent[-5:]) * 7 - (20 if availability not in {"", "active", "none"} else 0)))
        games = max(0, 18 - int(week or 1))
        weekly = round(median, 2) if median is not None else None
        status = "bye" if bye else "unavailable" if unavailable else "fallback"
        return {
            "player_id": player_id, "position": position, "week": week, "season": season,
            "weekly_projected_points": weekly,
            "weekly_floor": round(max(0, median - spread), 2) if median is not None else None,
            "weekly_median": weekly,
            "weekly_ceiling": round(median + spread * 1.35, 2) if median is not None else None,
            "rest_of_season_points": round(median * games, 2) if median is not None else None,
            "rest_of_season_games": games,
            "season_projected_points": round(median * 17, 2) if median is not None else None,
            "expected_points_per_game": weekly,
            "expected_usage": "Observed recent production and canonical role proxy" if recent else "Low-information role prior",
            "expected_role": player.get("roster_slot") or player.get("depth_chart_order") or "Unknown",
            "projection_confidence": confidence, "projection_agreement": None,
            "projection_coverage": "available" if weekly is not None else status,
            "sources": ["dtos_forward_production"], "status": status,
            "availability": availability, "limitations": ["No approved live external projection feed is configured."],
        }

    def generate(self, data: dict[str, Any], league_id: str) -> dict[str, Any]:
        with self._lock:
            self._generation_state = "generating"
        try:
            snapshot, normalization = self._generate(data, league_id)
        except Exception as exc:
            with self._lock:
                self._generation_state = "stale" if self._snapshot else "failed"
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
        return snapshot

    def _generate(self, data: dict[str, Any], league_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        league = data.get("league") or {}
        scoring = data.get("scoring_settings") or league.get("scoring_settings") or {}
        season = int(data.get("season") or league.get("season") or datetime.now().year)
        week_value = data.get("week") or data.get("leg")
        week = int(week_value) if week_value not in (None, "") else None
        players, normalization = self._players(data)
        external_snapshot = self._external_snapshot()
        external_players = (
            (external_snapshot or {}).get("players") or {}
            if (external_snapshot or {}).get("season") == season and (external_snapshot or {}).get("week") == week
            else {}
        )
        projections = {}
        for player in players:
            player_id = str(player.get("id") or player.get("player_id"))
            projection = self._project(player, scoring, season, week)
            evidence = external_players.get(player_id)
            sleeper_value = (evidence or {}).get("league_projection")
            dtos_value = projection.get("weekly_projected_points")
            if sleeper_value is not None and dtos_value is not None:
                difference = round(float(dtos_value) - float(sleeper_value), 2)
                magnitude = abs(difference)
                agreement = "High" if magnitude <= 2 else "Moderate" if magnitude <= 5 else "Low"
                reliability = .35 if freshness_state((external_snapshot or {}).get("retrieved_at")) == "Fresh" else .2
                canonical = round(float(dtos_value) * (1 - reliability) + float(sleeper_value) * reliability, 2)
                projection.update({
                    "sleeper_projection": round(float(sleeper_value), 2),
                    "dtos_projection": dtos_value, "canonical_projection": canonical,
                    "projection_difference": difference,
                    "projection_difference_percent": round(difference / abs(float(sleeper_value)) * 100, 2) if sleeper_value else None,
                    "projection_agreement": agreement,
                    "sleeper_evidence_fingerprint": (external_snapshot or {}).get("semantic_fingerprint"),
                    "sleeper_freshness": freshness_state((external_snapshot or {}).get("retrieved_at")),
                    "sources": ["dtos_forward_production", "sleeper_projections"],
                    "weekly_projected_points": canonical,
                })
            else:
                projection.update({
                    "sleeper_projection": sleeper_value,
                    "dtos_projection": dtos_value,
                    "canonical_projection": dtos_value,
                    "projection_difference": None,
                    "sleeper_freshness": freshness_state((external_snapshot or {}).get("retrieved_at")),
                })
            projections[player_id] = projection
        identity = {"league_id": league_id, "season": season, "week": week, "model_version": PROJECTION_MODEL_VERSION, "scoring": scoring, "players": projections}
        snapshot_id = _digest(identity)
        generated_at = _now()
        for projection in projections.values():
            projection["projection_snapshot_id"] = snapshot_id
            projection["generated_at"] = generated_at
        snapshot = {
            "schema_version": PROJECTION_SCHEMA_VERSION, "model_version": PROJECTION_MODEL_VERSION,
            "league_id": league_id, "season": season, "week": week, "generated_at": generated_at,
            "projection_snapshot_id": snapshot_id, "players": projections,
            "providers": provider_registry(), "scoring_settings": scoring,
            "sleeper_evidence_snapshot_id": (external_snapshot or {}).get("semantic_fingerprint"),
        }
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection:
            existing = connection.execute("SELECT payload FROM projection_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
            if existing:
                snapshot = json.loads(existing["payload"])
            else:
                connection.execute("INSERT INTO projection_snapshots VALUES (?, ?, ?, ?, ?, ?)", (snapshot_id, league_id, season, week, generated_at, payload))
                connection.commit()
        return snapshot, normalization

    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            return self._snapshot

    def player(self, player_id: str) -> dict[str, Any] | None:
        snapshot = self.snapshot()
        return (snapshot.get("players") or {}).get(str(player_id)) if snapshot else None

    def record_actual(self, snapshot_id: str, player_id: str, actual_points: float) -> None:
        with closing(self._connect()) as connection:
            connection.execute("INSERT OR IGNORE INTO projection_actuals VALUES (?, ?, ?, ?)", (snapshot_id, str(player_id), float(actual_points), _now()))
            connection.commit()

    def accuracy(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT a.actual_points, s.payload, a.player_id FROM projection_actuals a JOIN projection_snapshots s ON s.snapshot_id=a.snapshot_id").fetchall()
        errors = []
        for row in rows:
            projection = (json.loads(row["payload"]).get("players") or {}).get(row["player_id"]) or {}
            expected = projection.get("weekly_projected_points")
            if expected is not None:
                errors.append(float(expected) - float(row["actual_points"]))
        return {"samples": len(errors), "mae": round(mean(abs(item) for item in errors), 3) if errors else None, "bias": round(mean(errors), 3) if errors else None, "rmse": round(mean(item * item for item in errors) ** .5, 3) if errors else None}

    def health(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        players = (snapshot or {}).get("players") or {}
        by_position: dict[str, int] = {}
        available = 0
        for projection in players.values():
            available += projection.get("weekly_projected_points") is not None
            position = str(projection.get("position") or "Other")
            if projection.get("weekly_projected_points") is not None:
                by_position[position] = by_position.get(position, 0) + 1
        return {
            "status": self._generation_state, "generation_state": self._generation_state,
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "snapshot_id": (snapshot or {}).get("projection_snapshot_id"), "generated_at": (snapshot or {}).get("generated_at"),
            "players": len(players), "projected_players": available, "coverage": round(available / len(players) * 100, 2) if players else 0,
            "generations": self._generations, "external_requests": self._external_requests,
            "external_bytes": self._external_bytes,
            "external_failures": self._external_failures,
            "external_semantic_changes": self._external_semantic_changes,
            "external_provider": {
                "status": self._external_state,
                "classification": SOURCE_CLASSIFICATION,
                "refreshing": self._refreshing,
                "last_attempt": self._external_last_attempt,
                "last_success": self._external_last_success,
                "semantic_fingerprint": self._external_fingerprint,
                "parser_version": PARSER_VERSION,
                "transport": dict(self._external_transport),
            },
            "last_error_type": self._last_error_type,
            "last_error_message": self._last_error_message,
            "last_error_at": self._last_error_at,
            "last_success_at": self._last_success_at,
            "normalization": dict(self._normalization),
            "eligible_players": len(players),
            "skipped_players": self._normalization.get("malformed_records", 0),
            "stale_projections": 0 if self._generation_state == "ready" else len(players),
            "accuracy": self.accuracy(), "providers": provider_registry(),
            "position_coverage": by_position,
        }


projection_service = ProjectionService()
