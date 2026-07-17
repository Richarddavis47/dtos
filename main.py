"""DTOS v0.1 MVP — single-file Render deployment.

Public Day Traders dashboard with automatic Sleeper synchronization.
League ID defaults to 1313066632158924800 and can be overridden with
SLEEPER_LEAGUE_ID.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

LEAGUE_ID = os.getenv("SLEEPER_LEAGUE_ID", "1313066632158924800")
SLEEPER_BASE = "https://api.sleeper.app/v1"
SYNC_MINUTES = max(5, int(os.getenv("SYNC_MINUTES", "15")))
CACHE_FILE = Path(os.getenv("DTOS_CACHE_FILE", "/tmp/dtos_cache.json"))
REQUEST_TIMEOUT = float(os.getenv("SLEEPER_TIMEOUT", "30"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("dtos")

STATE: dict[str, Any] = {
    "data": {},
    "last_sync": None,
    "last_error": None,
    "syncing": False,
}
SYNC_LOCK = asyncio.Lock()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_cache() -> None:
    if not CACHE_FILE.exists():
        return
    try:
        payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        STATE.update(payload)
        STATE["syncing"] = False
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not load cache: %s", exc)


def save_cache() -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps({k: v for k, v in STATE.items() if k != "syncing"}),
            encoding="utf-8",
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not save cache: %s", exc)


async def sleeper_get(client: httpx.AsyncClient, path: str) -> Any:
    response = await client.get(f"{SLEEPER_BASE}{path}")
    response.raise_for_status()
    return response.json()


async def sync_sleeper(force_players: bool = False) -> dict[str, Any]:
    """Fetch and normalize the current Day Traders league state."""
    async with SYNC_LOCK:
        if STATE["syncing"]:
            return STATE
        STATE["syncing"] = True
        try:
            timeout = httpx.Timeout(REQUEST_TIMEOUT)
            headers = {"User-Agent": "DTOS/0.1 (+Day Traders)"}
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                league, users, rosters, traded_picks, drafts, nfl_state = await asyncio.gather(
                    sleeper_get(client, f"/league/{LEAGUE_ID}"),
                    sleeper_get(client, f"/league/{LEAGUE_ID}/users"),
                    sleeper_get(client, f"/league/{LEAGUE_ID}/rosters"),
                    sleeper_get(client, f"/league/{LEAGUE_ID}/traded_picks"),
                    sleeper_get(client, f"/league/{LEAGUE_ID}/drafts"),
                    sleeper_get(client, "/state/nfl"),
                )

                week = int((nfl_state or {}).get("week") or 1)
                season_type = (nfl_state or {}).get("season_type") or "regular"
                matchup_week = week if season_type in {"regular", "post"} else 1

                matchups, transactions = await asyncio.gather(
                    sleeper_get(client, f"/league/{LEAGUE_ID}/matchups/{matchup_week}"),
                    sleeper_get(client, f"/league/{LEAGUE_ID}/transactions/{matchup_week}"),
                )

                cached_players = (STATE.get("data") or {}).get("players") or {}
                players_fetched_at = (STATE.get("data") or {}).get("players_fetched_at")
                players_stale = True
                if players_fetched_at:
                    try:
                        age = utcnow() - datetime.fromisoformat(players_fetched_at)
                        players_stale = age > timedelta(hours=24)
                    except ValueError:
                        pass
                if force_players or not cached_players or players_stale:
                    players = await sleeper_get(client, "/players/nfl")
                    players_fetched_at = utcnow().isoformat()
                else:
                    players = cached_players

            user_by_id = {str(u.get("user_id")): u for u in users}
            team_rows = []
            for roster in rosters:
                owner_id = str(roster.get("owner_id") or "")
                owner = user_by_id.get(owner_id, {})
                metadata = owner.get("metadata") or {}
                settings = roster.get("settings") or {}
                player_ids = roster.get("players") or []
                starter_ids = set(roster.get("starters") or [])
                player_rows = []
                for player_id in player_ids:
                    p = players.get(str(player_id), {}) if isinstance(players, dict) else {}
                    full_name = p.get("full_name") or " ".join(
                        part for part in [p.get("first_name"), p.get("last_name")] if part
                    ) or str(player_id)
                    player_rows.append({
                        "id": str(player_id),
                        "name": full_name,
                        "position": p.get("position") or "—",
                        "team": p.get("team") or "FA",
                        "starter": str(player_id) in starter_ids,
                    })
                player_rows.sort(key=lambda p: (not p["starter"], p["position"], p["name"]))
                team_rows.append({
                    "roster_id": roster.get("roster_id"),
                    "owner_id": owner_id,
                    "owner": owner.get("display_name") or owner.get("username") or "Unassigned",
                    "team_name": metadata.get("team_name") or owner.get("display_name") or f"Team {roster.get('roster_id')}",
                    "avatar": owner.get("avatar"),
                    "wins": settings.get("wins", 0),
                    "losses": settings.get("losses", 0),
                    "ties": settings.get("ties", 0),
                    "points_for": round((settings.get("fpts", 0) or 0) + (settings.get("fpts_decimal", 0) or 0) / 100, 2),
                    "players": player_rows,
                })
            team_rows.sort(key=lambda t: (-t["wins"], t["losses"], -t["points_for"]))

            matchup_by_roster = {str(m.get("roster_id")): m for m in matchups}
            matchup_groups: dict[str, list[dict[str, Any]]] = {}
            for team in team_rows:
                m = matchup_by_roster.get(str(team["roster_id"]), {})
                matchup_id = str(m.get("matchup_id") or "Unassigned")
                matchup_groups.setdefault(matchup_id, []).append({
                    "team": team["team_name"],
                    "owner": team["owner"],
                    "points": m.get("points", 0),
                    "roster_id": team["roster_id"],
                })

            STATE["data"] = {
                "league": league,
                "scoring_settings": league.get("scoring_settings") or {},
                "league_settings": league.get("settings") or {},
                "roster_positions": league.get("roster_positions") or [],
                "owners": users,
                "teams": team_rows,
                "traded_picks": traded_picks,
                "drafts": drafts,
                "transactions": transactions,
                "matchups": matchup_groups,
                "nfl_state": nfl_state,
                "week": matchup_week,
                "players": players,
                "players_fetched_at": players_fetched_at,
            }
            STATE["last_sync"] = utcnow().isoformat()
            STATE["last_error"] = None
            save_cache()
            logger.info("Sleeper sync complete: %s teams", len(team_rows))
        except Exception as exc:
            STATE["last_error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Sleeper sync failed")
        finally:
            STATE["syncing"] = False
        return STATE


async def ensure_fresh() -> None:
    last_sync = STATE.get("last_sync")
    stale = True
    if last_sync:
        try:
            stale = utcnow() - datetime.fromisoformat(last_sync) > timedelta(minutes=SYNC_MINUTES)
        except ValueError:
            pass
    if stale and not STATE["syncing"]:
        await sync_sleeper()


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


app = FastAPI(title="DTOS", version="0.1.0", lifespan=lifespan)


CSS = """
:root{--bg:#07111f;--panel:#101d2d;--line:#26374c;--text:#f5f7fb;--muted:#9fb0c6;--accent:#6ee7b7;--gold:#f5c451}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#07111f,#0b1727);color:var(--text);font-family:Inter,system-ui,-apple-system,sans-serif}
a{color:inherit;text-decoration:none}.wrap{max-width:1180px;margin:auto;padding:20px}.top{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:20px}
.brand h1{margin:0;font-size:28px}.brand p{margin:4px 0;color:var(--muted)}.btn{border:0;border-radius:10px;padding:11px 15px;background:var(--accent);color:#062018;font-weight:800;cursor:pointer}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.nav a{padding:9px 12px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:rgba(16,29,45,.94);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 10px 25px rgba(0,0,0,.15)}.card h2,.card h3{margin-top:0}.muted{color:var(--muted)}.good{color:var(--accent)}.warn{color:#fca5a5}
.stat{font-size:27px;font-weight:850}.team{margin-bottom:14px}.record{color:var(--gold);font-weight:800}.players{display:grid;gap:5px}.player{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid rgba(38,55,76,.65)}.starter{font-weight:800}.pill{font-size:12px;padding:3px 7px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
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
        "version": "0.1.0",
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
    for team in teams:
        players = "".join(
            f'<div class="player {"starter" if p["starter"] else ""}"><span>{escape(p["name"])}</span><span class="pill">{escape(p["position"])} · {escape(p["team"])}</span></div>'
            for p in team["players"]
        )
        cards.append(f'<article class="card team"><h3>{escape(team["team_name"])}</h3><div class="muted">{escape(team["owner"])}</div><p class="record">{team["wins"]}-{team["losses"]}-{team["ties"]}</p><div class="players">{players}</div></article>')
    return page("Teams", '<h2>Teams & Rosters</h2><div class="grid">' + "".join(cards) + "</div>")


@app.get("/matchups", response_class=HTMLResponse)
async def matchups_page() -> HTMLResponse:
    await ensure_fresh()
    d = require_data()
    cards = []
    for matchup_id, sides in sorted(d["matchups"].items()):
        rows = "".join(f'<div class="player"><span><b>{escape(s["team"])}</b><br><span class="muted">{escape(s["owner"])}</span></span><span class="stat">{s["points"]:.2f}</span></div>' for s in sides)
        cards.append(f'<div class="card"><h3>Matchup {escape(matchup_id)}</h3>{rows}</div>')
    return page("Matchups", f'<h2>Week {d["week"]} Matchups</h2><div class="grid">{"".join(cards)}</div>')


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
