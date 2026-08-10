"""Optional, undocumented Sleeper projection evidence provider."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from src.core.projection_intelligence.scoring import fantasy_points

PROVIDER_ID = "sleeper_unofficial_projections"
SOURCE_CLASSIFICATION = "Sleeper Unofficial Projection Feed — Optional External Evidence"
PARSER_VERSION = "1.0"
ALLOWED_STATS = frozenset({
    "pass_yd", "pass_td", "pass_int", "pass_2pt", "rush_yd", "rush_td",
    "rush_2pt", "rec", "rec_yd", "rec_td", "rec_2pt", "fum_lost",
    "fgm", "fgmiss", "xpm", "xpmiss", "pts_std", "pts_half_ppr", "pts_ppr",
})


class SleeperProjectionSchemaError(ValueError):
    """A sanitized contract error from the undocumented source."""


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def parse_projection_feed(
    payload: Any, *, season: int, week: int, scoring: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], str, dict[str, int]]:
    """Validate and normalize one bulk weekly response without retaining raw payloads."""
    if not isinstance(payload, list):
        raise SleeperProjectionSchemaError("Sleeper projection response must be a list.")
    rows: dict[str, dict[str, Any]] = {}
    malformed = duplicates = 0
    for item in payload:
        if not isinstance(item, dict):
            malformed += 1
            continue
        player_id = str(item.get("player_id") or "")
        stats = item.get("stats")
        if not player_id or not isinstance(stats, dict):
            malformed += 1
            continue
        try:
            item_season = int(item.get("season"))
            item_week = int(item.get("week"))
        except (TypeError, ValueError):
            malformed += 1
            continue
        if item_season != season or item_week != week:
            malformed += 1
            continue
        normalized_stats: dict[str, float] = {}
        invalid = False
        for key in ALLOWED_STATS & stats.keys():
            try:
                normalized_stats[key] = float(stats[key])
            except (TypeError, ValueError):
                invalid = True
                break
        if invalid:
            malformed += 1
            continue
        position = str((item.get("player") or {}).get("position") or item.get("position") or "")
        displayed = stats.get("pts_ppr")
        row = {
            "player_id": player_id,
            "season": season,
            "week": week,
            "position": position,
            "team": item.get("team"),
            "opponent": item.get("opponent"),
            "projected_stats": normalized_stats,
            "displayed_projection": float(displayed) if displayed is not None else None,
            "league_projection": fantasy_points(normalized_stats, scoring, position),
            "source_company": item.get("company"),
            "source_updated_at": item.get("updated_at") or item.get("last_modified"),
        }
        if player_id in rows:
            duplicates += 1
        rows[player_id] = row
    if payload and not rows:
        raise SleeperProjectionSchemaError("Sleeper projection response contained no valid records.")
    fingerprint = _digest(rows)
    return rows, fingerprint, {
        "received": len(payload), "accepted": len(rows),
        "malformed": malformed, "duplicates": duplicates,
    }


@dataclass
class SleeperProjectionClient:
    """One-call bulk client; orchestration must invoke it only in background work."""

    base_url: str = "https://api.sleeper.app"
    enabled: bool = True

    async def fetch(
        self, client: httpx.AsyncClient, *, season: int, week: int,
    ) -> tuple[Any, int]:
        if not self.enabled:
            raise RuntimeError("Sleeper projection provider is disabled by its kill switch.")
        url = f"{self.base_url}/projections/nfl/{season}/{week}"
        response = await client.get(url, params=[
            ("season_type", "regular"), ("position[]", "QB"),
            ("position[]", "RB"), ("position[]", "WR"),
            ("position[]", "TE"), ("position[]", "FLEX"),
        ])
        response.raise_for_status()
        return response.json(), len(response.content)


def freshness_state(timestamp: str | None, *, now: datetime | None = None) -> str:
    if not timestamp:
        return "Unavailable"
    observed = datetime.fromisoformat(timestamp)
    age = (now or datetime.now(timezone.utc)) - observed
    if age <= timedelta(hours=1):
        return "Fresh"
    if age <= timedelta(hours=6):
        return "Aging"
    return "Stale"
