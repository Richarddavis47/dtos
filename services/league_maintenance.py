"""Lifecycle-owned refresh of resident leagues, never account-wide eager loading."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from src.core.league_runtime import LeagueRuntime, RuntimeState


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

    task = asyncio.create_task(maintain(), name=name)
    runtime.background_tasks.add(task)
    task.add_done_callback(runtime.background_tasks.discard)
