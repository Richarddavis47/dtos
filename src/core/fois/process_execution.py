"""Bounded spawned-process execution for canonical FOIS generation."""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import multiprocessing
import os
import shutil
import tempfile
import threading
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from time import perf_counter
from typing import Any

from config import (
    INTELLIGENCE_CHECKPOINT_FILE, METADATA_DATABASE_FILE,
    SLEEPER_SEASON_CACHE_ROOT,
)
from src.core.fois.models import FOIS_MODEL_VERSION
from src.platform.validation.progress import progress_from_environment

FOIS_PROCESS_TIMEOUT_SECONDS = 60.0
_EXECUTOR: concurrent.futures.ProcessPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def _worker_ready() -> dict[str, int]:
    """Import the complete compute path before the web process accepts traffic."""
    import psutil
    from src.core.fois.history import load_results_history  # noqa: F401
    from src.core.fois.repository import FOISRepository  # noqa: F401
    from src.core.fois.service import FOISService  # noqa: F401
    from src.core.history_context import canonical_history_store  # noqa: F401

    return {
        "pid": os.getpid(),
        "rss_bytes": psutil.Process(os.getpid()).memory_info().rss,
    }


def _executor() -> concurrent.futures.ProcessPoolExecutor:
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = concurrent.futures.ProcessPoolExecutor(
                max_workers=1,
                mp_context=multiprocessing.get_context("spawn"),
            )
        return _EXECUTOR


async def warm_fois_executor() -> dict[str, int]:
    """Start exactly one clean compute worker before request acceptance."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor(), _worker_ready)


async def shutdown_fois_executor() -> None:
    """Reap the one bounded compute worker without blocking the event loop."""
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        executor, _EXECUTOR = _EXECUTOR, None
    if executor is not None:
        await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)


def compact_fois_input(data: dict[str, Any]) -> dict[str, Any]:
    """Return only canonical fields consumed by isolated FOIS generation."""
    teams = data.get("teams") or []
    asset_ids = {
        f"player:{player.get('id') or player.get('player_id')}"
        for team in teams
        for player in team.get("players") or ()
        if isinstance(player, dict) and (player.get("id") or player.get("player_id"))
    }
    report = data.get("valuation_intelligence") or {}
    compact_report = {
        name: value
        for name, value in report.items()
        if name not in {"assets", "timeline"}
    }
    compact_report["assets"] = {
        asset_id: row
        for asset_id, row in (report.get("assets") or {}).items()
        if asset_id in asset_ids
    }
    compact_report["timeline"] = {
        asset_id: row
        for asset_id, row in (report.get("timeline") or {}).items()
        if asset_id in asset_ids
    }
    compact = {
        name: data[name]
        for name in ("league", "league_settings", "teams", "brain_semantic_metrics")
        if name in data
    }
    if report:
        compact["valuation_intelligence"] = compact_report
    if "fois_history" in data:
        compact["fois_history"] = data["fois_history"]
    return compact


def _compute_fois_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one immutable compact FOIS work unit in the persistent child."""
    progress = progress_from_environment()
    record = progress.record if progress is not None else lambda *_args, **_kwargs: None
    record("fois_child_phase", phase="compute", status="started")
    import psutil
    from src.core.fois.history import load_results_history
    from src.core.fois.repository import FOISRepository
    from src.core.fois.service import FOISService
    from src.core.history_context import canonical_history_store

    data = payload["data"]
    league_id = str(payload["league_id"])
    canonical_history_store.update_current(league_id, data)
    repository = FOISRepository(Path(payload["fois_database"]))
    service = FOISService(
        repository,
        history_loader=lambda selected: load_results_history(
            canonical_history_store, selected,
        ),
    )
    started = perf_counter()
    scores = service._generate_sync(data)
    duration_ms = round((perf_counter() - started) * 1000, 3)
    record(
        "fois_child_phase", phase="compute", status="completed",
        duration_ms=duration_ms, records=len(scores),
    )
    return {
        "status": "complete",
        "records": len(scores),
        "duration_ms": duration_ms,
        "peak_rss_bytes": psutil.Process(os.getpid()).memory_info().rss,
        "worker_pid": os.getpid(),
    }


