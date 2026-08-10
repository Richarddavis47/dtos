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

PROJECTION_SCHEMA_VERSION = "1.0"
PROJECTION_MODEL_VERSION = "dtos-forward-production-1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def provider_registry() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "sleeper_projections", "provider_name": "Sleeper",
            "evidence_family": "projection", "supported_projection_types": [],
            "availability_state": "unsupported", "licensing_state": "not_documented",
            "reason": "No approved projection interface is documented by Sleeper.",
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
        self._error: str | None = None
        self._generations = 0
        self._external_requests = 0
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
            connection.commit()
            row = connection.execute("SELECT payload FROM projection_snapshots ORDER BY generated_at DESC LIMIT 1").fetchone()
        if row:
            self._snapshot = json.loads(row["payload"])

    @staticmethod
    def _players(data: dict[str, Any]) -> list[dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        for player in data.get("players") or []:
            player_id = str(player.get("id") or player.get("player_id") or "")
            if player_id:
                found[player_id] = player
        for team in data.get("teams") or []:
            for player in team.get("players") or []:
                player_id = str(player.get("id") or player.get("player_id") or "")
                if player_id:
                    found[player_id] = player
        return list(found.values())

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
        league = data.get("league") or {}
        scoring = data.get("scoring_settings") or league.get("scoring_settings") or {}
        season = int(data.get("season") or league.get("season") or datetime.now().year)
        week_value = data.get("week") or data.get("leg")
        week = int(week_value) if week_value not in (None, "") else None
        players = self._players(data)
        projections = {str(player.get("id") or player.get("player_id")): self._project(player, scoring, season, week) for player in players}
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
        }
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as connection:
            existing = connection.execute("SELECT payload FROM projection_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
            if existing:
                snapshot = json.loads(existing["payload"])
            else:
                connection.execute("INSERT INTO projection_snapshots VALUES (?, ?, ?, ?, ?, ?)", (snapshot_id, league_id, season, week, generated_at, payload))
                connection.commit()
        with self._lock:
            self._snapshot = snapshot
            self._error = None
            self._generations += 1
        return snapshot

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
            "status": "ready" if snapshot else "pending", "schema_version": PROJECTION_SCHEMA_VERSION,
            "snapshot_id": (snapshot or {}).get("projection_snapshot_id"), "generated_at": (snapshot or {}).get("generated_at"),
            "players": len(players), "projected_players": available, "coverage": round(available / len(players) * 100, 2) if players else 0,
            "generations": self._generations, "external_requests": self._external_requests,
            "last_error": self._error, "accuracy": self.accuracy(), "providers": provider_registry(), "position_coverage": by_position,
        }


projection_service = ProjectionService()
