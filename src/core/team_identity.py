"""Canonical user-facing franchise identity resolution."""
from __future__ import annotations

from typing import Any


def canonical_team_name(team: dict[str, Any] | None) -> str:
    """Return the best public franchise identity without numbered fallbacks."""
    row = team or {}
    for key in ("team_name", "owner", "display_name", "franchise_name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "Unassigned Franchise"


def team_name_map(data: dict[str, Any]) -> dict[int, str]:
    return {
        int(team.get("roster_id") or 0): canonical_team_name(team)
        for team in data.get("teams") or ()
        if int(team.get("roster_id") or 0)
    }


def team_name_for(data: dict[str, Any], roster_id: int | str | None) -> str:
    try:
        key = int(roster_id or 0)
    except (TypeError, ValueError):
        key = 0
    return team_name_map(data).get(key, "Unassigned Franchise")