def _read_published(repository: Any, league_id: str) -> tuple[tuple[Any, ...], dict[str, object]]:
    scores = tuple(repository.league(league_id, FOIS_MODEL_VERSION))
    health = repository.canonical_health(league_id, FOIS_MODEL_VERSION)
    return scores, health


def _prepare_working_database(source: Path, target: Path) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, target)


def _validate_and_publish(
    working_path: Path, repository: Any, league_id: str, expected: int,
) -> tuple[tuple[Any, ...], dict[str, object]]:
    from src.core.fois.repository import FOISRepository

    working = FOISRepository(working_path)
    working_scores = tuple(working.league(league_id, FOIS_MODEL_VERSION))
    if len(working_scores) != expected:
        raise RuntimeError("FOIS compute publication count mismatch.")
    os.replace(working_path, repository.path)
    return _read_published(repository, league_id)


async def generate_fois_isolated(
    data: dict[str, Any], repository: Any,
    *,
    timeout: float = FOIS_PROCESS_TIMEOUT_SECONDS,
) -> tuple[tuple[Any, ...], dict[str, object], dict[str, object]]:
    """Compute/persist FOIS in one spawned child, then reconcile in the parent."""
    league_id = str((data.get("league") or {}).get("league_id") or "configured-league")
    started = perf_counter()
    progress = progress_from_environment()
    record = progress.record if progress is not None else lambda *_args, **_kwargs: None
    record("fois_phase", phase="parent_input", status="started", league_identity="configured")
    repository.path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".dtos-fois-compute-", dir=repository.path.parent,
    ) as directory:
        temporary = Path(directory)
        working_database = temporary / "fois.sqlite3"
        await asyncio.to_thread(
            _prepare_working_database, repository.path, working_database,
        )
        compact_data = compact_fois_input(data)
        payload: dict[str, Any] = {
            "data": compact_data,
            "input_contract": "compact_fois_v1",
            "league_id": league_id,
            "fois_database": str(working_database),
            "intelligence_checkpoint_file": str(INTELLIGENCE_CHECKPOINT_FILE),
            "metadata_database_file": str(METADATA_DATABASE_FILE),
            "sleeper_season_cache_root": str(SLEEPER_SEASON_CACHE_ROOT),
        }
        input_bytes = await asyncio.to_thread(
            lambda: len(json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=str,
            ).encode("utf-8")),
        )
        record("fois_phase", phase="parent_input", status="completed", input_bytes=input_bytes, duration_ms=round((perf_counter() - started) * 1000, 3))
        try:
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(_executor(), _compute_fois_payload, payload),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise RuntimeError("FOIS compute process timed out.") from None
            except BrokenProcessPool as exc:
                raise RuntimeError("FOIS compute process failed.") from exc
            if result.get("status") != "complete" or int(result.get("records") or -1) < 0:
                raise RuntimeError("FOIS compute process returned an invalid result contract.")
        except asyncio.CancelledError:
            raise

        publication_started = perf_counter()
        record("fois_phase", phase="publication", status="started")
        scores, canonical = await asyncio.to_thread(
            _validate_and_publish, working_database, repository, league_id,
            int(result["records"]),
        )
        record("fois_phase", phase="publication", status="completed", records=len(scores), duration_ms=round((perf_counter() - publication_started) * 1000, 3))
        metrics = {
            "execution": "spawned_subprocess",
            "process_model": "persistent_spawn_pool",
            "input_contract": "compact_fois_v1",
            "worker_pid": result["worker_pid"],
            "input_bytes": input_bytes,
            "output_bytes": len(json.dumps(result, sort_keys=True).encode("utf-8")),
            "child_duration_ms": result.get("duration_ms"),
            "child_peak_rss_bytes": result.get("peak_rss_bytes"),
            "parent_duration_ms": round((perf_counter() - started) * 1000, 3),
            "exit_status": 0,
            "reaped": False,
        }
        return scores, canonical, metrics
