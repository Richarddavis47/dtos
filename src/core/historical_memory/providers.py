"""Approved historical player-data provider adapters."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from src.core.historical_memory.season_state import SeasonClassification, SeasonState


@dataclass(frozen=True)
class ProviderCapabilities:
    weekly_game_logs: bool
    raw_box_scores: bool
    snaps: bool
    routes: bool
    targets: bool
    carries: bool
    air_yards: bool
    red_zone: bool
    availability: bool
    team_history: bool
    position_history: bool


class PlayerDataProvider(Protocol):
    name: str
    license: str
    capabilities: ProviderCapabilities

    async def weekly(self, season: int) -> list[dict[str, Any]]: ...


class NflverseProvider:
    """Free CC-BY-4.0 nflverse weekly player-stat adapter."""

    name = "nflverse"
    license = "CC-BY-4.0; attribution required"
    cost = "$0"
    update_frequency = "Nightly during the NFL season"
    capabilities = ProviderCapabilities(
        weekly_game_logs=True, raw_box_scores=True, snaps=False, routes=False,
        targets=True, carries=True, air_yards=True, red_zone=False,
        availability=False, team_history=True, position_history=True,
    )
    url_template = (
        "https://github.com/nflverse/nflverse-data/releases/download/"
        "stats_player/stats_player_week_{season}.csv"
    )

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def weekly(self, season: int) -> list[dict[str, Any]]:
        response = await self.client.get(self.url_template.format(season=season))
        response.raise_for_status()
        return [
            normalize_nflverse_row(row)
            for row in csv.DictReader(io.StringIO(response.text))
        ]


@dataclass(frozen=True)
class ProviderAvailability:
    status: str
    reason: str
    next_eligible_at: str | None = None


def classify_nflverse_404(
    season: SeasonClassification, *, prior_week_count: int = 0,
) -> ProviderAvailability:
    """Classify only nflverse weekly-file 404s; other HTTP errors remain errors."""
    if season.state == SeasonState.PRE_REGULAR:
        return ProviderAvailability(
            "pending",
            "The NFL regular season has not begun and nflverse has not published weekly player statistics.",
            season.next_eligible_at.isoformat() if season.next_eligible_at else None,
        )
    if season.state == SeasonState.FUTURE:
        return ProviderAvailability(
            "not_yet_available",
            "This future NFL season is not yet eligible for weekly player-stat enrichment.",
            season.next_eligible_at.isoformat() if season.next_eligible_at else None,
        )
    if season.state == SeasonState.UNSUPPORTED:
        return ProviderAvailability(
            "unsupported",
            "The requested season predates configured nflverse weekly-stat coverage.",
        )
    if season.state == SeasonState.ACTIVE and prior_week_count:
        return ProviderAvailability(
            "pending",
            "Previously imported current-season coverage exists; the provider snapshot is temporarily unpublished.",
        )
    return ProviderAvailability(
        "failed",
        "The nflverse weekly dataset is expected for this eligible season but returned HTTP 404.",
    )


def normalize_nflverse_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize provider CSV while preserving unavailable versus observed zero."""
    raw_stats = {
        key: _number(row.get(source))
        for key, source in {
            "pass_att": "attempts",
            "pass_cmp": "completions",
            "pass_yd": "passing_yards",
            "pass_td": "passing_tds",
            "pass_int": "interceptions",
            "rush_att": "carries",
            "rush_yd": "rushing_yards",
            "rush_td": "rushing_tds",
            "rec": "receptions",
            "rec_yd": "receiving_yards",
            "rec_td": "receiving_tds",
            "rec_tgt": "targets",
            "rec_air_yd": "receiving_air_yards",
            "fumbles": "fumbles",
            "fumbles_lost": "fumbles_lost",
        }.items()
    }
    return {
        "provider_player_id": row.get("player_id") or None,
        "provider_record_id": (
            f"{row.get('season')}:{row.get('week')}:{row.get('player_id')}"
        ),
        "season": _integer(row.get("season")),
        "week": _integer(row.get("week")),
        "season_type": row.get("season_type") or None,
        "nfl_team": row.get("recent_team") or row.get("team") or None,
        "opponent": row.get("opponent_team") or None,
        "position": row.get("position") or None,
        "raw_stats": raw_stats,
        "metric_status": {
            key: "unavailable" if value is None else "observed"
            for key, value in raw_stats.items()
        },
        "provider": "nflverse",
        "license": NflverseProvider.license,
        "confidence": 90,
    }


def _number(value: Any) -> float | None:
    if value in {None, "", "NA", "NaN"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None
