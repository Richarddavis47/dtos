"""Sleeper-owned season-chain discovery with no calendar cutoff."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class SeasonReference:
    league_id: str
    season: int | None
    previous_league_id: str | None
    availability: str
    completeness: str
    reason: str | None = None


@dataclass(frozen=True)
class SeasonChain:
    current_league_id: str
    seasons: tuple[SeasonReference, ...]
    terminated: bool
    termination_reason: str

    @property
    def year_one(self) -> int | None:
        values = [row.season for row in self.seasons if row.season is not None]
        return min(values) if values else None

    def public(self) -> dict[str, Any]:
        return {
            "current_league_id": self.current_league_id,
            "year_one": self.year_one,
            "terminated": self.terminated,
            "termination_reason": self.termination_reason,
            "discoverable_seasons": len(self.seasons),
            "available_seasons": sum(row.availability == "available" for row in self.seasons),
            "unavailable_seasons": [row.season for row in self.seasons if row.availability != "available"],
            "seasons": [row.__dict__ for row in self.seasons],
        }


LeagueFetcher = Callable[[str], Awaitable[dict[str, Any] | None]]


async def discover_season_chain(
    current_league_id: str,
    fetch_league: LeagueFetcher,
    *,
    maximum_seasons: int = 100,
) -> SeasonChain:
    """Walk ``previous_league_id`` until Sleeper terminates the chain.

    The safety bound detects corruption/cycles; it is not a historical year cutoff.
    """
    league_id = str(current_league_id)
    seen: set[str] = set()
    rows: list[SeasonReference] = []
    for _ in range(maximum_seasons):
        if league_id in seen:
            return SeasonChain(str(current_league_id), tuple(rows), False, "cycle_detected")
        seen.add(league_id)
        try:
            league = await fetch_league(league_id)
        except Exception as exc:
            rows.append(SeasonReference(
                league_id, None, None, "unavailable", "unavailable",
                f"provider_error:{type(exc).__name__}",
            ))
            return SeasonChain(str(current_league_id), tuple(rows), False, "provider_unavailable")
        if not league:
            rows.append(SeasonReference(
                league_id, None, None, "unavailable", "unavailable",
                "league_object_unavailable",
            ))
            return SeasonChain(str(current_league_id), tuple(rows), False, "provider_unavailable")
        previous = str(league.get("previous_league_id") or "").strip() or None
        season_value = league.get("season")
        rows.append(SeasonReference(
            league_id=league_id,
            season=int(season_value) if str(season_value).isdigit() else None,
            previous_league_id=previous,
            availability="available",
            completeness="league_object",
        ))
        if previous is None:
            return SeasonChain(str(current_league_id), tuple(rows), True, "provider_chain_terminated")
        league_id = previous
    return SeasonChain(str(current_league_id), tuple(rows), False, "safety_bound_exceeded")
