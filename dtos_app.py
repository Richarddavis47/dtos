"""DTOS FastAPI application setup and router registration."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from html import escape
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app_metadata import APPLICATION_NAME, VERSION
from config import SYNC_MINUTES
from routes.api import create_api_router
from routes.crawl import create_crawl_router
from routes.draft import create_draft_router
from routes.front_offices import create_front_offices_router
from routes.hq import create_hq_router
from routes.matchups import create_matchups_router
from routes.settings import create_settings_router
from routes.teams import create_teams_router
from routes.trades import create_trades_router
from routes.transactions import create_transactions_router
from services.sleeper import (
    LEAGUE_ID,
    STATE,
    ensure_data_fresh,
    load_cache,
    sync_sleeper,
    sync_transactions,
)
from src.platform.observability import install_observability, mark_startup_complete

_PROCESS_STARTED = perf_counter()


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
    mark_startup_complete(_PROCESS_STARTED)
    task = asyncio.create_task(background_sync())
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title=APPLICATION_NAME, version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)
install_observability(app)


CSS = """
:root{color-scheme:dark;--bg:#07111f;--panel:#101d2d;--line:#26374c;--text:#f5f7fb;--muted:#9fb0c6;--accent:#6ee7b7;--gold:#f5c451}
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

.matchup-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.matchup-card{display:block;background:linear-gradient(180deg,#122238,#0d1a2a);border:1px solid var(--line);border-radius:16px;padding:16px;transition:transform .15s ease,border-color .15s ease}.matchup-card:hover{transform:translateY(-2px);border-color:#3d5877}.matchup-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.matchup-number{font-size:12px;color:var(--accent);font-weight:900;text-transform:uppercase;letter-spacing:.08em}.matchup-status{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:4px 8px}.versus{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.matchup-team{text-align:left}.matchup-team.right{text-align:right}.matchup-team h3{margin:3px 0 2px;font-size:18px}.matchup-owner{font-size:12px;color:var(--muted)}.score{font-size:30px;font-weight:900;margin-top:8px}.vs-mark{color:var(--muted);font-size:12px;font-weight:900}.matchup-footer{display:flex;justify-content:space-between;gap:10px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}.edge{color:var(--gold);font-weight:900}.matchup-hero{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:16px;padding:18px}.scoreboard{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.scoreboard-side.right{text-align:right}.scoreboard-score{font-size:42px;font-weight:950}.scoreboard-team{font-size:20px;font-weight:900}.battle-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.battle-card{background:#101d2d;border:1px solid var(--line);border-radius:14px;padding:12px;overflow:hidden}.battle-card h3{margin:0 0 10px;font-size:13px;color:var(--accent);letter-spacing:.08em;text-transform:uppercase}.battle-head{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);align-items:center;gap:8px}.battle-side{min-width:0;border:1px solid rgba(38,55,76,.8);border-radius:11px;padding:11px 9px;background:#0b1727;text-align:left}.battle-side.right{text-align:right}.battle-side.winning{border-color:rgba(110,231,183,.8);box-shadow:inset 0 0 0 1px rgba(110,231,183,.18)}.battle-side.losing{border-color:rgba(248,113,113,.55)}.battle-side.tied{border-color:var(--line)}.battle-side.vacant{border-style:dashed;opacity:.72}.battle-owner{font-size:9px;font-weight:900;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.battle-player b{display:block;font-size:14px;line-height:1.15;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.battle-player span{display:block;font-size:10px;color:var(--muted);margin-top:3px}.battle-points{font-size:18px;font-weight:950;margin-top:8px}.battle-vs{display:grid;place-items:center;color:var(--muted);font-size:10px;font-weight:950}.battle-result{display:block;font-size:8px;margin-top:4px;text-transform:uppercase;letter-spacing:.08em}.winning .battle-result{color:var(--accent)}.losing .battle-result{color:#fca5a5}.tied .battle-result{color:var(--muted)}.matchup-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.leader-banner{margin-top:14px;padding:10px 12px;border-radius:10px;background:#0b1727;border:1px solid var(--line);color:var(--muted)}.advantage-strip{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;margin-top:14px}.advantage-side{background:#0b1727;border:1px solid var(--line);border-radius:12px;padding:10px 12px}.advantage-side.right{text-align:right}.advantage-side b{display:block;font-size:20px}.advantage-side span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.advantage-center{text-align:center;color:var(--muted);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.bench-compare{display:grid;gap:8px}.bench-row{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);gap:8px;align-items:stretch}.bench-player{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:9px;min-width:0}.bench-player.right{text-align:right}.bench-player.leading{border-color:rgba(110,231,183,.72)}.bench-player.trailing{border-color:rgba(248,113,113,.48)}.bench-player.empty{border-style:dashed;opacity:.68}.bench-player b{display:block;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bench-player span{display:block;color:var(--muted);font-size:9px;margin-top:3px}.bench-player strong{display:block;font-size:15px;margin-top:6px}.bench-vs{display:grid;place-items:center;color:var(--muted);font-size:9px;font-weight:900}.bench-total-card{background:linear-gradient(180deg,#14263d,#0b1727);border:1px solid var(--line);border-radius:14px;padding:12px;margin-bottom:10px}.bench-total-grid{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center}.bench-total-side.right{text-align:right}.bench-total-side b{display:block;font-size:24px}.bench-total-side span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.edge-badge{display:inline-block;margin-top:8px;padding:4px 8px;border-radius:999px;border:1px solid var(--line);font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.07em}.edge-badge.good{border-color:rgba(110,231,183,.55);background:rgba(110,231,183,.08)}.edge-badge.warn{border-color:rgba(248,113,113,.45);background:rgba(248,113,113,.07)}.edge-badge.tie{color:var(--muted)}
.matchup-hero.leading-left{border-color:rgba(110,231,183,.52);box-shadow:0 14px 34px rgba(0,0,0,.18),inset 3px 0 0 rgba(110,231,183,.75)}
.matchup-hero.leading-right{border-color:rgba(96,165,250,.52);box-shadow:0 14px 34px rgba(0,0,0,.18),inset -3px 0 0 rgba(96,165,250,.75)}
.matchup-hero.tied-game{box-shadow:0 14px 34px rgba(0,0,0,.16)}
.leader-banner.leading{border-color:rgba(110,231,183,.50);background:linear-gradient(90deg,rgba(110,231,183,.11),rgba(11,23,39,.96));color:var(--text)}
.leader-banner.tied{background:linear-gradient(90deg,rgba(159,176,198,.08),rgba(11,23,39,.96))}
.live-share{margin-top:12px}.live-share-head{display:flex;justify-content:space-between;gap:12px;font-size:10px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.07em}.live-share-track{height:8px;margin-top:6px;background:#07111f;border:1px solid var(--line);border-radius:999px;overflow:hidden;display:flex}.live-share-left{height:100%;background:linear-gradient(90deg,var(--accent),#34d399)}.live-share-right{height:100%;background:linear-gradient(90deg,#60a5fa,#93c5fd)}
.battle-card{box-shadow:0 8px 20px rgba(0,0,0,.10)}.battle-card.top-battle{border-color:rgba(245,196,81,.58);box-shadow:0 0 0 1px rgba(245,196,81,.08),0 10px 24px rgba(0,0,0,.14)}
.top-performer{position:relative}.top-performer:after{content:"TOP STARTER";display:inline-block;margin-top:7px;padding:3px 6px;border-radius:999px;border:1px solid rgba(245,196,81,.5);background:rgba(245,196,81,.08);color:var(--gold);font-size:7px;font-weight:950;letter-spacing:.08em}
.scoreboard-side.leading .scoreboard-score{color:var(--accent);text-shadow:0 0 18px rgba(110,231,183,.16)}.scoreboard-side.trailing{opacity:.84}.scoreboard-side.right.leading .scoreboard-score{color:#93c5fd;text-shadow:0 0 18px rgba(96,165,250,.16)}
@media(max-width:600px){.versus,.scoreboard{grid-template-columns:1fr auto 1fr;gap:8px}.score{font-size:24px}.scoreboard-score{font-size:32px}.scoreboard-team{font-size:16px}.matchup-summary-grid{grid-template-columns:repeat(2,1fr)}.battle-grid{grid-template-columns:1fr}.battle-card{padding:9px}.battle-head{grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr);gap:5px}.battle-side{padding:8px 7px}.battle-player b{font-size:13px}.battle-owner{font-size:8px}.battle-points{font-size:17px}.bench-row{grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr);gap:5px}.bench-player{padding:8px 6px}.bench-player b{font-size:11px}.bench-total-side b{font-size:20px}}
@media(max-width:760px){.summary-grid{grid-template-columns:repeat(2,1fr)}.team-report{grid-template-columns:repeat(2,1fr)}.analytics-grid{grid-template-columns:repeat(2,1fr)}.position-strip{grid-template-columns:repeat(2,1fr)}}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word}.footer{color:var(--muted);font-size:13px;padding:24px 0}.error{background:#3b1720;border:1px solid #7f1d1d;padding:12px;border-radius:10px;margin-bottom:15px}@media(max-width:600px){.wrap{padding:14px}.card{padding:13px}th,td{padding:7px;font-size:13px}}
"""


def page(title: str, body: str, commissioner_chrome: bool = False) -> HTMLResponse:
    sync = STATE.get("last_sync") or "Never"
    error = STATE.get("last_error")
    error_html = f'<div class="error"><b>Sync error:</b> {escape(error)}</div>' if error else ""
    league_name = str(((STATE.get("data") or {}).get("league") or {}).get("name") or "Sleeper League")
    standard_chrome = f"""<header class="top"><div class="brand"><h1>{APPLICATION_NAME}</h1><p>{escape(league_name)} Front Office · Live Sleeper data</p></div><form method="post" action="/sync"><button class="btn" type="submit">Sync Now</button></form></header>
<nav class="nav"><a href="/">Commissioner Desk</a><a href="/teams">Teams</a><a href="/front-offices">Front Offices</a><a href="/trades">Trade Intelligence</a><a href="/matchups">Matchups</a><a href="/picks">Draft Picks</a><a href="/transactions">Transactions</a><a href="/settings">League Settings</a><a href="/api/status">API</a></nav>"""
    footer = f'<footer class="footer">Last sync: {escape(sync)} · Automatic refresh every {SYNC_MINUTES} minutes while service is active.</footer>'
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · {APPLICATION_NAME}</title><style>{CSS}</style></head>
<body><main class="wrap">{"" if commissioner_chrome else standard_chrome}{error_html}{body}{"" if commissioner_chrome else footer}</main></body></html>"""
    return HTMLResponse(html)


def require_data() -> dict[str, Any]:
    data = STATE.get("data") or {}
    if not data:
        raise HTTPException(503, "DTOS has not completed its first Sleeper sync.")
    return data


app.include_router(
    create_api_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        sync_sleeper=sync_sleeper,
        state=STATE,
        league_id=LEAGUE_ID,
    )
)

app.include_router(
    create_crawl_router(
        get_data=lambda: STATE.get("data") or {},
        state=STATE,
        league_id=LEAGUE_ID,
    )
)

app.include_router(
    create_draft_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_front_offices_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_hq_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        state=STATE,
        league_id=LEAGUE_ID,
        page=page,
    )
)

app.include_router(
    create_matchups_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_settings_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)

app.include_router(
    create_teams_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        state=STATE,
        page=page,
    )
)

app.include_router(
    create_transactions_router(
        ensure_fresh=ensure_fresh,
        refresh_transactions=sync_transactions,
        require_data=require_data,
        state=STATE,
        page=page,
    )
)

app.include_router(
    create_trades_router(
        ensure_fresh=ensure_fresh,
        require_data=require_data,
        page=page,
    )
)
