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
from src.platform.memory_reclamation import reclaim_unused_analytical_memory
from src.platform.fois_admission import (
    WORKING_RESERVE_BYTES as FOIS_WORKING, SAFETY_MARGIN_BYTES as FOIS_SAFETY,
)
from src.platform.cache_restoration_admission import (
    MIB as MIB, SERVICE_LIMIT, CACHE_EXPANSION_FACTOR, CACHE_MINIMUM_WORKING,
    CACHE_SAFETY, restoration_admission,
)
# JSON decoding plus consumer generation fingerprints have separate temporary
# representations. Reserve conservatively from serialized size; never discount
# file cache or borrow the FOIS/Trade working reservations.


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
                # Existing FOIS allocations are already in cgroup current, but
                # its outstanding demand is not. Do not spend the analytical
                # owner's reserve on a newly decoded league. No RSS subtraction
                # or file-cache credit is treated as committed free capacity.
                plan = restoration_admission(
                    stat.st_size, sample, lifecycle_coordinator.fois_generation_active(),
                    fois_working_bytes=FOIS_WORKING, fois_safety_bytes=FOIS_SAFETY,
                    expansion_factor=CACHE_EXPANSION_FACTOR,
                    minimum_working_bytes=CACHE_MINIMUM_WORKING,
                    cache_safety_bytes=CACHE_SAFETY, service_limit_bytes=SERVICE_LIMIT,
                )
                if (plan['would_admit'] is False
                        and plan['headroom_bytes'] >= plan['safety_bytes']):
                    # This cold reader already owns the existing phase and pins
                    # its file generation. Reclaim only unusable cache entries
                    # and idle execution resources, as explicit Trade already
                    # does. Never evict active/unexpired contexts or discount
                    # file pages. Keep the existing safety margin available even
                    # for cleanup; unknown/near-limit samples defer immediately.
                    recovery = {'attempted': True, 'before_bytes': sample['cgroup_current_bytes']}
                    try:
                        recovery.update(reclaim_unused_analytical_memory())
                    except Exception:
                        # Optional cleanup failure is not a Sleeper/source error
                        # or permission to decode. Only fresh measured admission
                        # can permit the next allocation.
                        recovery['cleanup_unavailable'] = True
                    sample = memory_snapshot()
                    plan = restoration_admission(
                        stat.st_size, sample, lifecycle_coordinator.fois_generation_active(),
                        fois_working_bytes=FOIS_WORKING, fois_safety_bytes=FOIS_SAFETY,
                        expansion_factor=CACHE_EXPANSION_FACTOR,
                        minimum_working_bytes=CACHE_MINIMUM_WORKING,
                        cache_safety_bytes=CACHE_SAFETY, service_limit_bytes=SERVICE_LIMIT,
                    )
                    recovery.update(after_bytes=sample.get('cgroup_current_bytes'),
                                    required_bytes=plan['required_bytes'],
                                    would_admit=plan['would_admit'])
                    runtime.lifecycle['cache_restore_memory_recovery'] = recovery
                if plan['would_admit'] is not True:
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
