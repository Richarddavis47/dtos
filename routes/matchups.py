"""Matchup routes for DTOS.

This module is intentionally isolated from application startup. The router factory
receives shared DTOS helpers so the existing UI and data behavior remain unchanged.
"""
from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.matchup_intelligence import matchup_projection

EnsureFresh = Callable[[], Awaitable[None]]
RequireData = Callable[[], dict[str, Any]]
PageRenderer = Callable[[str, str], HTMLResponse]


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
            projected = matchup_projection(d, sides)
            if left["points"] == right["points"]:
                status = "Tied"
            else:
                status = "Live score"
            cards.append(
                f'<a class="matchup-card" href="/matchups/{escape(matchup_id)}">'
                f'<div class="matchup-label"><span class="matchup-number">Matchup {escape(matchup_id)}</span><span class="matchup-status">{status}</span></div>'
                f'<div class="versus"><div class="matchup-team"><div class="matchup-owner">{escape(left["owner"])}</div><h3>{escape(left["team"])}</h3><div class="record">{escape(left["record"])}</div><div class="score">{left["points"]:.2f}</div></div>'
                f'<div class="vs-mark">VS</div>'
                f'<div class="matchup-team right"><div class="matchup-owner">{escape(right["owner"])}</div><h3>{escape(right["team"])}</h3><div class="record">{escape(right["record"])}</div><div class="score">{right["points"]:.2f}</div></div></div>'
                f'<div class="matchup-footer"><span><b class="edge">Projected:</b> {projected["sides"][0]["projected"]:.1f}–{projected["sides"][1]["projected"]:.1f} ({escape(projected["status"])})</span><span><b>Largest edge:</b> {escape(projected["largest_advantage"])}</span></div></a>'
            )
        body = (
            f'<div class="section-title"><div><h2 style="margin:0">Week {d["week"]} Matchups</h2><div class="muted">Live Sleeper scoring and lineup comparison</div></div>'
            f'<span class="pill">{len(cards)} matchups</span></div><div class="matchup-grid">{"".join(cards)}</div>'
        )
        return page("Matchups", body)


    @router.get("/matchups/{matchup_id}", response_class=HTMLResponse)
    async def matchup_detail_page(matchup_id: str) -> HTMLResponse:
        await ensure_fresh()
        d = require_data()
        sides = d["matchups"].get(str(matchup_id))
        if not sides:
            raise HTTPException(status_code=404, detail="Matchup not found")
        if len(sides) < 2:
            return page("Matchup", f'<a class="back" href="/matchups">← All Matchups</a><div class="card"><h2>Matchup {escape(matchup_id)}</h2><p class="muted">Opponent assignment is not complete.</p></div>')
        left, right = sides[0], sides[1]
        projected = matchup_projection(d, sides)
        projection_summary = (
            f'<section class="card"><h3>Projected Starter Outlook · {escape(projected["status"])}</h3><div class="matchup-summary-grid">'
            f'<div class="metric"><b>{projected["sides"][0]["projected"]:.1f}</b><span>{escape(left["team"])} Projection</span></div>'
            f'<div class="metric"><b>{projected["sides"][1]["projected"]:.1f}</b><span>{escape(right["team"])} Projection</span></div>'
            f'<div class="metric"><b>{projected["sides"][0]["floor"]:.1f}–{projected["sides"][0]["ceiling"]:.1f}</b><span>{escape(left["team"])} Range</span></div>'
            f'<div class="metric"><b>{projected["sides"][1]["floor"]:.1f}–{projected["sides"][1]["ceiling"]:.1f}</b><span>{escape(right["team"])} Range</span></div>'
            f'<div class="metric"><b>{escape(projected["largest_advantage"])}</b><span>Largest Advantage</span></div>'
            f'<div class="metric"><b>{escape(projected["highest_volatility"])}</b><span>Highest Volatility</span></div>'
            f'<div class="metric"><b>{escape(projected["confidence"])}</b><span>Projection Confidence · {projected["missing"]} missing</span></div></div></section>'
        )
        margin = abs(float(left["points"]) - float(right["points"]))
        if left["points"] == right["points"]:
            headline = "Matchup is tied"
            hero_state = "tied-game"
            banner_state = "tied"
            left_score_state = right_score_state = ""
        elif left["points"] > right["points"]:
            headline = f'{left["team"]} leads by {margin:.2f}'
            hero_state = "leading-left"
            banner_state = "leading"
            left_score_state, right_score_state = "leading", "trailing"
        else:
            headline = f'{right["team"]} leads by {margin:.2f}'
            hero_state = "leading-right"
            banner_state = "leading"
            left_score_state, right_score_state = "trailing", "leading"
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

            left_html = (
                f'<div class="battle-player"><b>{escape(lp["name"])}</b><span>{escape(lp["position"])} · {escape(lp["nfl_team"] or "—")}</span></div>'
                f'<div class="battle-points">{left_points:.2f}</div><span class="battle-result">{left_result}</span>'
            ) if lp else '<div class="battle-player"><b>Vacant</b><span>No starter assigned</span></div><div class="battle-points">—</div><span class="battle-result">Vacant</span>'
            right_html = (
                f'<div class="battle-player"><b>{escape(rp["name"])}</b><span>{escape(rp["position"])} · {escape(rp["nfl_team"] or "—")}</span></div>'
                f'<div class="battle-points">{right_points:.2f}</div><span class="battle-result">{right_result}</span>'
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
                f'<div class="bench-player {lclass}"><b>{escape(lp["name"])}</b><span>{escape(lp["position"])} · {escape(lp.get("nfl_team") or "—")}</span><strong>{lpts:.2f}</strong></div>'
                if lp else '<div class="bench-player empty"><b>—</b><span>No bench player</span><strong>—</strong></div>'
            )
            right_player = (
                f'<div class="bench-player right {rclass}"><b>{escape(rp["name"])}</b><span>{escape(rp["position"])} · {escape(rp.get("nfl_team") or "—")}</span><strong>{rpts:.2f}</strong></div>'
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
            f'<div class="bench-total-card"><div class="bench-total-grid">'
            f'<div class="bench-total-side"><span>{escape(left["team"])} Bench</span><b>{left_bench_total:.2f}</b></div>'
            f'<div class="advantage-center">{escape(bench_edge)}</div>'
            f'<div class="bench-total-side right"><span>{escape(right["team"])} Bench</span><b>{right_bench_total:.2f}</b></div>'
            f'</div></div><div class="bench-compare">{("".join(bench_rows) if bench_rows else "<div class=\"muted\">No bench scoring available.</div>")}</div>'
        )
        top_scorer_text = f'{combined_top["name"]} · {combined_top["points"]:.2f}' if combined_top else "No points yet"
        body = (
            f'<a class="back" href="/matchups">← All Matchups</a>'
            f'<section class="matchup-hero {hero_state}"><div class="matchup-label"><span class="matchup-number">Week {d["week"]} · Matchup {escape(matchup_id)}</span><span class="matchup-status">Live Sleeper data</span></div>'
            f'<div class="scoreboard"><div class="scoreboard-side {left_score_state}"><div class="matchup-owner">{escape(left["owner"])}</div><div class="scoreboard-team">{escape(left["team"])}</div><div class="record">{escape(left["record"])}</div><div class="scoreboard-score">{left["points"]:.2f}</div></div>'
            f'<div class="vs-mark">VS</div><div class="scoreboard-side right {right_score_state}"><div class="matchup-owner">{escape(right["owner"])}</div><div class="scoreboard-team">{escape(right["team"])}</div><div class="record">{escape(right["record"])}</div><div class="scoreboard-score">{right["points"]:.2f}</div></div></div>'
            f'<div class="leader-banner {banner_state}"><b>{escape(headline)}</b></div>'
            f'<div class="live-share"><div class="live-share-head"><span>{escape(left["team"])} {left_share:.0f}%</span><span>Live score share</span><span>{escape(right["team"])} {right_share:.0f}%</span></div><div class="live-share-track"><div class="live-share-left" style="width:{left_share:.2f}%"></div><div class="live-share-right" style="width:{right_share:.2f}%"></div></div></div>'
            f'<div class="matchup-summary-grid"><div class="metric"><b>{margin:.2f}</b><span>Score Margin</span></div><div class="metric"><b>{len(left.get("lineup", []))}</b><span>{escape(left["owner"])} Starters</span></div><div class="metric"><b>{len(right.get("lineup", []))}</b><span>{escape(right["owner"])} Starters</span></div><div class="metric"><b>{escape(top_scorer_text)}</b><span>Top Starter</span></div></div>'
            f'<div class="advantage-strip"><div class="advantage-side"><span>{escape(left["team"])} Battle Wins</span><b>{left_battle_wins}</b></div><div class="advantage-center">{tied_battles} tied slots</div><div class="advantage-side right"><span>{escape(right["team"])} Battle Wins</span><b>{right_battle_wins}</b></div></div></section>'
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Starting Lineup Battles</span><span class="muted">Slot-by-slot live points</span></div><div class="battle-grid">{"".join(battles)}</div></section>'
            f'{projection_summary}'
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">Bench Comparison</span><span class="muted">Top 12 bench players, side by side</span></div>{bench_comparison_html}</section>'
        )
        return page(f'{left["team"]} vs {right["team"]}', body)

    return router
