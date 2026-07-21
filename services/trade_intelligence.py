"""Application-facing Trade Intelligence view assembly."""
from __future__ import annotations

from typing import Any

from src.core.intelligence import intelligence_orchestrator


def build_trade_center(data: dict[str, Any], active_roster_id: int | None = None) -> dict[str, Any]:
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    roster_id = active_roster_id if active_roster_id in valid_ids else int(teams[0].get("roster_id") or 0)
    active_team = next(team for team in teams if int(team.get("roster_id") or 0) == roster_id)
    intelligence = intelligence_orchestrator.analyze(data, roster_id)
    dossiers: tuple[Any, ...] = intelligence.trades
    return {"active_team": active_team, "teams": teams, "dossiers": dossiers, "unified_recommendation": intelligence.recommendation}
