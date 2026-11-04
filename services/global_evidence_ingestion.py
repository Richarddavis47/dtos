"""Single-flight isolated global ingestion; never called by page handlers."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

from src.core.asset_market.read_model import memory_admission
from src.core.data_platform.ingestion_lock import ingestion_lock
from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot


_FLIGHT = threading.Lock()
WORKER_ESTIMATE = 256 * 1048576
WORKER_TIMEOUT = 300


def run_ingestion(season: int, database: Path, *, cancelled: threading.Event | None = None) -> dict:
    """Serialize background and CLI writers across process boundaries."""
    if cancelled is not None and cancelled.is_set():
        return {'status': 'cancelled'}
    state = lifecycle_coordinator.snapshot()
    if not lifecycle_coordinator.startup_complete() or state['heavy_work']['market_critical']:
        return {'status': 'deferred', 'reason': 'canonical_startup_or_market_pending'}
    database = database.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    with ingestion_lock(database) as acquired:
        if not acquired:
            return {'status': 'deferred', 'reason': 'global_ingestion_in_flight'}
        return _run_ingestion(season, database, cancelled=cancelled)


def _run_ingestion(season: int, database: Path, *, cancelled: threading.Event | None = None) -> dict:
    """Run in a coordinator thread, with bounded worker life and parent cleanup."""
    if not _FLIGHT.acquire(blocking=False):
        return {"status": "deferred", "reason": "global_ingestion_in_flight"}
    try:
        if cancelled is not None and cancelled.is_set():
            return {'status': 'cancelled'}
        state = lifecycle_coordinator.snapshot()
        if not lifecycle_coordinator.startup_complete() or state['heavy_work']['market_critical']:
            return {"status": "deferred", "reason": "canonical_startup_or_market_pending"}
        with lifecycle_coordinator.phase('global_evidence_ingestion'):
            admission = memory_admission(memory_snapshot(), estimate=WORKER_ESTIMATE)
            if not admission['admitted']:
                return {"status": "deferred", "reason": "memory_admission", "admission": admission}
            database = database.resolve()
            database.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='global-job-', dir=database.parent) as temporary:
                request = json.dumps({'protocol': 1, 'season': season, 'database': str(database),
                                      'temporary_directory': temporary}).encode()
                # Public-source worker has no use for production credentials.
                environment = {key: value for key, value in os.environ.items()
                    if key.upper() in {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'}}
                environment['PYTHONUTF8'] = '1'
                process = subprocess.Popen([sys.executable, '-m', 'src.global_evidence_worker'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=Path(__file__).resolve().parents[1], env=environment,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                started = time.monotonic()
                first = True
                peak_rss = 0
                try:
                    while True:
                        if cancelled is not None and cancelled.is_set():
                            return {'status': 'cancelled'}
                        try:
                            output, _ = process.communicate(input=request if first else None, timeout=1)
                            break
                        except subprocess.TimeoutExpired:
                            first = False
                            try:
                                peak_rss = max(peak_rss, psutil.Process(process.pid).memory_info().rss)
                            except psutil.NoSuchProcess:
                                pass
                            if time.monotonic() - started > WORKER_TIMEOUT:
                                raise TimeoutError('Global ingestion worker deadline exceeded.')
                            if not memory_admission(memory_snapshot(), estimate=0)['admitted']:
                                raise MemoryError('Global ingestion worker exceeded memory admission.')
                    if len(output) > 16384:
                        raise ValueError('Global ingestion worker output exceeded contract.')
                    result = json.loads(output)
                    if result.get('protocol') != 1 or result.get('status') not in {'complete', 'partial'} or process.returncode:
                        return {'status': 'failed', 'reason': 'source_worker_failed'}
                    if result.get('season') != season:
                        raise ValueError('Global ingestion worker season mismatch.')
                    result['observed_peak_worker_rss'] = max(peak_rss, result.get('final_worker_rss', 0))
                    result['worker_cleanup'] = True
                    return result
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()
    finally:
        _FLIGHT.release()


async def ingest_in_background(season: int, database: Path) -> dict:
    """Cancellation waits for bounded teardown; it cannot orphan a write worker."""
    cancelled = threading.Event()
    task = asyncio.create_task(asyncio.to_thread(run_ingestion, season, database, cancelled=cancelled))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        cancelled.set()
        await asyncio.gather(task, return_exceptions=True)
        raise
