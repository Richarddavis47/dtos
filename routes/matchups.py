"""Matchup routes for DTOS.

This module is intentionally isolated from application startup. The router factory
receives shared DTOS helpers so the existing UI and data behavior remain unchanged.
"""
from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from src.ui.intelligence_presentation import (
    league_is_preseason,
    matchup_game_state,
    matchup_score_hierarchy,
    projection_presentation_value,
)
from src.ui import player_summary
from services.matchup_season import season_week_view
from src.core.projection_intelligence import projection_service
from src.platform.league_context import current_league_context
from src.ui.matchup_season import render_season_week

_MATCHUP_CSS = (Path(__file__).resolve().parents[1] / 'static' / 'css' / 'matchups.css').read_text(encoding='utf-8')

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def _franchise_identity(side: dict[str, Any]) -> str:
    """Link only a known franchise; missing ownership must not become team zero."""
    label = escape(str(side.get("team") or "Franchise unavailable"))
    roster_id = str(side.get("roster_id") or "")
    if roster_id.isdecimal() and int(roster_id) > 0:
        return f'<a href="/teams/{int(roster_id)}">{label}</a>'
    return label


def _projection_value(value: Any) -> str:
    return f"{float(value):.2f}" if value is not None else "Unavailable"


def _projection_range(side: dict[str, Any]) -> str:
    floor, ceiling = side.get("floor"), side.get("ceiling")
    if floor is None or ceiling is None:
        return "Unavailable"
    return f"{floor:.1f}–{ceiling:.1f}"


def _battle_edge(*, state: str, left: Any, right: Any, left_name: str, right_name: str) -> tuple[str, str]:
    """Pregame compares projections; live/final callers supply actual scores."""
    if left is None or right is None:
        return ("Projection unavailable" if state == "pregame" else "Score unavailable", "unavailable")
    if left == right:
        return ("Even projected battle" if state == "pregame" else "Final tie" if state == "final" else "Even battle", "tie")
    winner = left_name if left > right else right_name
    suffix = "projected edge" if state == "pregame" else "wins" if state == "final" else "leads"
    return (f"{winner} {suffix}", "good" if left > right else "warn")


def _player_identity(player: dict[str, Any], context: str | None = None) -> str:
    identity = player_summary(player_id=str(player.get("id") or ""), name=str(player["name"]), position=player.get("position"), nfl_team=player.get("nfl_team"), context=context)
    player_id = str(player.get("id") or "")
    if not player_id or not all(c.isalnum() or c in {"-", "_"} for c in player_id):
        return identity
    return f'<a class="matchup-player-link" href="/players/{escape(player_id)}" aria-label="Open {escape(str(player["name"]))} player dossier">{identity}</a>'


def _starter_projection_html(row: dict[str, Any] | None) -> str:
    projection = row or {}
    sleeper = projection.get("canonical_projection")
    if sleeper is None:
        return (
            '<div class="starter-projections unavailable" data-dtos-semantic-field="pregame_projection" '
            'data-dtos-availability="unavailable"><span>Projection unavailable</span>'
            '<details><summary>Technical Details</summary><small>No canonical Sleeper projection exists for this starter. DTOS does not fabricate a fallback.</small></details></div>'
        )
    technical = (
        f'<details><summary>Technical Details</summary><small>Provider: Sleeper. '
        f'Availability: {escape(str(projection.get("projection_availability") or "projected"))}. '
        f'Confidence: {escape(str(projection.get("projection_confidence") if projection.get("projection_confidence") is not None else "Unavailable"))}%. '
        f'DTOS uses the unrounded league-scored total for intelligence; the displayed '
        f'player projection follows Sleeper web formatting where source-order evidence is available.</small></details>'
    )
    display = escape(str(projection.get("sleeper_web_display_projection") or _projection_value(sleeper)))
    return (
        '<div class="starter-projections" data-dtos-semantic-field="pregame_projection" '
        f'data-dtos-availability="available" data-dtos-value="{display}">'
        f'<span><small>Pregame projection</small><b>{display}</b></span>'
        f'</div>{technical}'
    )


