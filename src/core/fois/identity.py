"""Canonical owner/franchise identity boundary for FOIS."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FranchiseIdentity:
    league_id: str
    franchise_id: str
    owner_id: str | None
    owner_name: str
    franchise_name: str


def identity_from_team(league_id: str, team: dict) -> FranchiseIdentity:
    roster_id = str(team.get("roster_id") or "")
    owner_id = team.get("owner_id") or team.get("user_id")
    return FranchiseIdentity(
        league_id,
        f"{league_id}:franchise:{roster_id}",
        str(owner_id) if owner_id is not None else None,
        str(team.get("owner") or "Unassigned"),
        str(team.get("team_name") or f"Team {roster_id}"),
    )
