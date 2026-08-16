"""Canonical owner/franchise identity boundary for FOIS."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from src.core.team_identity import canonical_team_name


@dataclass(frozen=True)
class FranchiseIdentity:
    league_id: str
    franchise_id: str
    owner_id: str | None
    owner_name: str
    franchise_name: str

    @property
    def gm_id(self) -> str:
        subject = self.owner_id or "unassigned"
        return f"{self.league_id}:gm:{subject}"

    def tenure_id(self, started_at: str) -> str:
        source = f"{self.league_id}|{self.franchise_id}|{self.gm_id}|{started_at}"
        return hashlib.sha256(source.encode()).hexdigest()[:24]


def identity_from_team(league_id: str, team: dict) -> FranchiseIdentity:
    roster_id = str(team.get("roster_id") or "")
    owner_id = team.get("owner_id") or team.get("user_id")
    return FranchiseIdentity(
        league_id,
        f"{league_id}:franchise:{roster_id}",
        str(owner_id) if owner_id is not None else None,
        str(team.get("owner") or "Unassigned"),
        canonical_team_name(team),
    )


def canonical_league_identity(league: dict) -> str:
    """Return the stable dynasty-chain namespace supplied by canonical context."""
    return str(
        league.get("root_league_id")
        or league.get("canonical_league_id")
        or league.get("league_id")
        or "configured-league"
    )
