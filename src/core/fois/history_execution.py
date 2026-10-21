"""One owned full-history producer, including serialization and ASGI output.

No job queue, decoded cross-request cache or permanent response archive. An
anonymous OS temporary file holds only a fully verified encoded response. The
single lease covers child retirement, backpressured output and file cleanup.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from starlette.responses import JSONResponse, Response

from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot
from src.platform.request_diagnostics import span

PREPARATION_TIMEOUT_SECONDS = 60.0
OUTPUT_TIMEOUT_SECONDS = 60.0
WORKER_STOP_SECONDS = 2.0
MEMORY_RESERVE_BYTES = 256 * 1024**2
MEMORY_STOP_RESERVE_BYTES = 64 * 1024**2
CHUNK_BYTES = 64 * 1024


def _memory_available(reserve):
    snapshot = memory_snapshot()
    limit, used = snapshot['cgroup_limit_bytes'], snapshot['cgroup_current_bytes']
    return limit is None or used is None or limit - used >= reserve


async def _drain(task):
    """A repeated cancellation may not abandon an owned child or file read."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


async def _owned_read(executor, stream):
    # One reader belonging to the admitted response. Lifecycle waiters in the
    # application's default pool must not starve the operation they await.
    task = asyncio.ensure_future(asyncio.get_running_loop().run_in_executor(
        executor, stream.read, CHUNK_BYTES))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await _drain(task)
        raise


class HistoryRequests:
    def __init__(self):
        self.lock = threading.Lock()
        self.task = None
        self.stopping = False

    @property
    def active_count(self):
        with self.lock:
            return int(self.task is not None)

    def acquire(self):
        with self.lock:
            if self.stopping or self.task is not None or not _memory_available(MEMORY_RESERVE_BYTES):
                return False
            if not lifecycle_coordinator.try_reserve_history_response():
                return False
            self.task = asyncio.current_task()
            return True

    def release(self):
        with self.lock:
            self.task = None
            lifecycle_coordinator.release_history_response()

    def startup(self):
        with self.lock:
            if self.task is None:
                self.stopping = False

    async def shutdown(self):
        with self.lock:
            self.stopping = True
            task = self.task
        if task is not None:
            task.cancel()
            try:
                await _drain(task)
            except asyncio.CancelledError:
                pass


history_requests = HistoryRequests()


async def _stop(process):
    if process is None:
        return
    if process.stdin is not None:
        process.stdin.close()
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), WORKER_STOP_SECONDS)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
    else:
        await process.wait()


