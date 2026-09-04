"""Shared immutable request context for every intelligence provider."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .league_scope import scoped_evidence


@dataclass(frozen=True)
class IntelligenceContext:
    league_id: str
    active_roster_id: int
    league: dict[str, Any]
    roster: dict[str, Any]
    teams: tuple[dict[str, Any], ...]
    picks: tuple[dict[str, Any], ...]
    settings: dict[str, Any]
    opponents: tuple[dict[str, Any], ...]
    market: dict[str, Any]
    front_offices: tuple[dict[str, Any], ...]
    cached_data: dict[str, Any]
    user_preferences: dict[str, Any]
    snapshot_key: str


def build_context(data: dict[str, Any], roster_id: int, user_preferences: dict[str, Any] | None = None) -> IntelligenceContext:
    teams = tuple(data.get("teams") or ())
    roster = next((team for team in teams if int(team.get("roster_id") or 0) == roster_id), None)
    if roster is None:
        raise ValueError(f"Front Office {roster_id} is not available.")
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or "configured-league")
    settings = {**(data.get("league_settings") or {}), "roster_positions": league.get("roster_positions") or []}
    transactions = data.get("transactions") or []
    players_updated = str(data.get("players_fetched_at") or "")
    front_office_rows = scoped_evidence(data, "front_office_evidence").rows
    behavior_rows = scoped_evidence(data, "gm_behavioral_intelligence").rows
    front_office_generation = ",".join(sorted(
        str(row.get("semantic_identity") or "")
        for row in front_office_rows.values()
        if isinstance(row, dict)
    ))
    behavior_generation = ",".join(sorted(
        str(row.get("semantic_identity") or "")
        for row in behavior_rows.values()
        if isinstance(row, dict)
    ))
    market_generation = str(
        (data.get("market_data") or {}).get("generation")
        or (data.get("market_data") or {}).get("generated_at") or ""
    )
    snapshot_key = f"{league_id}:{roster_id}:{len(teams)}:{len(transactions)}:{players_updated}:{data.get('week', '')}:{front_office_generation}:{behavior_generation}:{market_generation}:{id(data)}"
    return IntelligenceContext(
        league_id, roster_id, league, roster, teams, tuple(roster.get("picks_owned") or ()), settings,
        tuple(team for team in teams if int(team.get("roster_id") or 0) != roster_id),
        {"players": data.get("players") or {}, "position_counts": data.get("position_counts") or {}},
        teams, data, dict(user_preferences or {}), snapshot_key,
    )
