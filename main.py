"""DTOS v0.3 Complete Teams Experience — single-file Render deployment.

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
            headers = {"User-Agent": "DTOS/0.2 (+Day Traders)"}
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
                    reserve_ids = set(str(x) for x in (roster.get("reserve") or []))
                    taxi_ids = set(str(x) for x in (roster.get("taxi") or []))
                    pid = str(player_id)
                    if pid in starter_ids:
                        roster_slot = "Starter"
                    elif pid in taxi_ids:
                        roster_slot = "Taxi"
                    elif pid in reserve_ids:
                        roster_slot = "IR"
                    else:
                        roster_slot = "Bench"
                    player_rows.append({
                        "id": pid,
                        "name": full_name,
                        "position": p.get("position") or "—",
                        "team": p.get("team") or "FA",
                        "starter": pid in starter_ids,
                        "roster_slot": roster_slot,
                    })
                slot_order = {"Starter": 0, "Bench": 1, "IR": 2, "Taxi": 3}
                pos_order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DEF": 5}
                player_rows.sort(key=lambda p: (slot_order.get(p["roster_slot"], 9), pos_order.get(p["position"], 8), p["name"]))
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
                    "points_against": round((settings.get("fpts_against", 0) or 0) + (settings.get("fpts_against_decimal", 0) or 0) / 100, 2),
                    "max_points": round((settings.get("ppts", 0) or 0) + (settings.get("ppts_decimal", 0) or 0) / 100, 2),
                    "players": player_rows,
                })
            team_rows.sort(key=lambda t: (-t["wins"], t["losses"], -t["points_for"]))

            # Build a complete future-pick ledger, including untraded original picks.
            try:
                current_season = int(league.get("season") or utcnow().year)
            except (TypeError, ValueError):
                current_season = utcnow().year
            future_years = {current_season + offset for offset in (1, 2, 3)}
            future_years.update(
                int(pick.get("season"))
                for pick in traded_picks
                if str(pick.get("season") or "").isdigit() and int(pick.get("season")) > current_season
            )
            draft_rounds = int((league.get("settings") or {}).get("draft_rounds") or 4)
            roster_name_by_id = {int(team["roster_id"]): team["team_name"] for team in team_rows}
            traded_owner = {}
            for pick in traded_picks:
                try:
                    key = (int(pick.get("season")), int(pick.get("round")), int(pick.get("roster_id")))
                    traded_owner[key] = int(pick.get("owner_id"))
                except (TypeError, ValueError):
                    continue

            pick_ledger = []
            for season in sorted(future_years):
                for original_roster_id in sorted(roster_name_by_id):
                    for round_number in range(1, draft_rounds + 1):
                        current_owner_id = traded_owner.get(
                            (season, round_number, original_roster_id), original_roster_id
                        )
                        pick_ledger.append({
                            "season": season,
                            "round": round_number,
                            "original_roster_id": original_roster_id,
                            "original_team": roster_name_by_id.get(original_roster_id, f"Team {original_roster_id}"),
                            "current_owner_id": current_owner_id,
                            "current_owner": roster_name_by_id.get(current_owner_id, f"Team {current_owner_id}"),
                            "is_traded": current_owner_id != original_roster_id,
                        })

            for team in team_rows:
                roster_id = int(team["roster_id"])
                team["picks_owned"] = [p for p in pick_ledger if p["current_owner_id"] == roster_id]
                team["picks_traded_away"] = [
                    p for p in pick_ledger
                    if p["original_roster_id"] == roster_id and p["current_owner_id"] != roster_id
                ]
                team["pick_counts"] = {
                    str(round_number): sum(1 for p in team["picks_owned"] if p["round"] == round_number)
                    for round_number in range(1, draft_rounds + 1)
                }

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
                "pick_ledger": pick_ledger,
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



OWNER_DISPLAY_NAMES={"RichardDavis47":"Richard","danreilley":"Dan","davefedex":"Dave","garrettadame36":"Garrett","Mears30":"Matt","zkobes":"Zach","OGV":"Will","TheLandsharks":"Mike","anthonyrangel":"Anthony","Markgus13":"Mark"}
app = FastAPI(title="DTOS", version="0.2.0", lifespan=lifespan)


CSS = """
:root{--bg:#07111f;--panel:#101d2d;--line:#26374c;--text:#f5f7fb;--muted:#9fb0c6;--accent:#6ee7b7;--gold:#f5c451}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#07111f,#0b1727);color:var(--text);font-family:Inter,system-ui,-apple-system,sans-serif}
a{color:inherit;text-decoration:none}.wrap{max-width:1180px;margin:auto;padding:20px}.top{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:20px}
.brand h1{margin:0;font-size:28px}.brand p{margin:4px 0;color:var(--muted)}.btn{border:0;border-radius:10px;padding:11px 15px;background:var(--accent);color:#062018;font-weight:800;cursor:pointer}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.nav a{padding:9px 12px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:rgba(16,29,45,.94);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 10px 25px rgba(0,0,0,.15)}.card h2,.card h3{margin-top:0}.muted{color:var(--muted)}.good{color:var(--accent)}.warn{color:#fca5a5}
.stat{font-size:27px;font-weight:850}.team{margin-bottom:14px}.record{color:var(--gold);font-weight:800}.players{display:grid;gap:5px}.player{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid rgba(38,55,76,.65)}.starter{font-weight:800}.pill{font-size:12px;padding:3px 7px;border:1px solid var(--line);border-radius:999px;color:var(--muted)}
.team-link{display:block;transition:transform .15s ease,border-color .15s ease}.team-link:hover{transform:translateY(-2px);border-color:#3d5877}.team-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.rank-badge{min-width:38px;height:38px;border-radius:12px;background:#182a40;border:1px solid var(--line);display:grid;place-items:center;font-weight:900;color:var(--gold)}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.metric{background:#0b1727;border:1px solid var(--line);border-radius:10px;padding:10px}.metric b{display:block;font-size:17px}.metric span{font-size:11px;color:var(--muted)}.roster-section{margin-top:18px}.section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.slot-label{font-size:12px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.back{display:inline-block;margin-bottom:14px;color:var(--accent)}.pick-year{margin-top:14px}.pick-list{display:grid;gap:7px}.pick-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 0;border-top:1px solid rgba(38,55,76,.65)}.pick-origin{font-size:12px;color:var(--muted)}.away{color:#fca5a5}
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
        "version": "0.2.0",
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
        cards.append(
            f'<a class="card team team-link" href="/teams/{team["roster_id"]}">'
            f'<div class="team-head"><div><h3>{escape(team["team_name"])}</h3>'
            f'<div class="muted">{escape(team["owner"])}</div></div><div class="rank-badge">#{rank}</div></div>'
            f'<p class="record">{team["wins"]}-{team["losses"]}-{team["ties"]}</p>'
            f'<div class="metric-grid">'
            f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div>'
            f'<div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>'
            f'<div class="metric"><b>{starters}</b><span>Starters</span></div>'
            f'</div></a>'
        )
    return page(
        "Teams",
        '<h2>League Franchises</h2><p class="muted">Select a team for its complete roster and front-office summary.</p><div class="grid">'
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
    roster_html = []
    for slot in ("Starter", "Bench", "IR", "Taxi"):
        slot_players = [p for p in team["players"] if p["roster_slot"] == slot]
        if not slot_players:
            continue
        rows = "".join(
            f'<div class="player {"starter" if p["starter"] else ""}"><span>{escape(p["name"])}</span><span class="pill">{escape(p["position"])} · {escape(p["team"])}</span></div>'
            for p in slot_players
        )
        roster_html.append(
            f'<section class="roster-section"><div class="section-title"><span class="slot-label">{slot}</span>'
            f'<span class="muted">{len(slot_players)} players</span></div><div class="card players">{rows}</div></section>'
        )

    body = (
        f'<a class="back" href="/teams">← All Teams</a>'
        f'<section class="card"><div class="team-head"><div><div class="muted">Franchise #{rank}</div>'
        f'<h2>{escape(team["team_name"])}</h2><p class="muted">Owner: {escape(team["owner"])}</p></div>'
        f'<div class="rank-badge">#{rank}</div></div>'
        f'<div class="metric-grid">'
        f'<div class="metric"><b>{team["wins"]}-{team["losses"]}-{team["ties"]}</b><span>Record</span></div>'
        f'<div class="metric"><b>{team["points_for"]:.2f}</b><span>Points For</span></div>'
        f'<div class="metric"><b>{team["points_against"]:.2f}</b><span>Points Against</span></div>'
        f'<div class="metric"><b>{team["max_points"]:.2f}</b><span>Max PF</span></div>'
        f'<div class="metric"><b>{len(team["players"])}</b><span>Total Players</span></div>'
        f'<div class="metric"><b>{sum(1 for p in team["players"] if p["roster_slot"] == "Taxi")}</b><span>Taxi</span></div>'
        f'</div></section>'
    )

    owned_by_year = {}
    for pick in team.get("picks_owned", []):
        owned_by_year.setdefault(pick["season"], []).append(pick)
    owned_sections = []
    for season, picks in sorted(owned_by_year.items()):
        rows = "".join(
            f'<div class="pick-row"><div><b>Round {pick["round"]}</b>'
            f'<div class="pick-origin">{"Own pick" if not pick["is_traded"] else "From " + escape(pick["original_team"])}</div></div>'
            f'<span class="pill">{season}</span></div>'
            for pick in sorted(picks, key=lambda item: (item["round"], item["original_team"]))
        )
        owned_sections.append(
            f'<div class="pick-year"><div class="section-title"><span class="slot-label">{season}</span>'
            f'<span class="muted">{len(picks)} picks</span></div><div class="card pick-list">{rows}</div></div>'
        )

    away_rows = "".join(
        f'<div class="pick-row"><div><b>{pick["season"]} Round {pick["round"]}</b>'
        f'<div class="pick-origin away">Now owned by {escape(pick["current_owner"])}</div></div>'
        f'<span class="pill">Original</span></div>'
        for pick in sorted(team.get("picks_traded_away", []), key=lambda item: (item["season"], item["round"]))
    )
    firsts = team.get("pick_counts", {}).get("1", 0)
    seconds = team.get("pick_counts", {}).get("2", 0)
    total_picks = len(team.get("picks_owned", []))
    draft_capital = (
        f'<section class="roster-section"><div class="section-title"><span class="slot-label">Draft Capital</span>'
        f'<span class="muted">Current ownership and original source</span></div>'
        f'<div class="card"><div class="metric-grid">'
        f'<div class="metric"><b>{total_picks}</b><span>Total Picks</span></div>'
        f'<div class="metric"><b>{firsts}</b><span>Future 1sts</span></div>'
        f'<div class="metric"><b>{seconds}</b><span>Future 2nds</span></div></div></div>'
        f'{"".join(owned_sections)}'
        + (f'<div class="pick-year"><div class="section-title"><span class="slot-label away">Original Picks Traded Away</span>'
           f'<span class="muted">{len(team.get("picks_traded_away", []))} picks</span></div>'
           f'<div class="card pick-list">{away_rows}</div></div>' if away_rows else '')
        + '</section>'
    )
    body += draft_capital + "".join(roster_html)
    return page(team["team_name"], body)


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
