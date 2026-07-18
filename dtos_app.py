"""DTOS v0.8.1 — modular Sleeper service migration."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from html import escape
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from config import SYNC_MINUTES
from services.sleeper import (
    LEAGUE_ID, STATE, ensure_data_fresh, load_cache, sync_sleeper, utcnow
)

async def ensure_fresh() -> None:
    await ensure_data_fresh()


async def background_sync() -> None:
    while True:
        await asyncio.sleep(SYNC_MINUTES * 60)
        await sync_sleeper()


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_cache()
    await sync_sleeper()
    task = asyncio.create_task(background_sync())
    yield
    task.cancel()


app = FastAPI(title="DTOS", version="0.7.0", lifespan=lifespan)


CSS = """
:root{--bg:#07111f;--panel:#101d2d;--line:#26374c;--text:#f5f7fb;--muted:#9fb0c6;--accent:#6ee7b7;--gold:#f5c451}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#07111f,#0b1727);color:var(--text);font-family:Inter,system-ui,-apple-system,sans-serif}
a{color:inherit;text-decoration:none}.wrap{max-width:1180px;margin:auto;padding:20px}.top{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:20px}
.brand h1{margin:0;font-size:28px}.brand p{margin:4px 0;color:var(--muted)}.btn{border:0;border-radius:10px;padding:11px 15px;background:var(--accent);color:#062018;font-weight:800;cursor:pointer}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.nav a{padding:9px 12px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:rgba(16,29,45,.94);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 10px 25px rgba(0,0,0,.15)}.card h2,.card h3{margin-top:0}.muted{color:var(--muted)}.good{color:var(--accent)}.warn{color:#fca5a5}
.stat{font-size:27px;font-weight:850}.team{margin-bottom:14px}.record{color:var(--gold);font-weight:800}.players{display:grid;gap:5px}.player{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid rgba(38,55,76,.65)}.starter{font-weight:800}.pill{font-size:12px;padding:3px 7px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.team-link{display:block;transition:transform .15s ease,border-color .15s ease}.team-link:hover{transform:translateY(-2px);border-color:#3d5877}.team-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.rank-badge{min-width:38px;height:38px;border-radius:12px;background:#182a40;border:1px solid var(--line);display:grid;place-items:center;font-weight:900;color:var(--gold)}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.metric{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:10px}.metric b{display:block;font-size:17px}.metric span{font-size:11px;color:var(--muted)}.roster-section{margin-top:18px}.section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.slot-label{font-size:12px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.back{display:inline-block;margin-bottom:14px;color:var(--accent)}.pick-year{margin-top:14px}.pick-list{display:grid;gap:7px}.pick-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 0;border-top:1px solid rgba(38,55,76,.65)}.pick-origin{font-size:12px;color:var(--muted)}.away{color:#fca5a5}

.identity-kicker{font-size:12px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.09em}.franchise-name{margin:3px 0 0}.owner-line{margin:8px 0 0;color:var(--muted)}
.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.summary-grid .metric{min-height:66px}.analytics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.analytics-card{background:linear-gradient(180deg,#122238,#0b1727);border:1px solid var(--line);border-radius:12px;padding:12px}.analytics-card b{display:block;font-size:18px}.analytics-card span{font-size:11px;color:var(--muted)}
.position-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}.position-count{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:9px;text-align:center}.position-count b{display:block;font-size:18px}.position-count span{font-size:11px;color:var(--muted)}
.position-block{margin-top:10px}.position-head{display:flex;justify-content:space-between;align-items:center;padding:8px 2px;color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.player-name{display:flex;align-items:center;gap:8px}.pos-dot{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px rgba(110,231,183,.10)}
.pick-row.own{border-left:3px solid var(--accent);padding-left:10px}.pick-row.acquired{border-left:3px solid #60a5fa;padding-left:10px}.pick-row.traded-away{border-left:3px solid #f87171;padding-left:10px}.pick-status{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.pick-status.own{color:var(--accent)}.pick-status.acquired{color:#93c5fd}.pick-status.away{color:#fca5a5}

.team-report{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.report-card{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:12px;padding:12px}.report-card .grade{font-size:26px;font-weight:900;color:var(--gold)}.report-card small{display:block;color:var(--muted);margin-top:4px}
.progress-row{margin-top:10px}.progress-label{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;margin-bottom:5px}.progress-track{height:8px;background:#07111f;border:1px solid var(--line);border-radius:999px;overflow:hidden}.progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),#60a5fa);border-radius:999px}
details.pick-year{margin-top:12px}.pick-summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;background:#101d2d;border:1px solid var(--line);border-radius:12px;padding:12px 14px}.pick-summary::-webkit-details-marker{display:none}.pick-summary:after{content:"＋";color:var(--accent);font-size:18px}.pick-year[open] .pick-summary:after{content:"−"}.pick-year .pick-list{border-top-left-radius:0;border-top-right-radius:0;margin-top:-1px}
.sleeper-lineup{display:grid;gap:8px}.lineup-row{display:grid;grid-template-columns:56px 1fr;gap:8px;align-items:stretch}.lineup-slot{display:grid;place-items:center;background:#0b1727;border:1px solid var(--line);border-radius:10px;font-size:11px;font-weight:900;color:var(--accent)}.lineup-player{display:flex;justify-content:space-between;align-items:center;gap:10px;background:#101d2d;border:1px solid var(--line);border-radius:10px;padding:10px 12px}.lineup-player b{font-size:14px}.lineup-meta{font-size:11px;color:var(--muted);text-align:right}.lineup-empty{color:var(--muted);font-style:italic}
.owner-primary{font-size:13px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.08em}.franchise-secondary{color:var(--muted);font-size:13px;margin-top:3px}

.matchup-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.matchup-card{display:block;background:linear-gradient(180deg,#122238,#0d1a2a);border:1px solid var(--line);border-radius:16px;padding:16px;transition:transform .15s ease,border-color .15s ease}.matchup-card:hover{transform:translateY(-2px);border-color:#3d5877}.matchup-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.matchup-number{font-size:12px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.08em}.matchup-status{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:4px 8px}.versus{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.matchup-team{text-align:left}.matchup-team.right{text-align:right}.matchup-team h3{margin:3px 0 2px;font-size:18px}.matchup-owner{font-size:12px;color:var(--muted)}.score{font-size:30px;font-weight:900;margin-top:8px}.vs-mark{color:var(--muted);font-size:12px;font-weight:900}.matchup-footer{display:flex;justify-content:space-between;gap:10px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}.edge{color:var(--gold);font-weight:900}.matchup-hero{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:16px;padding:18px}.scoreboard{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.scoreboard-side.right{text-align:right}.scoreboard-score{font-size:42px;font-weight:950}.scoreboard-team{font-size:20px;font-weight:900}.battle-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}.battle-card{background:#101d2d;border:1px solid var(--line);border-radius:12px;padding:12px}.battle-card h3{margin:0 0 8px;font-size:14px;color:var(--accent)}.battle-row{display:grid;grid-template-columns:44px 1fr auto;gap:8px;align-items:center;padding:8px 0;border-top:1px solid rgba(38,55,76,.65)}.battle-slot{font-size:10px;font-weight:900;color:var(--muted);text-transform:uppercase}.battle-player b{display:block;font-size:13px}.battle-player span{font-size:11px;color:var(--muted)}.battle-points{font-weight:900}.matchup-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.leader-banner{margin-top:14px;padding:10px 12px;border-radius:10px;background:#0b1727;border:1px solid var(--line);color:var(--muted)}
@media(max-width:600px){.versus,.scoreboard{grid-template-columns:1fr auto 1fr;gap:8px}.score{font-size:24px}.scoreboard-score{font-size:32px}.scoreboard-team{font-size:16px}.matchup-summary-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.summary-grid{grid-template-columns:repeat(2,1fr)}.team-report{grid-template-columns:repeat(2,1fr)}.analytics-grid{grid-template-columns:repeat(2,1fr)}.position-strip{grid-template-columns:repeat(2,1fr)}}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word}.footer{color:var(--muted);font-size:13px;padding:24px 0}.error{background:#3b1720;border:1px solid #7f1d1d;padding:12px;border-radius:10px;margin-bottom:15px}@media(max-width:600px){.wrap{padding:14px}.card{padding:13px}th,td{padding:7px;font-size:13px}}
"""


def page(title: str, body: str) -> HTMLResponse:
    sync = STATE.get("last_sync") or "Never"
    error = STATE.get("last_error")
    error_html = f'<div class="error"><b>Sync error:</b> {escape(error)}</div>' if error else ""
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · DTOS</title><style>{CSS}</style></head>
<body><main class="wrap"><header class="top"><div class="brand"><h1>DTOS</h1><p>Day Traders Front Office · Live Sleeper data</p></div><form method="post" action="/sync"><button class="btn" type="submit">Sync Now</button></form></header>
<nav class="nav"><a href="/">HQ</a><a href="/teams">Teams</a><a href="/matchups">Matchups</a><a href="/picks">Draft Picks</a><a href="/transactions">Transactions</a><a href="/settings">League Settings</a><a href="/api/status">API</a></nav>{error_html}{body}<footer class="footer">Last sync: {escape(sync)} · Automatic refresh every {SYNC_MINUTES} minutes while service is active.</footer></main></body></html>"""
    return HTMLResponse(html)


def require_data() -> dict[str, Any]:
    data = STATE.get("data") or {}
    if not data:
        raise HTTPException(503, "DTOS has not completed its first Sleeper sync.")
    return data


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok" if STATE.get("data") else "starting", "league_id": LEAGUE_ID, "last_sync": STATE.get("last_sync"), "last_error": STATE.get("last_error")}


@app.get("/api/status")
async def api_status() -> JSONResponse:
    await ensure_fresh()
    data = STATE.get("data") or {}
    return JSONResponse({
        "version": "0.8.1",
        "league_id": LEAGUE_ID,
        "last_sync": STATE.get("last_sync"),
        "last_error": STATE.get("last_error"),
        "syncing": STATE.get("syncing"),
        "counts": {
            "owners": len(data.get("owners") or []),
            "teams": len(data.get("teams") or []),
            "traded_picks": len(data.get("traded_picks") or []),
            "transactions": len(data.get("transactions") or []),
        },
    })


@app.get("/api/league")
async def api_league() -> JSONResponse:
    await ensure_fresh()
    data = require_data().copy()
    data.pop("players", None)
    return JSONResponse(data)


@app.post("/sync")
async def manual_sync(request: Request):
    await sync_sleeper(force_players=False)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": STATE.get("last_error") is None, "last_sync": STATE.get("last_sync"), "error": STATE.get("last_error")})
    return RedirectResponse(url="/", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    await ensure_fresh()
    d = require_data()
    league = d["league"]
    teams = d["teams"]
    nfl = d["nfl_state"]
    leader = teams[0] if teams else None
    body = f"""
<section class="grid">
<div class="card"><div class="muted">League</div><div class="stat">{escape(league.get('name') or 'Day Traders')}</div><p class="muted">{len(teams)} teams · {escape(str(league.get('season') or ''))} season</p></div>
<div class="card"><div class="muted">NFL State</div><div class="stat">Week {escape(str(d['week']))}</div><p class="muted">{escape(str(nfl.get('season_type') or ''))}</p></div>
<div class="card"><div class="muted">Current Leader</div><div class="stat">{escape(leader['team_name'] if leader else '—')}</div><p class="record">{leader['wins'] if leader else 0}-{leader['losses'] if leader else 0}</p></div>
<div class="card"><div class="muted">Data Health</div><div class="stat good">Live</div><p class="muted">Scoring settings, rosters, owners, picks, matchups and transactions synced.</p></div>
</section>
<h2>Standings</h2><div class="card"><table><thead><tr><th>#</th><th>Team</th><th>Owner</th><th>Record</th><th>PF</th></tr></thead><tbody>{''.join(f'<tr><td>{i}</td><td><b>{escape(t["team_name"])}</b></td><td>{escape(t["owner"])}</td><td>{t["wins"]}-{t["losses"]}-{t["ties"]}</td><td>{t["points_for"]}</td></tr>' for i,t in enumerate(teams,1))}</tbody></table></div>
"""
    return page("Front Office HQ", body)


@app.get("/teams", response_class=HTMLResponse)
async def teams_page() -> HTMLResponse:
    await ensure_fresh()
    teams = require_data()["teams"]
    cards = []
    for rank, team in enumerate(teams, 1):
        starters = sum(1 for p in team["players"] if p["roster_slot"] == "Starter")
        pos_counts = {pos: sum(1 for p in team["players"] if p["position"] == pos) for pos in ("QB", "RB", "WR", "TE")}
        firsts = team.get("pick_counts", {}).get("1", 0)
        cards.append(
            f'<a class="card team team-link" href="/teams/{team["roster_id"]}">'
            f'<div class="team-head"><div><div class="identity-kicker">Owner: {escape(team["owner"])}</div>'
            f'<h3 class="franchise-name">{escape(team["team_name"])}</h3></div><div class="rank-badge">#{rank}</div></div>'
            f'<p class="record">{team["wins"]}-{team["losses"]}-{team["ties"]}</p>'
            f'<div class="summary-grid">'
            f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div>'
            f'<div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>'
            f'<div class="metric"><b>{len(team["players"])}</b><span>Players</span></div>'
            f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
            f'</div><div class="position-strip">'
            + ''.join(f'<div class="position-count"><b>{pos_counts[pos]}</b><span>{pos}</span></div>' for pos in ("QB","RB","WR","TE"))
            + f'</div><p class="muted" style="margin-bottom:0">{starters} starters · {len(team.get("picks_owned", []))} total future picks</p></a>'
        )
    return page(
        "Teams",
        '<h2>League Franchises</h2><p class="muted">Select a team for its complete roster, draft capital and front-office summary.</p><div class="grid">'
        + "".join(cards)
        + "</div>",
    )


@app.get("/teams/{roster_id}", response_class=HTMLResponse)
async def team_detail_page(roster_id: int) -> HTMLResponse:
    await ensure_fresh()
    teams = require_data()["teams"]
    team = next((t for t in teams if int(t["roster_id"]) == roster_id), None)
    if not team:
        raise HTTPException(404, "Team not found")

    rank = next((i for i, t in enumerate(teams, 1) if int(t["roster_id"]) == roster_id), "—")
    pos_order = ("QB", "RB", "WR", "TE", "K", "DEF", "—")
    pos_counts = {pos: sum(1 for p in team["players"] if p["position"] == pos) for pos in ("QB", "RB", "WR", "TE")}

    roster_html = []
    for slot in ("Starter", "Bench", "IR", "Taxi"):
        slot_players = [p for p in team["players"] if p["roster_slot"] == slot]
        if not slot_players:
            continue
        if slot == "Starter":
            ordered = sorted(slot_players, key=lambda p: (p.get("starter_index") is None, p.get("starter_index") or 0))
            rows = "".join(
                f'<div class="lineup-row"><div class="lineup-slot">{escape(p.get("starter_slot") or p["position"])}</div>'
                f'<div class="lineup-player"><div><b>{escape(p["name"])}</b><div class="muted">{escape(p["position"])} · {escape(p["team"])}</div></div>'
                f'<div class="lineup-meta">STARTER</div></div></div>'
                for p in ordered
            )
            roster_html.append(
                f'<section class="roster-section"><div class="section-title"><span class="slot-label">Starting Lineup</span>'
                f'<span class="muted">{len(slot_players)} starters</span></div><div class="sleeper-lineup">{rows}</div></section>'
            )
            continue
        groups = []
        present_positions = [pos for pos in pos_order if any(p["position"] == pos for p in slot_players)]
        other_positions = sorted({p["position"] for p in slot_players if p["position"] not in pos_order})
        for pos in present_positions + other_positions:
            players = [p for p in slot_players if p["position"] == pos]
            rows = "".join(
                f'<div class="player"><span class="player-name"><span class="pos-dot"></span>{escape(p["name"])}</span><span class="pill">{escape(p["position"])} · {escape(p["team"])}</span></div>'
                for p in players
            )
            groups.append(f'<div class="position-block"><div class="position-head"><span>{escape(pos)}</span><span>{len(players)}</span></div>{rows}</div>')
        roster_html.append(
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">{slot}</span>'
            f'<span class="muted">{len(slot_players)} players</span></div><div class="card players">{"".join(groups)}</div></section>'
        )

    total_picks = len(team.get("picks_owned", []))
    firsts = team.get("pick_counts", {}).get("1", 0)
    seconds = team.get("pick_counts", {}).get("2", 0)
    thirds = team.get("pick_counts", {}).get("3", 0)
    roster_size = max(1, len(team["players"]))
    # Transparent first-pass presentation metrics. These are UI summaries, not market-value models.
    position_strength = {pos: min(100, round(pos_counts[pos] / max(1, {"QB":3,"RB":8,"WR":10,"TE":4}[pos]) * 100)) for pos in ("QB","RB","WR","TE")}
    contender_score = min(99, round((position_strength["QB"] * .25 + position_strength["RB"] * .25 + position_strength["WR"] * .30 + position_strength["TE"] * .20)))
    dynasty_score = min(99, round(contender_score * .75 + min(100, total_picks * 7) * .25))
    overall_grade = "A" if contender_score >= 85 else "B" if contender_score >= 70 else "C" if contender_score >= 55 else "D"
    body = (
        f'<a class="back" href="/teams">← All Teams</a>'
        f'<section class="card"><div class="team-head"><div><div class="identity-kicker">Owner: {escape(team["owner"])}</div>'
        f'<h2 class="franchise-name">{escape(team["team_name"])}</h2><p class="owner-line">Franchise rank #{rank}</p></div>'
        f'<div class="rank-badge">#{rank}</div></div>'
        f'<div class="summary-grid">'
        f'<div class="metric"><b>{team["wins"]}-{team["losses"]}-{team["ties"]}</b><span>Record</span></div>'
        f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div>'
        f'<div class="metric"><b>{team["points_against"]:.2f}</b><span>Points Against</span></div>'
        f'<div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>'
        f'<div class="metric"><b>{len(team["players"])}</b><span>Total Players</span></div>'
        f'<div class="metric"><b>{total_picks}</b><span>Future Picks</span></div>'
        f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
        f'<div class="metric"><b>{seconds}</b><span>Future 2nds</span></div>'
        f'</div><div class="position-strip">'
        + ''.join(f'<div class="position-count"><b>{pos_counts[pos]}</b><span>{pos}</span></div>' for pos in ("QB","RB","WR","TE"))
        + '</div></section>'
        f'<section class="roster-section"><div class="section-title"><span class="slot-label">Front Office Analytics</span><span class="muted">Engine framework</span></div>'
        f'<div class="analytics-grid">'
        f'<div class="analytics-card"><b>#{rank}</b><span>Current Rank</span></div>'
        f'<div class="analytics-card"><b>{firsts}</b><span>1st-Round Assets</span></div>'
        f'<div class="analytics-card"><b>{thirds}</b><span>3rd-Round Assets</span></div>'
        f'<div class="analytics-card"><b>Coming Soon</b><span>Contender Score</span></div>'
        f'<div class="analytics-card"><b>Coming Soon</b><span>Dynasty Grade</span></div>'
        f'</div></section>'
        f'<section class="roster-section"><div class="section-title"><span class="slot-label">Team Report</span><span class="muted">At-a-glance roster profile</span></div>'
        f'<div class="team-report"><div class="report-card"><div class="grade">{overall_grade}</div><small>Overall Grade</small></div>'
        f'<div class="report-card"><div class="grade">{contender_score}</div><small>Contender Score</small></div>'
        f'<div class="report-card"><div class="grade">{dynasty_score}</div><small>Dynasty Score</small></div></div>'
        f'<div class="card">' + ''.join(
            f'<div class="progress-row"><div class="progress-label"><span>{pos} Room</span><b>{position_strength[pos]}</b></div><div class="progress-track"><div class="progress-fill" style="width:{position_strength[pos]}%"></div></div></div>'
            for pos in ("QB","RB","WR","TE")
        ) + '</div></section>'
    )

    owned_by_year = {}
    for pick in team.get("picks_owned", []):
        owned_by_year.setdefault(pick["season"], []).append(pick)
    owned_sections = []
    for season, picks in sorted(owned_by_year.items()):
        rows = "".join(
            f'<div class="pick-row {"acquired" if pick["is_traded"] else "own"}"><div><b>Round {pick["round"]}</b>'
            f'<div class="pick-origin">Original: {escape(pick["original_team"])}</div>'
            f'<div class="pick-status {"acquired" if pick["is_traded"] else "own"}">{"Acquired" if pick["is_traded"] else "Own"}</div></div>'
            f'<span class="pill">{season}</span></div>'
            for pick in sorted(picks, key=lambda item: (item["round"], item["original_team"]))
        )
        owned_sections.append(
            f'<details class="pick-year"><summary class="pick-summary"><span><b>{season}</b></span><span class="muted">{len(picks)} picks</span></summary>'
            f'<div class="card pick-list">{rows}</div></details>'
        )

    away_rows = "".join(
        f'<div class="pick-row traded-away"><div><b>{pick["season"]} Round {pick["round"]}</b>'
        f'<div class="pick-origin">Original: {escape(team["team_name"])}</div>'
        f'<div class="pick-status away">Current owner: {escape(pick["current_owner"])}</div></div>'
        f'<span class="pill">Traded</span></div>'
        for pick in sorted(team.get("picks_traded_away", []), key=lambda item: (item["season"], item["round"]))
    )
    draft_capital = (
        f'<section class="roster-section"><div class="section-title"><span class="slot-label">Draft Capital</span>'
        f'<span class="muted">Green = own · Blue = acquired · Red = traded away</span></div>'
        f'<div class="card"><div class="summary-grid">'
        f'<div class="metric"><b>{total_picks}</b><span>Total Picks</span></div>'
        f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
        f'<div class="metric"><b>{seconds}</b><span>Future 2nds</span></div>'
        f'<div class="metric"><b>{thirds}</b><span>Future 3rds</span></div></div></div>'
        f'{"".join(owned_sections)}'
        + (f'<details class="pick-year"><summary class="pick-summary"><span class="away"><b>Original Picks Traded Away</b></span><span class="muted">{len(team.get("picks_traded_away", []))} picks</span></summary>'
           f'<div class="card pick-list">{away_rows}</div></details>' if away_rows else '')
        + '</section>'
    )
    body += draft_capital + "".join(roster_html)
    return page(team["team_name"], body)


@app.get("/matchups", response_class=HTMLResponse)
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
        margin = abs(float(left["points"]) - float(right["points"]))
        if left["points"] == right["points"]:
            status = "Tied"
            edge_text = "Even"
        else:
            leader = left if left["points"] > right["points"] else right
            status = "Live score"
            edge_text = f'{leader["team"]} +{margin:.2f}'
        top_scorer = max((p for side in sides for p in side.get("lineup", [])), key=lambda p: p["points"], default=None)
        top_text = f'{top_scorer["name"]} {top_scorer["points"]:.2f}' if top_scorer else "No points yet"
        cards.append(
            f'<a class="matchup-card" href="/matchups/{escape(matchup_id)}">'
            f'<div class="matchup-label"><span class="matchup-number">Matchup {escape(matchup_id)}</span><span class="matchup-status">{status}</span></div>'
            f'<div class="versus"><div class="matchup-team"><div class="matchup-owner">{escape(left["owner"])}</div><h3>{escape(left["team"])}</h3><div class="record">{escape(left["record"])}</div><div class="score">{left["points"]:.2f}</div></div>'
            f'<div class="vs-mark">VS</div>'
            f'<div class="matchup-team right"><div class="matchup-owner">{escape(right["owner"])}</div><h3>{escape(right["team"])}</h3><div class="record">{escape(right["record"])}</div><div class="score">{right["points"]:.2f}</div></div></div>'
            f'<div class="matchup-footer"><span><b class="edge">Edge:</b> {escape(edge_text)}</span><span><b>Top scorer:</b> {escape(top_text)}</span></div></a>'
        )
    body = (
        f'<div class="section-title"><div><h2 style="margin:0">Week {d["week"]} Matchups</h2><div class="muted">Live Sleeper scoring and lineup comparison</div></div>'
        f'<span class="pill">{len(cards)} matchups</span></div><div class="matchup-grid">{"".join(cards)}</div>'
    )
    return page("Matchups", body)


@app.get("/matchups/{matchup_id}", response_class=HTMLResponse)
async def matchup_detail_page(matchup_id: str) -> HTMLResponse:
    await ensure_fresh()
    d = require_data()
    sides = d["matchups"].get(str(matchup_id))
    if not sides:
        raise HTTPException(status_code=404, detail="Matchup not found")
    if len(sides) < 2:
        return page("Matchup", f'<a class="back" href="/matchups">← All Matchups</a><div class="card"><h2>Matchup {escape(matchup_id)}</h2><p class="muted">Opponent assignment is not complete.</p></div>')
    left, right = sides[0], sides[1]
    margin = abs(float(left["points"]) - float(right["points"]))
    if left["points"] == right["points"]:
        headline = "Matchup is tied"
    else:
        leader = left if left["points"] > right["points"] else right
        headline = f'{leader["team"]} leads by {margin:.2f}'
    left_top = max(left.get("lineup", []), key=lambda p: p["points"], default=None)
    right_top = max(right.get("lineup", []), key=lambda p: p["points"], default=None)
    combined_top = max([p for p in (left_top, right_top) if p], key=lambda p: p["points"], default=None)

    max_slots = max(len(left.get("lineup", [])), len(right.get("lineup", [])))
    battles = []
    for index in range(max_slots):
        lp = left.get("lineup", [])[index] if index < len(left.get("lineup", [])) else None
        rp = right.get("lineup", [])[index] if index < len(right.get("lineup", [])) else None
        slot = (lp or rp or {}).get("slot", "START")
        left_html = (f'<div class="battle-player"><b>{escape(lp["name"])}</b><span>{escape(lp["position"])} · {escape(lp["nfl_team"])}</span></div><div class="battle-points">{lp["points"]:.2f}</div>') if lp else '<div class="battle-player"><b>Empty</b></div><div class="battle-points">—</div>'
        right_html = (f'<div class="battle-player"><b>{escape(rp["name"])}</b><span>{escape(rp["position"])} · {escape(rp["nfl_team"])}</span></div><div class="battle-points">{rp["points"]:.2f}</div>') if rp else '<div class="battle-player"><b>Empty</b></div><div class="battle-points">—</div>'
        battles.append(
            f'<div class="battle-card"><h3>{escape(slot)}</h3>'
            f'<div class="battle-row"><div class="battle-slot">{escape(left["owner"])}</div>{left_html}</div>'
            f'<div class="battle-row"><div class="battle-slot">{escape(right["owner"])}</div>{right_html}</div></div>'
        )

    def bench_html(side: dict[str, Any]) -> str:
        rows = ''.join(
            f'<div class="player"><span><b>{escape(p["name"])}</b><br><span class="muted">{escape(p["position"])} · {escape(p["nfl_team"])}</span></span><b>{p["points"]:.2f}</b></div>'
            for p in side.get("bench", [])[:12]
        ) or '<div class="muted">No bench scoring available.</div>'
        return f'<div class="card"><h3>{escape(side["team"])} Bench</h3>{rows}</div>'

    top_scorer_text = f'{combined_top["name"]} · {combined_top["points"]:.2f}' if combined_top else "No points yet"
    body = (
        f'<a class="back" href="/matchups">← All Matchups</a>'
        f'<section class="matchup-hero"><div class="matchup-label"><span class="matchup-number">Week {d["week"]} · Matchup {escape(matchup_id)}</span><span class="matchup-status">Live Sleeper data</span></div>'
        f'<div class="scoreboard"><div class="scoreboard-side"><div class="matchup-owner">{escape(left["owner"])}</div><div class="scoreboard-team">{escape(left["team"])}</div><div class="record">{escape(left["record"])}</div><div class="scoreboard-score">{left["points"]:.2f}</div></div>'
        f'<div class="vs-mark">VS</div><div class="scoreboard-side right"><div class="matchup-owner">{escape(right["owner"])}</div><div class="scoreboard-team">{escape(right["team"])}</div><div class="record">{escape(right["record"])}</div><div class="scoreboard-score">{right["points"]:.2f}</div></div></div>'
        f'<div class="leader-banner"><b>{escape(headline)}</b></div>'
        f'<div class="matchup-summary-grid"><div class="metric"><b>{margin:.2f}</b><span>Score Margin</span></div><div class="metric"><b>{len(left.get("lineup", []))}</b><span>{escape(left["owner"])} Starters</span></div><div class="metric"><b>{len(right.get("lineup", []))}</b><span>{escape(right["owner"])} Starters</span></div><div class="metric"><b>{escape(top_scorer_text)}</b><span>Top Starter</span></div></div></section>'
        f'<section class="roster-section"><div class="section-title"><span class="slot-label">Starting Lineup Battles</span><span class="muted">Slot-by-slot live points</span></div><div class="battle-grid">{"".join(battles)}</div></section>'
        f'<section class="roster-section"><div class="section-title"><span class="slot-label">Bench Scoring</span><span class="muted">Top 12 bench players shown</span></div><div class="grid">{bench_html(left)}{bench_html(right)}</div></section>'
    )
    return page(f'{left["team"]} vs {right["team"]}', body)


@app.get("/picks", response_class=HTMLResponse)
async def picks_page() -> HTMLResponse:
    await ensure_fresh()
    d = require_data()
    roster_names = {str(t["roster_id"]): t["team_name"] for t in d["teams"]}
    rows = []
    for p in sorted(d["traded_picks"], key=lambda x: (x.get("season", ""), x.get("round", 0), x.get("roster_id", 0))):
        rows.append(f'<tr><td>{escape(str(p.get("season","")))}</td><td>{escape(str(p.get("round","")))}</td><td>{escape(roster_names.get(str(p.get("roster_id")), str(p.get("roster_id"))))}</td><td>{escape(roster_names.get(str(p.get("owner_id")), str(p.get("owner_id"))))}</td></tr>')
    body = '<h2>Traded Draft Picks</h2><div class="card"><table><thead><tr><th>Season</th><th>Round</th><th>Original Team</th><th>Current Owner</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
    return page("Draft Picks", body)


@app.get("/transactions", response_class=HTMLResponse)
async def transactions_page() -> HTMLResponse:
    await ensure_fresh()
    txs = require_data()["transactions"]
    cards = []
    for tx in txs:
        created = tx.get("created")
        date = datetime.fromtimestamp(created / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if created else "—"
        cards.append(f'<div class="card"><h3>{escape(str(tx.get("type") or "Transaction").replace("_"," ").title())}</h3><div class="muted">{escape(date)} · {escape(str(tx.get("status") or ""))}</div><pre>{escape(json.dumps(tx, indent=2)[:5000])}</pre></div>')
    return page("Transactions", '<h2>Latest Week Transactions</h2><div class="grid">' + "".join(cards) + "</div>")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page() -> HTMLResponse:
    await ensure_fresh()
    d = require_data()
    scoring_rows = "".join(f'<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>' for k,v in sorted(d["scoring_settings"].items()))
    setting_rows = "".join(f'<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>' for k,v in sorted(d["league_settings"].items()))
    positions = " ".join(f'<span class="pill">{escape(str(p))}</span>' for p in d["roster_positions"])
    body = f'<h2>League Configuration</h2><div class="card"><h3>Roster Positions</h3><p>{positions}</p></div><div class="grid"><div class="card"><h3>Scoring Settings</h3><table><tbody>{scoring_rows}</tbody></table></div><div class="card"><h3>League Settings</h3><table><tbody>{setting_rows}</tbody></table></div></div>'
    return page("League Settings", body)
