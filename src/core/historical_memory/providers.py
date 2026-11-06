"""Approved historical player-data provider adapters."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from collections.abc import AsyncIterator
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
        rows: list[dict[str, Any]] = []
        async for batch in self.weekly_batches(season, 1000):
            rows.extend(batch)
        return rows

    async def weekly_batches(
        self, season: int, batch_size: int,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Stream and normalize a bounded number of provider rows at a time."""
        url = self.url_template.format(season=season)
        async with self.client.stream("GET", url) as response:
            response.raise_for_status()
            lines = response.aiter_lines()
            header_line = await anext(lines)
            fieldnames = next(csv.reader([header_line]))
            batch: list[dict[str, Any]] = []
            async for line in lines:
                if not line:
                    continue
                row = next(csv.DictReader([line], fieldnames=fieldnames))
                batch.append(normalize_nflverse_row(row))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch


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
    # Published nflverse schemas changed these names. Prefer the current field
    # when present (including explicit null); never silently backfill a null
    # current field from a conflicting legacy alias.
    aliases = {
        "interceptions": "passing_interceptions",
        "fumbles": "fumbles_total",
        "fumbles_lost": "fumbles_lost_total",
    }
    normalized_row = dict(row)
    for legacy, current in aliases.items():
        if current in row:
            normalized_row[legacy] = row[current]
    raw_stats = {
        key: _number(normalized_row.get(source))
        for key, source in {
            "pass_att": "attempts",
            "pass_cmp": "completions",
            "pass_yd": "passing_yards",
            "pass_td": "passing_tds",
            "pass_int": "interceptions",
            "pass_2pt": "passing_2pt_conversions",
            "pass_fd": "passing_first_downs",
            "pass_sack": "sacks_suffered",
            "pass_cmp_40p": "passing_40",
            "rush_40p": "rushing_40",
            "rec_40p": "receiving_40",
            "rush_att": "carries",
            "rush_yd": "rushing_yards",
            "rush_td": "rushing_tds",
            "rush_2pt": "rushing_2pt_conversions",
            "rush_fd": "rushing_first_downs",
            "rec": "receptions",
            "rec_yd": "receiving_yards",
            "rec_td": "receiving_tds",
            "rec_2pt": "receiving_2pt_conversions",
            "rec_fd": "receiving_first_downs",
            "rec_tgt": "targets",
            "rec_air_yd": "receiving_air_yards",
            "target_share": "target_share",
            "air_yards_share": "air_yards_share",
            "fumbles": "fumbles",
            "fumbles_lost": "fumbles_lost",
        }.items()
    }
    # Exact published counts only. Team-defense totals are not individual
    # player statistics, and 40-yard plays are not long-touchdown evidence.
    for key, source in {
        'fgm': 'fg_made', 'xpm': 'pat_made', 'fgm_0_19': 'fg_made_0_19',
        'fgm_20_29': 'fg_made_20_29', 'fgm_30_39': 'fg_made_30_39',
        'fgm_40_49': 'fg_made_40_49', 'fgm_50_59': 'fg_made_50_59',
        'fgm_60p': 'fg_made_60_', 'st_td': 'special_teams_tds',
        'kr_yd': 'kickoff_return_yards', 'pr_yd': 'punt_return_yards',
    }.items():
        raw_stats[key] = _number(row.get(source))
    upper = (raw_stats['fgm_50_59'], raw_stats['fgm_60p'])
    raw_stats['fgm_50p'] = sum(upper) if all(value is not None for value in upper) else None
    # A zero number of unsuccessful attempts is provable without equating the
    # provider's separate missed/blocked counters with Sleeper's miss category.
    # Positive unmatched attempts remain unsupported until that mapping is proven.
    for key, attempts, made in (('fgmiss', 'fg_att', 'fg_made'), ('xpmiss', 'pat_att', 'pat_made')):
        attempted, successful = _number(row.get(attempts)), _number(row.get(made))
        raw_stats[key] = 0 if attempted is not None and attempted >= 0 and attempted == successful else None
    return {
        "provider_player_id": row.get("player_id") or None,
        "provider_record_id": (
            f"{row.get('season')}:{row.get('week')}:{row.get('player_id')}"
        ),
        "season": _integer(row.get("season")),
        "week": _integer(row.get("week")),
        "season_type": row.get("season_type") or None,
        "game_id": row.get("game_id") or None,
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
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None