def _production_ranks(data: dict[str, Any]) -> dict[str, str]:
    """Derive current league-scoring positional ranks from cached actual points."""
    if league_is_preseason(data):
        return {}
    by_position: dict[str, dict[str, float]] = {}
    for sides in (data.get("matchups") or {}).values():
        for side in sides:
            for group in ("lineup", "bench", "taxi", "reserve", "ir"):
                for player in side.get(group) or []:
                    player_id = str(player.get("id") or "")
                    position = str(player.get("position") or "").upper()
                    if player_id and position:
                        by_position.setdefault(position, {})[player_id] = float(player.get("points") or 0)
    result: dict[str, str] = {}
    for position, scores in by_position.items():
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        for rank, (player_id, _score) in enumerate(ordered, start=1):
            result[player_id] = f"{position} #{rank}"
    return result


def _game_state(data: dict[str, Any], sides: list[dict[str, Any]]) -> str:
    """Classify visible matchup scoring without interpreting absent points as play."""
    return matchup_game_state(data, sides)


def _team_score_html(*, actual: Any, projected: Any, state: str) -> str:
    rows = matchup_score_hierarchy(actual=actual, pregame=projected, state=state)
    def display_value(label: str, value: str) -> str:
        if "projection" not in label.casefold() or value == "Projection unavailable":
            return value
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return value

    rendered = []
    for index, (label, value) in enumerate(rows):
        displayed = display_value(label, value)
        semantic = ""
        if label == "Pregame projection":
            availability = "unavailable" if value == "Projection unavailable" else "available"
            value_attribute = "" if availability == "unavailable" else f' data-dtos-value="{escape(displayed)}"'
            semantic = (
                ' data-dtos-semantic-field="pregame_projection"'
                f' data-dtos-availability="{availability}"{value_attribute}'
            )
        rendered.append(
            f'<div class="score-row {"primary" if index == 0 else "supporting"}"{semantic}>'
            f'<small>{escape(label)}</small><b>{escape(displayed)}</b></div>'
        )
    return "".join(rendered)


def _has_team_projections(projected: dict[str, Any]) -> bool:
    sides = projected.get("sides") or []
    return len(sides) >= 2 and any(_team_projection_value(side) is not None for side in sides[:2])


def _team_projection_value(side: dict[str, Any]) -> Any | None:
    return projection_presentation_value(
        side.get("canonical_projection_total", side.get("sleeper_total")),
        side.get("canonical_projection_coverage", side.get("sleeper_coverage")),
    )


def _complete_team_projection(side: dict[str, Any]) -> bool:
    """Partial totals may be displayed with coverage, not compared as full teams."""
    coverage = str(side.get("canonical_projection_coverage", side.get("sleeper_coverage", "")))
    try:
        available, expected = map(int, coverage.split("/"))
    except (ValueError, TypeError):
        return False
    return expected > 0 and available == expected and _team_projection_value(side) is not None


def create_matchups_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """One prepared read boundary for every season/week; no analysis fallback."""
    router = APIRouter(tags=["matchups"])

    @router.get('/static/css/matchups.css', include_in_schema=False)
    async def matchup_styles() -> Response:
        return Response(_MATCHUP_CSS, media_type='text/css', headers={'Cache-Control': 'no-cache'})

    async def read_week(week: int | None) -> tuple[int, dict, dict]:
        await ensure_fresh()
        data = require_data()
        selected = week if isinstance(week, int) else int(data.get("week") or 1)
        context = current_league_context()
        service = context.projection if context else projection_service
        view = await asyncio.to_thread(season_week_view, data, selected, service)
        return selected, view, data

    @router.get("/matchups", response_class=HTMLResponse)
    async def matchups_page(week: int | None = Query(default=None, ge=1, le=18)) -> HTMLResponse:
        selected, view, _ = await read_week(week)
        return page(f"Week {selected} Matchups", render_season_week(view))

    @router.get("/matchups/{matchup_id}", response_class=HTMLResponse)
    async def matchup_detail_page(matchup_id: str, week: int | None = Query(default=None, ge=1, le=18)) -> HTMLResponse:
        selected, view, data = await read_week(week)
        if view["availability"] == "available" and view["opponents_locked"] and matchup_id not in view["groups"]:
            raise HTTPException(status_code=404, detail="Matchup not found in the selected week")
        from services.matchup_desk import matchup_desk
        from src.ui.matchup_season import render_desk
        desk = await asyncio.to_thread(matchup_desk, data, view, matchup_id)
        return page(f"Week {selected} Matchup", render_season_week(view, matchup_id=matchup_id) + render_desk(desk))

    return router
