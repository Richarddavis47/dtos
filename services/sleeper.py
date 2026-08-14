"""Sleeper API synchronization and cache service for DTOS."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import threading
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app_metadata import APPLICATION_NAME, VERSION
from src.core.data_platform import data_platform
from src.core.data_platform.normalization import PlayerIdentityResolver
from src.core.data_platform.provider_activation import refresh_public_market
from src.core.intelligence.cache import intelligence_cache
from src.core.provider_network import build_provider_network
from src.core.projection_intelligence import projection_service
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import SleeperProjectionClient
from src.platform.lifecycle import lifecycle_coordinator
from src.core.valuation.automation import audit_market_calibration
from src.core.valuation_intelligence import build_valuation_intelligence
from services.history import capture_current_state, player_history_evidence
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
SYNC_LOCK = threading.Lock()
TRANSACTIONS_SYNC_LOCK = asyncio.Lock()
_LEAGUE_SYNC_LOCKS: dict[str, threading.Lock] = {}
_LEAGUE_TRANSACTION_LOCKS: dict[str, asyncio.Lock] = {}
SLEEPER_PROJECTION_CLIENT = SleeperProjectionClient(
    enabled=os.getenv("DTOS_SLEEPER_PROJECTIONS_ENABLED", "1").strip().lower()
    not in {"0", "false", "no", "off"}
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def league_cache_file(league_id: str) -> Path:
    """Resolve a league-specific cache while retaining the legacy default path."""
    if str(league_id) == str(LEAGUE_ID):
        return CACHE_FILE
    return CACHE_FILE.with_name(f"{CACHE_FILE.stem}.{league_id}{CACHE_FILE.suffix}")


def load_cache(
    *, state: dict[str, Any] | None = None, league_id: str = LEAGUE_ID,
) -> None:
    state = STATE if state is None else state
    cache_file = league_cache_file(league_id)
    if not cache_file.exists():
        return
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        cached_league = str(((payload.get("data") or {}).get("league") or {}).get("league_id") or league_id)
        if cached_league != str(league_id):
            raise ValueError("Cached Sleeper league identity does not match the requested runtime.")
        state.update(payload)
        state["syncing"] = False
        state["transactions_syncing"] = False
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not load cache: %s", exc)


def save_cache(
    *, state: dict[str, Any] | None = None, league_id: str = LEAGUE_ID,
) -> None:
    state = STATE if state is None else state
    cache_file = league_cache_file(league_id)
    temporary_path = None
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v for k, v in state.items() if not k.endswith("syncing")}
        encoder = json.JSONEncoder(separators=(",", ":"), ensure_ascii=False)
        with lifecycle_coordinator.phase("cache_persistence") as phase:
            phase.update({
                "serialization_state": "streaming",
                "cache_entry_count": len(payload),
            })
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=cache_file.parent,
                prefix=f".{cache_file.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temporary_path = handle.name
                for chunk in encoder.iterencode(payload):
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, cache_file)
            temporary_path = None
            phase["serialization_state"] = "complete"
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not save cache: %s", exc)
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


async def sleeper_get(client: httpx.AsyncClient, path: str) -> Any:
    return await data_platform.get_json(client, f"{SLEEPER_BASE}{path}")


def request_headers() -> dict[str, str]:
    """Return the shared DTOS identity used for Sleeper requests."""
    return {"User-Agent": f"{APPLICATION_NAME}/{VERSION} (+Front Office OS)"}


async def _sync_sleeper(
    force_players: bool = False,
    *,
    league_id: str = LEAGUE_ID,
    state: dict[str, Any] = STATE,
    projections: ProjectionService = projection_service,
) -> dict[str, Any]:
    """Fetch and normalize one explicitly identified Sleeper league state."""
    runtime_lock = _LEAGUE_SYNC_LOCKS.setdefault(str(league_id), threading.Lock())
    with runtime_lock:
        if state["syncing"]:
            return state
        state["syncing"] = True
        try:
            lifecycle_context = lifecycle_coordinator.phase("sleeper_sync")
            lifecycle_context.__enter__()
            timeout = httpx.Timeout(REQUEST_TIMEOUT)
            async with httpx.AsyncClient(
                timeout=timeout, headers=request_headers()
            ) as client:
                league, users, rosters, traded_picks, drafts, nfl_state = await asyncio.gather(
                    sleeper_get(client, f"/league/{league_id}"),
                    sleeper_get(client, f"/league/{league_id}/users"),
                    sleeper_get(client, f"/league/{league_id}/rosters"),
                    sleeper_get(client, f"/league/{league_id}/traded_picks"),
                    sleeper_get(client, f"/league/{league_id}/drafts"),
                    sleeper_get(client, "/state/nfl"),
                )

                week = int((nfl_state or {}).get("week") or 1)
                season_type = (nfl_state or {}).get("season_type") or "regular"
                matchup_week = week if season_type in {"regular", "post"} else 1

                matchups, transactions, trending_adds, trending_drops = await asyncio.gather(
                    sleeper_get(client, f"/league/{league_id}/matchups/{matchup_week}"),
                    sleeper_get(client, f"/league/{league_id}/transactions/{matchup_week}"),
                    sleeper_get(client, "/players/nfl/trending/add?lookback_hours=24&limit=50"),
                    sleeper_get(client, "/players/nfl/trending/drop?lookback_hours=24&limit=50"),
                )
                draft_picks = []
                for draft in drafts or ():
                    draft_id = str(draft.get("draft_id") or "")
                    if draft_id and str(draft.get("status") or "").casefold() == "complete":
                        draft_picks.extend(await sleeper_get(client, f"/draft/{draft_id}/picks") or ())

                cached_players = (state.get("data") or {}).get("players") or {}
                players_fetched_at = (state.get("data") or {}).get("players_fetched_at")
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
                    client, (state.get("data") or {}).get("market_data")
                )
                projection_payload = None
                projection_bytes = 0
                projection_transport = None
                projection_week_payloads: list[tuple[int, Any]] = []
                projection_claimed = projections.begin_external_refresh()
                if projection_claimed:
                    projection_season = int((nfl_state or {}).get("season") or league.get("season") or utcnow().year)
                    try:
                        projection_payload, projection_bytes, projection_transport = await SLEEPER_PROJECTION_CLIENT.fetch(
                            client,
                            season=projection_season,
                            week=matchup_week,
                        )
                        cached_weeks = set(projections.cached_weeks(projection_season))
                        for projection_week in range(1, 19):
                            if projection_week == matchup_week or projection_week in cached_weeks:
                                continue
                            try:
                                week_payload, week_bytes, _week_transport = await SLEEPER_PROJECTION_CLIENT.fetch(
                                    client, season=projection_season, week=projection_week,
                                )
                                projection_week_payloads.append((projection_week, week_payload))
                                projection_bytes += week_bytes
                            except Exception as exc:
                                logger.info(
                                    "Sleeper projection Week %s is unavailable: %s",
                                    projection_week, type(exc).__name__,
                                )
                    except Exception as exc:
                        projections.fail_external_refresh(
                            exc, transport_details=SLEEPER_PROJECTION_CLIENT.last_transport,
                        )
                        logger.warning("Optional Sleeper projection refresh failed: %s", type(exc).__name__)

            user_by_id = {str(u.get("user_id")): u for u in users}
            team_rows = []
            history_by_player: dict[str, dict[str, Any]] = {}
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
                    if pid not in history_by_player:
                        history_by_player[pid] = player_history_evidence(league_id, pid)
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
                        "historical_evidence": history_by_player[pid],
                    })
                slot_order = {"Starter": 0, "Bench": 1, "IR": 2, "Taxi": 3}
                pos_order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DEF": 5}
                player_rows.sort(key=lambda p: (slot_order.get(p["roster_slot"], 9), pos_order.get(p["position"], 8), p["name"]))
                team_rows.append({
                    "roster_id": roster.get("roster_id"),
                    "owner_id": owner_id,
                    "owner": owner.get("display_name") or owner.get("username") or "Unassigned",
                    "team_name": metadata.get("team_name") or owner.get("display_name") or "Unassigned Franchise",
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
                            "original_team": roster_name_by_id.get(original_roster_id, "Unassigned Franchise"),
                            "current_owner_id": current_owner_id,
                            "current_owner": roster_name_by_id.get(current_owner_id, "Unassigned Franchise"),
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
            previous_data = state.get("data") or {}
            retained_history = {
                "calibration_state": previous_data.get("calibration_state") or {},
                "calibration_history": previous_data.get("calibration_history") or [],
                "provider_reliability_history": previous_data.get("provider_reliability_history") or [],
                "valuation_intelligence_timeline": previous_data.get("valuation_intelligence_timeline") or {},
                "valuation_intelligence": previous_data.get("valuation_intelligence") or {},
                "brain_semantic_metrics": previous_data.get("brain_semantic_metrics") or {},
            }
            state["data"] = {
                "league": league,
                "scoring_settings": league.get("scoring_settings") or {},
                "league_settings": league.get("settings") or {},
                "roster_positions": league.get("roster_positions") or [],
                "owners": users,
                "teams": team_rows,
                "traded_picks": traded_picks,
                "pick_ledger": pick_ledger,
                "drafts": drafts,
                "draft_picks": draft_picks,
                "transactions": transactions,
                "matchups": matchup_groups,
                "nfl_state": nfl_state,
                "week": matchup_week,
                "players": players,
                "normalized_players": normalized_players,
                "trending_players": {"adds": trending_adds, "drops": trending_drops, "source": "Sleeper", "updated_at": utcnow().isoformat()},
                "players_fetched_at": players_fetched_at,
                "market_data": market_data,
                **retained_history,
            }
            # Drop synchronization-only references before provider, valuation,
            # and persistence phases allocate their own bounded working sets.
            del previous_data, retained_history, cached_players
            del history_by_player, user_by_id, matchup_by_roster, resolver
            state["last_sync"] = synced_at
            state["last_error"] = None
            state["transactions_last_sync"] = synced_at
            state["transactions_last_error"] = None
            from src.core.historical_memory import historical_store
            from src.core.relevant_players import (
                apply_relevant_player_filter, build_relevant_player_universe,
            )

            state["data"]["relevant_player_universe"] = await asyncio.to_thread(
                build_relevant_player_universe,
                state["data"], historical_store, league_id,
            )
            apply_relevant_player_filter(
                state["data"], state["data"]["relevant_player_universe"],
            )
            try:
                with lifecycle_coordinator.phase("provider_network") as phase:
                    await asyncio.to_thread(build_provider_network, state["data"], state)
                    phase["provider_count"] = len(
                        (state["data"].get("provider_network") or {}).get("providers") or []
                    )
                try:
                    if projection_payload is not None:
                        scoring = state["data"].get("scoring_settings") or (
                            state["data"].get("league") or {}
                        ).get("scoring_settings") or {}
                        for projection_week, week_payload in projection_week_payloads:
                            await asyncio.to_thread(
                                projections.cache_sleeper_week, week_payload,
                                scoring=scoring,
                                season=int((nfl_state or {}).get("season") or league.get("season") or utcnow().year),
                                week=projection_week,
                            )
                        await asyncio.to_thread(
                            projections.ingest_sleeper,
                            projection_payload,
                            data=state["data"],
                            league_id=league_id,
                            season=int((nfl_state or {}).get("season") or league.get("season") or utcnow().year),
                            week=matchup_week,
                            response_bytes=projection_bytes,
                            transport_details=projection_transport,
                        )
                    else:
                        restored = projections.restore_into(state["data"])
                        if not restored:
                            await asyncio.to_thread(
                                projections.generate, state["data"], league_id,
                            )
                except Exception:
                    logger.exception(
                        "Projection generation failed; canonical intelligence will publish an explicit unavailable state"
                    )
                with lifecycle_coordinator.phase("valuation_intelligence") as phase:
                    await asyncio.to_thread(build_valuation_intelligence, state["data"], state)
                    phase["canonical_generation"] = (
                        state["data"].get("valuation_intelligence") or {}
                    ).get("generated_at")
                await asyncio.to_thread(audit_market_calibration, state["data"], state, apply=True)
            except Exception:
                logger.exception("Provider network or automated market calibration audit failed")
                state["data"]["calibration_error"] = "Provider evidence evaluation failed; no model adjustment was applied."
            capture_current_state(state["data"], synced_at)
            from src.core.intelligence_memory import checkpoint_pipeline
            try:
                await asyncio.to_thread(
                    checkpoint_pipeline.ingest_runtime, state["data"], observed_at=synced_at,
                )
            except Exception:
                logger.exception("Intelligence checkpoint ingestion failed")
            save_cache(state=state, league_id=league_id)
            intelligence_cache.invalidate("snapshot:")
            intelligence_cache.invalidate("crawl:")
            logger.info("Sleeper sync complete: %s teams", len(team_rows))
        except Exception as exc:
            state["last_error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Sleeper sync failed")
        finally:
            state["syncing"] = False
            if "lifecycle_context" in locals():
                lifecycle_context.__exit__(None, None, None)
        return state


async def sync_sleeper(force_players: bool = False) -> dict[str, Any]:
    """Synchronize Sleeper without blocking the application event loop."""
    return await asyncio.to_thread(
        lambda: asyncio.run(_sync_sleeper(force_players=force_players)),
    )


async def sync_sleeper_league(
    league_id: str,
    state: dict[str, Any],
    *,
    force_players: bool = False,
    projections: ProjectionService | None = None,
) -> dict[str, Any]:
    """Synchronize a league without replacing process-global league state."""
    service = projections or ProjectionService(league_id=str(league_id))
    return await asyncio.to_thread(
        lambda: asyncio.run(_sync_sleeper(
            force_players=force_players,
            league_id=str(league_id),
            state=state,
            projections=service,
        )),
    )


async def sync_transactions(
    *, state: dict[str, Any] = STATE, league_id: str = LEAGUE_ID,
) -> bool:
    """Refresh only the cached transaction list from Sleeper."""
    transaction_lock = _LEAGUE_TRANSACTION_LOCKS.setdefault(
        str(league_id), asyncio.Lock(),
    )
    async with transaction_lock:
        if state.get("transactions_syncing"):
            return False
        state["transactions_syncing"] = True
        try:
            data = state.get("data") or {}
            if not data:
                raise RuntimeError("League data must be loaded before refreshing transactions.")
            week = int(data.get("week") or 1)
            timeout = httpx.Timeout(REQUEST_TIMEOUT)
            async with httpx.AsyncClient(
                timeout=timeout, headers=request_headers()
            ) as client:
                transactions = await sleeper_get(
                    client, f"/league/{league_id}/transactions/{week}"
                )
            data["transactions"] = transactions
            state["transactions_last_sync"] = utcnow().isoformat()
            state["transactions_last_error"] = None
            from src.core.intelligence_memory import checkpoint_pipeline
            await asyncio.to_thread(
                checkpoint_pipeline.ingest_transactions, data, transactions,
                observed_at=state["transactions_last_sync"],
            )
            save_cache(state=state, league_id=league_id)
            intelligence_cache.invalidate("snapshot:")
            intelligence_cache.invalidate("crawl:")
            logger.info("Transaction sync complete: %s transactions", len(transactions))
            return True
        except Exception as exc:
            state["transactions_last_error"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Transaction sync failed")
            return False
        finally:
            state["transactions_syncing"] = False



async def ensure_data_fresh() -> None:
    """Queue a cached Sleeper refresh without delaying the calling route."""
    if not STATE.get("data"):
        start_sleeper_sync(force_players=True)
        return
    last_sync = STATE.get("last_sync")
    if not last_sync:
        start_sleeper_sync()
        return
    try:
        age = utcnow() - datetime.fromisoformat(last_sync)
    except (TypeError, ValueError):
        start_sleeper_sync()
        return
    if age > timedelta(minutes=SYNC_MINUTES):
        start_sleeper_sync()


_SLEEPER_SYNC_TASK: asyncio.Task[dict[str, Any]] | None = None


def start_sleeper_sync(
    *, force_players: bool = False,
) -> asyncio.Task[dict[str, Any]]:
    """Return the one tracked in-process refresh task for this app worker."""
    global _SLEEPER_SYNC_TASK
    if _SLEEPER_SYNC_TASK is None or _SLEEPER_SYNC_TASK.done():
        _SLEEPER_SYNC_TASK = asyncio.create_task(
            sync_sleeper(force_players=force_players),
            name="dtos-sleeper-sync",
        )
    return _SLEEPER_SYNC_TASK

