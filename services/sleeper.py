"""Sleeper API synchronization and cache service for DTOS."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app_metadata import APPLICATION_NAME, VERSION
from src.core.data_platform import data_platform
from src.core.data_platform.normalization import PlayerIdentityResolver
from src.core.data_platform.provider_activation import refresh_public_market
from src.core.intelligence.cache import intelligence_cache
from config import (
    CACHE_FILE,
    LEAGUE_ID,
    LOG_LEVEL,
    REQUEST_TIMEOUT,
    SLEEPER_BASE,
    SYNC_MINUTES,
)

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("dtos.sleeper")

STATE: dict[str, Any] = {
    "data": {},
    "last_sync": None,
    "last_error": None,
    "syncing": False,
    "transactions_last_sync": None,
    "transactions_last_error": None,
    "transactions_syncing": False,
}
SYNC_LOCK = asyncio.Lock()
TRANSACTIONS_SYNC_LOCK = asyncio.Lock()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_cache() -> None:
    if not CACHE_FILE.exists():
        return
    try:
        payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        STATE.update(payload)
        STATE["syncing"] = False
        STATE["transactions_syncing"] = False
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not load cache: %s", exc)


def save_cache() -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps(
                {k: v for k, v in STATE.items() if not k.endswith("syncing")}
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not save cache: %s", exc)


async def sleeper_get(client: httpx.AsyncClient, path: str) -> Any:
    return await data_platform.get_json(client, f"{SLEEPER_BASE}{path}")


def request_headers() -> dict[str, str]:
    """Return the shared DTOS identity used for Sleeper requests."""
    return {"User-Agent": f"{APPLICATION_NAME}/{VERSION} (+Front Office OS)"}


async def sync_sleeper(force_players: bool = False) -> dict[str, Any]:
    """Fetch and normalize the configured Sleeper league state."""
    async with SYNC_LOCK:
        if STATE["syncing"]:
            return STATE
        STATE["syncing"] = True
        try:
            timeout = httpx.Timeout(REQUEST_TIMEOUT)
            async with httpx.AsyncClient(
                timeout=timeout, headers=request_headers()
            ) as client:
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

                matchups, transactions, trending_adds, trending_drops = await asyncio.gather(
                    sleeper_get(client, f"/league/{LEAGUE_ID}/matchups/{matchup_week}"),
                    sleeper_get(client, f"/league/{LEAGUE_ID}/transactions/{matchup_week}"),
                    sleeper_get(client, "/players/nfl/trending/add?lookback_hours=24&limit=50"),
                    sleeper_get(client, "/players/nfl/trending/drop?lookback_hours=24&limit=50"),
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

                market_data = await refresh_public_market(
                    client, (STATE.get("data") or {}).get("market_data")
                )

            user_by_id = {str(u.get("user_id")): u for u in users}
            team_rows = []
            for roster in rosters:
                owner_id = str(roster.get("owner_id") or "")
                owner = user_by_id.get(owner_id, {})
                metadata = owner.get("metadata") or {}
                settings = roster.get("settings") or {}
                player_ids = roster.get("players") or []
                starter_list = [str(x) for x in (roster.get("starters") or [])]
                starter_ids = set(starter_list)
                starter_index = {pid: idx for idx, pid in enumerate(starter_list)}
                lineup_slots = [slot for slot in (league.get("roster_positions") or []) if slot not in {"BN", "IR", "TAXI"}]
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
                        "team": p.get("team") or "Vacant",
                        "age": p.get("age"),
                        "bye_week": p.get("bye_week"),
                        "starter": pid in starter_ids,
                        "starter_index": starter_index.get(pid),
                        "starter_slot": lineup_slots[starter_index[pid]] if pid in starter_index and starter_index[pid] < len(lineup_slots) else None,
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
                players_points = m.get("players_points") or {}
                starters = [str(x) for x in (m.get("starters") or [])]
                starter_points_list = m.get("starters_points") or []
                starter_points = {
                    pid: float(starter_points_list[index] or 0)
                    if index < len(starter_points_list) else float(players_points.get(pid, 0) or 0)
                    for index, pid in enumerate(starters)
                }
                team_player_by_id = {str(p["id"]): p for p in team.get("players", [])}
                lineup = []
                for index, player_id in enumerate(starters):
                    player = team_player_by_id.get(player_id, {
                        "id": player_id, "name": player_id, "position": "—", "team": "Vacant"
                    })
                    lineup.append({
                        "id": player_id,
                        "name": player.get("name") or player_id,
                        "position": player.get("position") or "—",
                        "nfl_team": player.get("team") or "Vacant",
                        "slot": player.get("starter_slot") or (
                            lineup_slots[index] if index < len(lineup_slots) else "START"
                        ),
                        "points": round(float(starter_points.get(player_id, 0) or 0), 2),
                    })
                bench = []
                for player_id in (m.get("players") or []):
                    pid = str(player_id)
                    if pid in set(starters):
                        continue
                    player = team_player_by_id.get(pid)
                    if not player:
                        continue
                    bench.append({
                        "id": pid,
                        "name": player.get("name") or pid,
                        "position": player.get("position") or "—",
                        "nfl_team": player.get("team") or "Vacant",
                        "points": round(float(players_points.get(pid, 0) or 0), 2),
                    })
                matchup_groups.setdefault(matchup_id, []).append({
                    "team": team["team_name"],
                    "owner": team["owner"],
                    "points": round(float(m.get("points", 0) or 0), 2),
                    "custom_points": m.get("custom_points"),
                    "roster_id": team["roster_id"],
                    "record": f'{team["wins"]}-{team["losses"]}-{team["ties"]}',
                    "lineup": lineup,
                    "bench": sorted(bench, key=lambda p: (-p["points"], p["name"])),
                })

            resolver = PlayerIdentityResolver(players if isinstance(players, dict) else {})
            normalized_players = {player_id: asdict(player) for player_id in players if (player := resolver.resolve(player_id))} if isinstance(players, dict) else {}
            synced_at = utcnow().isoformat()
            for provider_name, records in (
                ("Sleeper Players", len(players) if isinstance(players, dict) else 0),
                ("Sleeper Trending", len(trending_adds) + len(trending_drops)),
                ("Sleeper Transactions", len(transactions)),
            ):
                market_data["provider_status"][provider_name] = {
                    "enabled": True,
                    "status": "healthy",
                    "last_refresh": synced_at,
                    "next_refresh": (utcnow() + timedelta(minutes=SYNC_MINUTES)).isoformat(),
                    "refresh_result": "success",
                    "records_retrieved": records,
                    "reason": None,
                }
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
                "normalized_players": normalized_players,
                "trending_players": {"adds": trending_adds, "drops": trending_drops, "source": "Sleeper", "updated_at": utcnow().isoformat()},
                "players_fetched_at": players_fetched_at,
                "market_data": market_data,
            }
            STATE["last_sync"] = synced_at
            STATE["last_error"] = None
            STATE["transactions_last_sync"] = synced_at
            STATE["transactions_last_error"] = None
            save_cache()
            intelligence_cache.invalidate("snapshot:")
            logger.info("Sleeper sync complete: %s teams", len(team_rows))
        except Exception as exc:
            STATE["last_error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Sleeper sync failed")
        finally:
            STATE["syncing"] = False
        return STATE


async def sync_transactions() -> bool:
    """Refresh only the cached transaction list from Sleeper."""
    async with TRANSACTIONS_SYNC_LOCK:
        if STATE.get("transactions_syncing"):
            return False
        STATE["transactions_syncing"] = True
        try:
            data = STATE.get("data") or {}
            if not data:
                raise RuntimeError("League data must be loaded before refreshing transactions.")
            week = int(data.get("week") or 1)
            timeout = httpx.Timeout(REQUEST_TIMEOUT)
            async with httpx.AsyncClient(
                timeout=timeout, headers=request_headers()
            ) as client:
                transactions = await sleeper_get(
                    client, f"/league/{LEAGUE_ID}/transactions/{week}"
                )
            data["transactions"] = transactions
            STATE["transactions_last_sync"] = utcnow().isoformat()
            STATE["transactions_last_error"] = None
            save_cache()
            intelligence_cache.invalidate("snapshot:")
            logger.info("Transaction sync complete: %s transactions", len(transactions))
            return True
        except Exception as exc:
            STATE["transactions_last_error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Transaction sync failed")
            return False
        finally:
            STATE["transactions_syncing"] = False



async def ensure_data_fresh() -> None:
    """Refresh cached Sleeper data when it is missing or stale."""
    if not STATE.get("data"):
        await sync_sleeper(force_players=True)
        return
    last_sync = STATE.get("last_sync")
    if not last_sync:
        await sync_sleeper()
        return
    try:
        age = utcnow() - datetime.fromisoformat(last_sync)
    except (TypeError, ValueError):
        await sync_sleeper()
        return
    if age > timedelta(minutes=SYNC_MINUTES):
        await sync_sleeper()

