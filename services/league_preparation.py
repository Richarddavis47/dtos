"""Restore the existing bounded Sleeper cache without a source synchronization.

This is a read of the last admitted source publication, never a new source,
freshness claim, price database, history import or analytical generation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import json
import os
import time
from typing import Callable

from services.sleeper import league_cache_file
from src.core.league_runtime import LeagueRuntime
from src.core.sync_status import safe_sync_state
from src.platform.cache_budget import JSON_BUDGET, reusable
from src.platform.lifecycle import HeavyWorkDeferred, lifecycle_coordinator, memory_snapshot

MIB = 1024 * 1024
SERVICE_LIMIT = 2 * 1024 * MIB
# JSON decoding plus consumer generation fingerprints have separate temporary
# representations. Reserve conservatively from serialized size; never discount
# file cache or borrow the FOIS/Trade working reservations.
CACHE_EXPANSION_FACTOR = 16
CACHE_MINIMUM_WORKING = 128 * MIB
CACHE_SAFETY = 128 * MIB


async def restore_cached_runtime_owned(runtime: LeagueRuntime, publish: Callable[[LeagueRuntime], None],
                                       *, expected_season: int | None = None) -> bool:
    """Eviction/shutdown must collect the reader before releasing its state."""
    worker = asyncio.create_task(asyncio.to_thread(
        restore_cached_runtime, runtime, publish, expected_season=expected_season,
    ), name='dtos-league-cache-restore')
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not worker.cancelled():
            worker.exception()
        raise


def restore_cached_runtime(runtime: LeagueRuntime, publish: Callable[[LeagueRuntime], None],
                           *, expected_season: int | None = None) -> bool:
    path = league_cache_file(runtime.league_id)
    if not reusable(path, JSON_BUDGET):
        runtime.lifecycle['cache_restore'] = 'not_reusable'
        return False
    # No unbounded waiting or new worker process. This lease blocks new FOIS
    # starts and sync allocations, while an existing FOIS can finish normally.
    with lifecycle_coordinator.phase('cache_persistence', wait=False):
        try:
            with path.open(encoding='utf-8') as handle:
                # Pin the opened generation before measuring. An atomic source
                # replacement must not turn a small-file reservation into a
                # larger decode after admission.
                stat = os.fstat(handle.fileno())
                if (stat.st_size > JSON_BUDGET.maximum_entry_bytes
                        or not 0 <= time.time() - stat.st_mtime <= JSON_BUDGET.maximum_age_seconds):
                    raise ValueError('Saved publication outside retention policy')
                sample = memory_snapshot()
                used, limit = sample.get('cgroup_current_bytes'), sample.get('cgroup_limit_bytes')
                required = max(CACHE_MINIMUM_WORKING, stat.st_size * CACHE_EXPANSION_FACTOR) + CACHE_SAFETY
                if (type(used) is not int or type(limit) is not int or used < 0 or limit <= 0
                        or min(limit, SERVICE_LIMIT) - used < required):
                    raise HeavyWorkDeferred('Saved league preparation is waiting for safe memory headroom.')
                payload = json.load(handle)
            data = payload['data']
            league = data['league']
            observed = datetime.fromisoformat(payload['last_sync'])
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - observed).total_seconds()
            season = int(league['season'])
            if (str(league.get('league_id')) != runtime.league_id
                    or expected_season is not None and season != expected_season
                    or str(data.get('season', season)) != str(season)
                    or not 0 <= age <= JSON_BUDGET.maximum_age_seconds
                    or not isinstance(data.get('teams'), list) or not data['teams']
                    or not isinstance(league.get('scoring_settings'), dict)
                    or not isinstance(league.get('roster_positions'), list)
                    or data.get('scoring_settings', league['scoring_settings']) != league['scoring_settings']
                    or data.get('roster_positions', league['roster_positions']) != league['roster_positions']):
                raise ValueError('Incompatible saved publication')
            from src.core.intelligence.team_strength import restore_cached_week_keys
            restore_cached_week_keys(data)
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            runtime.lifecycle['cache_restore'] = 'incompatible'
            return False
        runtime.state.update(safe_sync_state(payload))
        runtime.state.update(syncing=False, transactions_syncing=False, preparation_state='last_valid')
        runtime.apply_data(data)
        publish(runtime)
        runtime.lifecycle['cache_restore'] = 'restored'
        runtime.lifecycle['preparation_state'] = 'last_valid'
        return True