class HistoryResponse(Response):
    media_type = 'application/json'

    def __init__(self, *, database: Path, league_id: str, gm_id: str,
                 kind: str, metadata: dict, retained: bool):
        super().__init__(media_type=self.media_type)
        self.spec = {'database': str(database.resolve()), 'league_id': league_id,
                     'gm_id': gm_id, 'kind': kind, 'metadata': metadata, 'retained': retained}

    async def _run(self, scope, receive, send):
        if not history_requests.acquire():
            await JSONResponse({'detail': 'Full FOIS history is temporarily busy or unavailable. '
                'Please retry; ordinary league navigation remains available.',
                'history_status': 'unavailable'}, status_code=503,
                headers={'Retry-After': '5'})(scope, receive, send)
            return
        process = None
        spool = None
        spawning = None
        reader = None
        try:
            try:
                spool = tempfile.TemporaryFile(mode='w+b', prefix='dtos-fois-response-')
            except OSError:
                await JSONResponse({'detail': 'Full FOIS history is unavailable because temporary response storage '
                    'could not be opened. Please retry; no historical assessment has been revalidated.',
                    'history_status': 'unavailable'}, status_code=503,
                    headers={'Retry-After': '5'})(scope, receive, send)
                return
            spawning = asyncio.create_task(asyncio.create_subprocess_exec(
                sys.executable, '-m', 'src.core.fois.history_request_worker',
                cwd=str(Path(__file__).resolve().parents[3]),
                stdin=asyncio.subprocess.PIPE, stdout=spool, stderr=subprocess.DEVNULL))
            try:
                process = await asyncio.shield(spawning)
            except (OSError, RuntimeError):
                spawning = None
                await JSONResponse({'detail': 'Full FOIS history could not start within available resources. '
                    'Please retry; ordinary league navigation remains available.',
                    'history_status': 'unavailable'}, status_code=503,
                    headers={'Retry-After': '5'})(scope, receive, send)
                return
            try:
                process.stdin.write(json.dumps(self.spec, separators=(',', ':')).encode() + b'\n')
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                # Early child startup failure is classified by its exit below.
                pass
            waiter = asyncio.create_task(process.wait())
            try:
                async with asyncio.timeout(PREPARATION_TIMEOUT_SECONDS):
                    while process.returncode is None:
                        if not _memory_available(MEMORY_STOP_RESERVE_BYTES):
                            raise MemoryError('Historical response resource admission expired')
                        try:
                            await asyncio.wait_for(asyncio.shield(waiter), .25)
                        except asyncio.TimeoutError:
                            continue
            except (TimeoutError, MemoryError):
                await _stop(process)
                await JSONResponse({'detail': 'Full FOIS history could not finish within available resources. '
                    'Please retry; historical grades have not been revalidated.',
                    'history_status': 'unavailable'}, status_code=503,
                    headers={'Retry-After': '5'})(scope, receive, send)
                return
            if process.returncode:
                detail = ('No FOIS score exists for this GM tenure.' if process.returncode == 3 else
                    'FOIS history is unavailable because of an invalid retained delta. Historical grades have not been revalidated.'
                    if process.returncode == 4 else
                    'FOIS history is unavailable because retained evidence could not be prepared or verified. Historical grades have not been revalidated.')
                await JSONResponse({'detail': detail}, status_code=404 if process.returncode == 3 else 503)(scope, receive, send)
                return
            # Retire the child before output; no decoded result survives in the
            # application, and no unchecked partial spool is ever published.
            await _stop(process)
            size = spool.seek(0, 2)
            spool.seek(0)
            reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix='dtos-history-output')
            async with asyncio.timeout(OUTPUT_TIMEOUT_SECONDS):
                await send({'type': 'http.response.start', 'status': 200,
                            'headers': [(b'content-type', b'application/json'),
                                        (b'content-length', str(size).encode())]})
                while chunk := await _owned_read(reader, spool):
                    await send({'type': 'http.response.body', 'body': chunk, 'more_body': True})
                await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
        finally:
            # Shield the entire retirement/close sequence, not just terminate().
            async def cleanup():
                nonlocal process
                try:
                    if spawning is not None and process is None:
                        process = await _drain(spawning)
                    await _stop(process)
                finally:
                    if spool is not None:
                        spool.close()
                    if reader is not None:
                        reader.shutdown(wait=True, cancel_futures=True)
            cleanup_task = asyncio.create_task(cleanup())
            try:
                await _drain(cleanup_task)
            finally:
                history_requests.release()

    async def __call__(self, scope, receive, send):
        with span('fois_history_response', activate=True, memory=True):
            await self._serve(scope, receive, send)

    async def _serve(self, scope, receive, send):
        async def disconnected():
            while (await receive())['type'] != 'http.disconnect':
                pass
        operation = asyncio.create_task(self._run(scope, receive, send))
        disconnect = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait((operation, disconnect), return_when=asyncio.FIRST_COMPLETED)
            if operation in done:
                await operation
            else:
                operation.cancel()
                try:
                    await _drain(operation)
                except asyncio.CancelledError:
                    pass
        finally:
            operation.cancel()
            disconnect.cancel()
            for task in (operation, disconnect):
                try:
                    await _drain(task)
                except asyncio.CancelledError:
                    pass
