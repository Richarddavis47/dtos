"""Small immutable account-context contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LeagueMembership:
    account_id: str
    league_id: str
    sleeper_user_id: str
    roster_id: int | None
    status: str
    mapping_source: str
    league_name: str | None = None
    franchise_name: str | None = None
    season: int | None = None


@dataclass(frozen=True, slots=True)
class AccountContext:
    account_id: str
    username: str
    display_name: str
    sleeper_user_id: str | None
    sleeper_username: str | None
    sleeper_link_state: str | None
    active_league_id: str | None
    membership: LeagueMembership | None
    csrf_token: str
    session_id: str

    @property
    def controlled_roster_id(self) -> int | None:
        return self.membership.roster_id if self.membership else None
