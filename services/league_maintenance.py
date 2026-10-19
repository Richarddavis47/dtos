"""Lifecycle-owned refresh of resident leagues, never account-wide eager loading."""
from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any, Awaitable, Callable

from src.core.league_runtime import LeagueRuntime, RuntimeState


def ensure_fois_refresh(runtime: LeagueRuntime, generate: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
    """One optional, lifecycle-owned attempt; browsing never waits or retries it."""
    name = 'dtos-league-fois'
    if runtime.status in {RuntimeState.EVICTING, RuntimeState.CLOSED} or any(
        task.get_name() == name and not task.done() for task in runtime.background_tasks
    ):
        return

    async def maintain() -> None:
        started = perf_counter()
        data = runtime.state.get('data') or {}
        generations = dict(runtime.source_generations)
        runtime.lifecycle['fois_generation'] = 'running'
        context = runtime.canonical_context
        retained = context is not None and context.fois_state == 'retained'
        if context is not None:
            context.fois_state = 'pending'
        try:
            scores = await generate(data)
        except asyncio.CancelledError:
            runtime.lifecycle['fois_generation'] = 'cancelled'
            raise
        except Exception as exc:
            # The generator records its failure. Never turn an optional failure
            # into loss of canonical league/history facts or a fabricated grade.
            runtime.lifecycle['fois_generation'] = 'failed'
            runtime.lifecycle['fois_error_type'] = type(exc).__name__
            state = 'retained' if retained else 'unavailable'
        else:
            compatible = runtime.state.get('data') is data and runtime.source_generations == generations
            state = 'ready' if scores and compatible else 'retained' if scores or retained else 'unavailable'
            runtime.lifecycle['fois_generation'] = 'complete' if compatible else 'superseded'
            runtime.lifecycle.pop('fois_error_type', None)
            runtime.lifecycle['fois_last_run'] = getattr(scores[0], 'generated_at', None) if scores else None
            runtime.lifecycle['fois_records'] = len(scores or ())
        runtime.lifecycle['fois_duration_ms'] = round((perf_counter() - started) * 1000, 3)
        current = runtime.canonical_context
        if current is not None and runtime.status not in {RuntimeState.EVICTING, RuntimeState.CLOSED}:
            current.fois_state = state

    task = asyncio.create_task(maintain(), name=name)
    runtime.background_tasks.add(task)
    task.add_done_callback(runtime.background_tasks.discard)


def ensure_periodic_refresh(
    runtime: LeagueRuntime,
    refresh: Callable[[LeagueRuntime], Awaitable[Any]],
    *, interval_seconds: float,
) -> None:
    """Attach one cancellable maintenance loop to an already resident runtime."""
    name = "dtos-resident-league-refresh"
    if any(task.get_name() == name and not task.done() for task in runtime.background_tasks):
        return

    async def maintain() -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            if runtime.status is not RuntimeState.WARM:
                return
            runtime.lifecycle["refresh_state"] = "running"
            worker = asyncio.create_task(refresh(runtime))
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                # Runtime.close() must not release state before a writer exits.
                await asyncio.gather(worker, return_exceptions=True)
                raise
            except Exception as exc:
                runtime.lifecycle["refresh_state"] = "failed"
                runtime.lifecycle["refresh_error_type"] = type(exc).__name__
            else:
                runtime.lifecycle["refresh_state"] = (
                    "failed" if runtime.state.get("last_error") else "complete"
                )
                runtime.lifecycle.pop("refresh_error_type", None)
                from src.platform.storage_accounting import periodic_storage_accounting
                await asyncio.to_thread(periodic_storage_accounting)

    task = asyncio.create_task(maintain(), name=name)
    runtime.background_tasks.add(task)
    task.add_done_callback(runtime.background_tasks.discard)
