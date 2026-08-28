"""Bounded spawned-process execution for canonical FOIS generation."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from config import (
    INTELLIGENCE_CHECKPOINT_FILE, METADATA_DATABASE_FILE,
    SLEEPER_SEASON_CACHE_ROOT,
)
from src.core.fois.models import FOIS_MODEL_VERSION
from src.platform.validation.progress import (
    PROGRESS_FILE_ENVIRONMENT, PROGRESS_RUN_ENVIRONMENT,
    progress_from_environment,
)

FOIS_PROCESS_TIMEOUT_SECONDS = 60.0


def _write_input(path: Path, payload: dict[str, Any]) -> int:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    path.write_bytes(encoded)
    return len(encoded)


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


def _child_environment(root: Path) -> dict[str, str]:
    environment = {
        name: os.environ[name]
        for name in ("PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP")
        if name in os.environ
    }
    environment.update({
        "PYTHONPATH": str(root),
        "PYTHONUNBUFFERED": "1",
        "DTOS_FOIS_ENABLED": "1",
    })
    for name in (PROGRESS_FILE_ENVIRONMENT, PROGRESS_RUN_ENVIRONMENT):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


async def generate_fois_isolated(
    data: dict[str, Any], repository: Any,
    *,
    process_factory: Callable[..., Any] = asyncio.create_subprocess_exec,
    timeout: float = FOIS_PROCESS_TIMEOUT_SECONDS,
) -> tuple[tuple[Any, ...], dict[str, object], dict[str, object]]:
    """Compute/persist FOIS in one spawned child, then reconcile in the parent."""
    root = Path(__file__).resolve().parents[3]
    league_id = str((data.get("league") or {}).get("league_id") or "configured-league")
    started = perf_counter()
    process = None
    progress = progress_from_environment()
    record = progress.record if progress is not None else lambda *_args, **_kwargs: None
    record("fois_phase", phase="parent_input", status="started", league_identity="configured")
    repository.path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".dtos-fois-compute-", dir=repository.path.parent,
    ) as directory:
        temporary = Path(directory)
        input_file = temporary / "input.json"
        output_file = temporary / "output.json"
        working_database = temporary / "fois.sqlite3"
        await asyncio.to_thread(
            _prepare_working_database, repository.path, working_database,
        )
        payload = {
            "data": data,
            "league_id": league_id,
            "fois_database": str(working_database),
            "intelligence_checkpoint_file": str(INTELLIGENCE_CHECKPOINT_FILE),
            "metadata_database_file": str(METADATA_DATABASE_FILE),
            "sleeper_season_cache_root": str(SLEEPER_SEASON_CACHE_ROOT),
        }
        input_bytes = await asyncio.to_thread(_write_input, input_file, payload)
        record("fois_phase", phase="parent_input", status="completed", input_bytes=input_bytes, duration_ms=round((perf_counter() - started) * 1000, 3))
        try:
            spawn_started = perf_counter()
            record("fois_phase", phase="child_spawn", status="started")
            process = await process_factory(
                sys.executable, "-m", "src.fois_compute_worker",
                "--input", str(input_file), "--output", str(output_file),
                cwd=str(root), env=_child_environment(root),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            record("fois_phase", phase="child_spawn", status="completed", child_pid=process.pid, duration_ms=round((perf_counter() - spawn_started) * 1000, 3))
            try:
                record("fois_phase", phase="child_execution", status="started", child_pid=process.pid)
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout,
                )
                record("fois_phase", phase="child_execution", status="completed", child_pid=process.pid, returncode=process.returncode)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError("FOIS compute process timed out.") from None
            if process.returncode != 0:
                detail = stderr.decode("utf-8", errors="replace")[-500:]
                raise RuntimeError(
                    "FOIS compute process failed"
                    + (f": {detail}" if detail else ".")
                )
            if stdout:
                raise RuntimeError("FOIS compute process returned unexpected stdout.")
            try:
                result = json.loads(output_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError("FOIS compute process returned malformed output.") from exc
            if result.get("status") != "complete" or int(result.get("records") or -1) < 0:
                raise RuntimeError("FOIS compute process returned an invalid result contract.")
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
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
            "worker_pid": process.pid,
            "input_bytes": input_bytes,
            "output_bytes": output_file.stat().st_size,
            "child_duration_ms": result.get("duration_ms"),
            "child_peak_rss_bytes": result.get("peak_rss_bytes"),
            "parent_duration_ms": round((perf_counter() - started) * 1000, 3),
            "exit_status": process.returncode,
            "reaped": True,
        }
        return scores, canonical, metrics
