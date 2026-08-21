"""Matchup routes for DTOS.

This module is intentionally isolated from application startup. The router factory
receives shared DTOS helpers so the existing UI and data behavior remain unchanged.
"""
from __future__ import annotations

import asyncio
from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.matchup_intelligence import matchup_player_values, matchup_projection
from src.ui.intelligence_presentation import (
    league_is_preseason,
    matchup_game_state,
    matchup_score_hierarchy,
    matchup_state,
    projection_presentation_value,
)
from src.ui import player_summary

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


def _projection_value(value: Any) -> str:
    return f"{float(value):.2f}" if value is not None else "Unavailable"


def _starter_projection_html(row: dict[str, Any] | None) -> str:
    projection = row or {}
    sleeper = projection.get("canonical_projection")
    if sleeper is None:
        return (
            '<div class="starter-projections unavailable"><span>Projection unavailable</span>'
            '<details><summary>Technical Details</summary><small>No canonical Sleeper projection exists for this starter. DTOS does not fabricate a fallback.</small></details></div>'
        )
    technical = (
        f'<details><summary>Technical Details</summary><small>Provider: Sleeper. '
        f'Availability: {escape(str(projection.get("projection_availability") or "projected"))}. '
        f'Confidence: {escape(str(projection.get("projection_confidence") or "Unavailable"))}%. '
        f'DTOS consumes this league-scored value without blending a separate weekly forecast.</small></details>'
    )
    return (
        '<div class="starter-projections">'
        f'<span><small>Sleeper canonical projection</small><b>{_projection_value(sleeper)}</b></span>'
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

    return "".join(
        f'<div class="score-row {"primary" if index == 0 else "supporting"}"><small>{escape(label)}</small><b>{escape(display_value(label, value))}</b></div>'
        for index, (label, value) in enumerate(rows)
    )


def _has_team_projections(projected: dict[str, Any]) -> bool:
    sides = projected.get("sides") or []
    return len(sides) >= 2 and any(_team_projection_value(side) is not None for side in sides[:2])


def _team_projection_value(side: dict[str, Any]) -> Any | None:
    return projection_presentation_value(
        side.get("canonical_projection_total", side.get("sleeper_total")),
        side.get("canonical_projection_coverage", side.get("sleeper_coverage")),
    )


def create_matchups_router(
    *,
    ensure_fresh: EnsureFresh,
    require_data: RequireData,
    page: PageRenderer,
) -> APIRouter:
    """Create the matchups router using the application's shared dependencies."""
    router = APIRouter(tags=["matchups"])

    @router.get("/matchups", response_class=HTMLResponse)
    async def matchups_page() -> HTMLResponse:
        await ensure_fresh()
        d = require_data()
        player_values = await asyncio.to_thread(
            matchup_player_values,
            d,
            d["matchups"],
        )
        cards = []
        for matchup_id, sides in sorted(d["matchups"].items(), key=lambda item: (item[0] == "Unassigned", item[0])):
            if len(sides) < 2:
                side = sides[0] if sides else {"team": "Unassigned", "owner": "—", "points": 0, "record": "—"}
                cards.append(
                    f'<div class="matchup-card"><div class="matchup-label"><span class="matchup-number">Matchup {escape(matchup_id)}</span><span class="matchup-status">Waiting</span></div>'
                    f'<h3>{escape(side["team"])}</h3><div class="muted">Opponent not assigned</div></div>'
                )
                continue
            left, right = sides[0], sides[1]
            projected = matchup_projection(d, sides, player_values)
            projections_available = _has_team_projections(projected)
            projection_edge = (
                f'<span><b>Largest edge:</b> {escape(projected["largest_advantage"])}</span>'
                if projections_available else ""
            )
            game_state = _game_state(d, sides)
            status = matchup_state(
                left=float(left["points"]), right=float(right["points"]),
                week=int(d.get("week") or 0),
                season_started=not league_is_preseason(d),
            )
            cards.append(
                f'<a class="matchup-card" href="/matchups/{escape(matchup_id)}">'
                f'<div class="matchup-label"><span class="matchup-number">Matchup {escape(matchup_id)}</span><span class="matchup-status">{status}</span></div>'
                f'<div class="versus"><div class="matchup-team"><div class="matchup-owner">{escape(left["owner"])}</div><h3>{escape(left["team"])}</h3>{"" if game_state == "pregame" else f"<div class=\"record\">{escape(left['record'])}</div>"}{_team_score_html(actual=left["points"], projected=_team_projection_value(projected["sides"][0]), state=game_state)}</div>'
                f'<div class="vs-mark">VS</div>'
                f'<div class="matchup-team right"><div class="matchup-owner">{escape(right["owner"])}</div><h3>{escape(right["team"])}</h3>{"" if game_state == "pregame" else f"<div class=\"record\">{escape(right['record'])}</div>"}{_team_score_html(actual=right["points"], projected=_team_projection_value(projected["sides"][1]), state=game_state)}</div></div>'
                f'<div class="matchup-footer"><span><b class="edge">{escape(projected["status"] if projections_available else "Projection unavailable")}</b></span>'
                f'{projection_edge}</div></a>'
            )
        body = (
            f'<div class="section-title"><div><h2 style="margin:0">Week {d["week"]} Matchups</h2><div class="muted">Live Sleeper scoring and lineup comparison</div></div>'
            f'<span class="pill">{len(cards)} matchups</span></div><div class="matchup-grid">{"".join(cards)}</div>'
        )
        return page(f'Week {d["week"]} Matchups', body)


    @router.get("/matchups/{matchup_id}", response_class=HTMLResponse)
    async def matchup_detail_page(matchup_id: str) -> HTMLResponse:
        await ensure_fresh()
        d = require_data()
        sides = d["matchups"].get(str(matchup_id))
        if not sides:
            raise HTTPException(status_code=404, detail="Matchup not found")
        if len(sides) < 2:
            side_name = str(sides[0].get("team") or "Unassigned Franchise")
            return page(f"{side_name} — Matchup Awaiting Opponent", f'<a class="back" href="/matchups">← All Matchups</a><div class="card"><h2>{escape(side_name)}</h2><p class="muted">Opponent assignment is not complete. DTOS will update this page after Sleeper assigns both franchises.</p></div>')
        left, right = sides[0], sides[1]
        projected = matchup_projection(d, sides)
        projections_available = _has_team_projections(projected)
        game_state = _game_state(d, sides)
        projected_by_roster = {
            int(side.get("roster_id") or 0): {
                str(player.get("player_id")): player
                for player in side.get("players") or []
            }
            for side in projected.get("sides") or []
        }
        production_ranks = _production_ranks(d)
        projection_summary = (
            f'<section class="card"><h3>Canonical Sleeper Starter Projections</h3><div class="matchup-summary-grid">'
            f'<div class="metric"><b>{projected["sides"][0]["sleeper_total"]:.1f}</b><span>{escape(left["team"])} Sleeper Projection · {escape(projected["sides"][0]["sleeper_coverage"])} {escape(projected["sides"][0]["sleeper_status"])}</span></div>'
            f'<div class="metric"><b>{projected["sides"][1]["sleeper_total"]:.1f}</b><span>{escape(right["team"])} Sleeper Projection · {escape(projected["sides"][1]["sleeper_coverage"])} {escape(projected["sides"][1]["sleeper_status"])}</span></div>'
            f'</div></section>'
            f'<section class="card"><h3>Projected Starter Outlook · {escape(projected["status"])}</h3><div class="matchup-summary-grid">'
            f'<div class="metric"><b>{projected["sides"][0]["projected"]:.1f}</b><span>{escape(left["team"])} Projection</span></div>'
            f'<div class="metric"><b>{projected["sides"][1]["projected"]:.1f}</b><span>{escape(right["team"])} Projection</span></div>'
            f'<div class="metric"><b>{projected["sides"][0]["floor"]:.1f}–{projected["sides"][0]["ceiling"]:.1f}</b><span>{escape(left["team"])} Range</span></div>'
            f'<div class="metric"><b>{projected["sides"][1]["floor"]:.1f}–{projected["sides"][1]["ceiling"]:.1f}</b><span>{escape(right["team"])} Range</span></div>'
            f'<div class="metric"><b>{escape(projected["largest_advantage"])}</b><span>Largest Advantage</span></div>'
            f'<div class="metric"><b>{escape(projected["highest_volatility"])}</b><span>Highest Volatility</span></div>'
            f'<div class="metric"><b>{escape(projected["confidence"])}</b><span>Projection Confidence · {projected["missing"]} missing</span></div></div></section>'
        ) if projections_available else (
            '<section class="card evidence-unavailable"><h3>Pregame projections unavailable</h3>'
            '<p>Sleeper has not published canonical starter projections for this matchup. DTOS does not substitute zeroes or fabricate an outlook.</p></section>'
        )
        margin = abs(float(left["points"]) - float(right["points"]))
        if game_state == "pregame" and not projections_available:
            headline = "Pregame projections unavailable"
            hero_state = "not-started"
            banner_state = "upcoming"
        elif game_state == "pregame":
            favorite = left["team"] if projected["sides"][0]["projected"] > projected["sides"][1]["projected"] else right["team"] if projected["sides"][1]["projected"] > projected["sides"][0]["projected"] else "Even matchup"
            headline = f'{favorite} projected edge' if favorite != "Even matchup" else favorite
            hero_state = "not-started"
            banner_state = "upcoming"
        elif left["points"] == right["points"]:
            headline = "Matchup is tied"
            hero_state = "tied-game"
            banner_state = "tied"
        elif left["points"] > right["points"]:
            headline = f'{left["team"]} leads by {margin:.2f}'
            hero_state = "leading-left"
            banner_state = "leading"
        else:
            headline = f'{right["team"]} leads by {margin:.2f}'
            hero_state = "leading-right"
            banner_state = "leading"
        score_total = float(left["points"]) + float(right["points"])
        left_share = 50.0 if score_total <= 0 else (float(left["points"]) / score_total) * 100
        right_share = 100.0 - left_share
        left_top = max(left.get("lineup", []), key=lambda p: p["points"], default=None)
        right_top = max(right.get("lineup", []), key=lambda p: p["points"], default=None)
        combined_top = max([p for p in (left_top, right_top) if p], key=lambda p: p["points"], default=None)

        max_slots = max(len(left.get("lineup", [])), len(right.get("lineup", [])))
        battles = []
        left_battle_wins = 0
        right_battle_wins = 0
        tied_battles = 0
        for index in range(max_slots):
            lp = left.get("lineup", [])[index] if index < len(left.get("lineup", [])) else None
            rp = right.get("lineup", [])[index] if index < len(right.get("lineup", [])) else None
            slot = (lp or rp or {}).get("slot", "START")
            left_points = float(lp["points"]) if lp else 0.0
            right_points = float(rp["points"]) if rp else 0.0
            if lp and rp and left_points != right_points:
                left_state = "winning" if left_points > right_points else "losing"
                right_state = "winning" if right_points > left_points else "losing"
                left_result = "Winning" if left_points > right_points else "Trailing"
                right_result = "Winning" if right_points > left_points else "Trailing"
                if left_points > right_points:
                    left_battle_wins += 1
                else:
                    right_battle_wins += 1
            else:
                left_state = "tied"
                right_state = "tied"
                left_result = right_result = "Tied"
                tied_battles += 1
            if not lp:
                left_state += " vacant"
                left_result = "Vacant"
            if not rp:
                right_state += " vacant"
                right_result = "Vacant"

            left_score_rows = _team_score_html(actual=left_points, projected=(projected_by_roster.get(int(left.get("roster_id") or 0), {}).get(str(lp.get("id"))) or {}).get("canonical_projection"), state=game_state)
            right_score_rows = _team_score_html(actual=right_points, projected=(projected_by_roster.get(int(right.get("roster_id") or 0), {}).get(str(rp.get("id"))) or {}).get("canonical_projection"), state=game_state)
            left_html = (
                f'<div class="battle-player">{player_summary(player_id=str(lp.get("id") or ""), name=str(lp["name"]), position=str(lp.get("position") or ""), nfl_team=str(lp.get("nfl_team") or "—"), context=production_ranks.get(str(lp.get("id") or "")))}</div>'
                f'<div class="battle-points">{left_score_rows}</div>'
                f'{"" if game_state == "pregame" else f"<span class=\"battle-result\">{left_result}</span>"}'
            ) if lp else '<div class="battle-player"><b>Vacant</b><span>No starter assigned</span></div><div class="battle-points">—</div><span class="battle-result">Vacant</span>'
            right_html = (
                f'<div class="battle-player">{player_summary(player_id=str(rp.get("id") or ""), name=str(rp["name"]), position=str(rp.get("position") or ""), nfl_team=str(rp.get("nfl_team") or "—"), context=production_ranks.get(str(rp.get("id") or "")))}</div>'
                f'<div class="battle-points">{right_score_rows}</div>'
                f'{"" if game_state == "pregame" else f"<span class=\"battle-result\">{right_result}</span>"}'
            ) if rp else '<div class="battle-player"><b>Vacant</b><span>No starter assigned</span></div><div class="battle-points">—</div><span class="battle-result">Vacant</span>'
            if left_points > right_points:
                edge_label = f'{left["owner"]} edge'
                edge_class = 'good'
            elif right_points > left_points:
                edge_label = f'{right["owner"]} edge'
                edge_class = 'warn'
            else:
                edge_label = 'Even battle'
                edge_class = 'tie'
            left_top_class = " top-performer" if lp and combined_top and lp.get("name") == combined_top.get("name") and float(lp.get("points", 0) or 0) == float(combined_top.get("points", 0) or 0) and float(combined_top.get("points", 0) or 0) > 0 else ""
            right_top_class = " top-performer" if rp and combined_top and rp.get("name") == combined_top.get("name") and float(rp.get("points", 0) or 0) == float(combined_top.get("points", 0) or 0) and float(combined_top.get("points", 0) or 0) > 0 else ""
            battle_top_class = " top-battle" if left_top_class or right_top_class else ""
            battles.append(
                f'<div class="battle-card{battle_top_class}"><h3>{escape(slot)}</h3><div class="battle-head">'
                f'<div class="battle-side {left_state}{left_top_class}"><div class="battle-owner">{escape(left["owner"])}</div>{left_html}</div>'
                f'<div class="battle-vs">VS</div>'
                f'<div class="battle-side right {right_state}{right_top_class}"><div class="battle-owner">{escape(right["owner"])}</div>{right_html}</div>'
                f'</div><span class="edge-badge {edge_class}">{escape(edge_label)}</span></div>'
            )

        left_bench = list(left.get("bench", []))[:12]
        right_bench = list(right.get("bench", []))[:12]
        left_bench_total = sum(float(p.get("points", 0) or 0) for p in left_bench)
        right_bench_total = sum(float(p.get("points", 0) or 0) for p in right_bench)
        bench_rows = []
        for index in range(max(len(left_bench), len(right_bench))):
            lp = left_bench[index] if index < len(left_bench) else None
            rp = right_bench[index] if index < len(right_bench) else None
            lpts = float(lp.get("points", 0) or 0) if lp else 0.0
            rpts = float(rp.get("points", 0) or 0) if rp else 0.0
            lclass = 'leading' if lp and lpts > rpts else ('trailing' if lp and lpts < rpts else '')
            rclass = 'leading' if rp and rpts > lpts else ('trailing' if rp and rpts < lpts else '')
            left_player = (
                f'<div class="bench-player {lclass}"><b>{escape(lp["name"])}</b><span>{escape(lp["position"])} · {escape(lp.get("nfl_team") or "—")}</span><strong>{lpts:.2f}</strong>{_starter_projection_html(projected_by_roster.get(int(left.get("roster_id") or 0), {}).get(str(lp.get("id"))))}</div>'
                if lp else '<div class="bench-player empty"><b>—</b><span>No bench player</span><strong>—</strong></div>'
            )
            right_player = (
                f'<div class="bench-player right {rclass}"><b>{escape(rp["name"])}</b><span>{escape(rp["position"])} · {escape(rp.get("nfl_team") or "—")}</span><strong>{rpts:.2f}</strong>{_starter_projection_html(projected_by_roster.get(int(right.get("roster_id") or 0), {}).get(str(rp.get("id"))))}</div>'
                if rp else '<div class="bench-player right empty"><b>—</b><span>No bench player</span><strong>—</strong></div>'
            )
            bench_rows.append(f'<div class="bench-row">{left_player}<div class="bench-vs">VS</div>{right_player}</div>')

        if left_bench_total > right_bench_total:
            bench_edge = f'{left["team"]} bench +{left_bench_total-right_bench_total:.2f}'
        elif right_bench_total > left_bench_total:
            bench_edge = f'{right["team"]} bench +{right_bench_total-left_bench_total:.2f}'
        else:
            bench_edge = 'Bench scoring tied'
        bench_comparison_html = (
            '<div class="evidence-unavailable"><b>Bench scoring has not started.</b><br>Pregame starter projections are the decision evidence for this matchup.</div>'
            if game_state == "pregame" else
            f'<div class="bench-total-card"><div class="bench-total-grid">'
            f'<div class="bench-total-side"><span>{escape(left["team"])} Bench</span><b>{left_bench_total:.2f}</b></div>'
            f'<div class="advantage-center">{escape(bench_edge)}</div>'
            f'<div class="bench-total-side right"><span>{escape(right["team"])} Bench</span><b>{right_bench_total:.2f}</b></div>'
            f'</div></div><div class="bench-compare">{("".join(bench_rows) if bench_rows else "<div class=\"muted\">No bench scoring available.</div>")}</div>'
        )
        top_scorer_text = f'{combined_top["name"]} · {combined_top["points"]:.2f}' if combined_top else "No points yet"
        storyline = (
            "Sleeper has not published enough canonical starter projections to compare these lineups yet."
            if not projections_available else
            f'{left["team"]} has the stronger pregame projection, while {right["team"]} can close the gap through the highlighted lineup battles.'
            if projected["sides"][0]["projected"] > projected["sides"][1]["projected"] else
            f'{right["team"]} has the stronger pregame projection, while {left["team"]} can close the gap through the highlighted lineup battles.'
            if projected["sides"][1]["projected"] > projected["sides"][0]["projected"] else
            "The available pregame projections are even; lineup execution is the clearest differentiator."
        )
        hero_scores = (
            f'<div class="scoreboard"><div class="scoreboard-side"><div class="matchup-owner">{escape(left["owner"])}</div><div class="scoreboard-team">{escape(left["team"])}</div>{_team_score_html(actual=left["points"], projected=_team_projection_value(projected["sides"][0]), state=game_state)}</div>'
            f'<div class="vs-mark">VS</div><div class="scoreboard-side right"><div class="matchup-owner">{escape(right["owner"])}</div><div class="scoreboard-team">{escape(right["team"])}</div>{_team_score_html(actual=right["points"], projected=_team_projection_value(projected["sides"][1]), state=game_state)}</div></div>'
        )
        live_context = "" if game_state == "pregame" else (
            f'<div class="live-share"><div class="live-share-head"><span>{escape(left["team"])} {left_share:.0f}%</span><span>Live score share</span><span>{escape(right["team"])} {right_share:.0f}%</span></div><div class="live-share-track"><div class="live-share-left" style="width:{left_share:.2f}%"></div><div class="live-share-right" style="width:{right_share:.2f}%"></div></div></div>'
        )
        battle_summary = "" if game_state == "pregame" else (
            f'<div class="advantage-strip"><div class="advantage-side"><span>{escape(left["team"])} Battle Wins</span><b>{left_battle_wins}</b></div><div class="advantage-center">{tied_battles} tied slots</div><div class="advantage-side right"><span>{escape(right["team"])} Battle Wins</span><b>{right_battle_wins}</b></div></div>'
        )
        body = (
            f'<a class="back" href="/matchups">← All Matchups</a>'
            f'<section class="matchup-hero {hero_state}"><div class="matchup-label"><span class="matchup-number">Week {d["week"]} · Matchup {escape(matchup_id)}</span><span class="matchup-status">Live Sleeper data</span></div>'
            f'{hero_scores}'
            f'<div class="leader-banner {banner_state}"><b>{escape(headline)}</b></div>'
            f'{live_context}'
            f'<div class="matchup-summary-grid">{"" if game_state == "pregame" else f"<div class=\"metric\"><b>{margin:.2f}</b><span>Score Margin</span></div>"}<div class="metric"><b>{len(left.get("lineup", []))}</b><span>{escape(left["owner"])} Starters</span></div><div class="metric"><b>{len(right.get("lineup", []))}</b><span>{escape(right["owner"])} Starters</span></div>{"" if game_state == "pregame" else f"<div class=\"metric\"><b>{escape(top_scorer_text)}</b><span>Top Starter</span></div>"}</div>'
            f'{battle_summary}</section>'
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Starting Lineup Outlook</span><span class="muted">{"Pregame projections" if game_state == "pregame" else "Slot-by-slot live points"}</span></div><div class="battle-grid">{"".join(battles)}</div></section>'
            f'{projection_summary}'
            f'<section class="card"><h3>Balanced Storyline</h3><p>{escape(storyline)}</p><details><summary>Why?</summary><p class="muted">This storyline uses only the cached canonical starter projections and visible lineup evidence. It is not a calibrated win probability.</p></details></section>'
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Bench Comparison</span><span class="muted">Top 12 bench players, side by side</span></div>{bench_comparison_html}</section>'
        )
        return page(f'{left["team"]} vs {right["team"]} — Matchup', body)

    return router
