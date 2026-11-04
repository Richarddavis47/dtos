"""One owned full-history producer, including serialization and ASGI output.

No job queue, decoded cross-request cache or permanent response archive. An
anonymous OS temporary file holds only a fully verified encoded response. The
single lease covers child retirement, backpressured output and file cleanup.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
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
PUBLICATION_ENVELOPE_BYTES = 16 * 1024


class HistoryPublication:
    """Pin admission identity; qualify that evidence at the ASGI header boundary.

    Runtime source publishers and FOIS refresh use the same per-runtime lock.
    No reconstruction, bulk serialization or bulk response transfer holds it.
    """
    def __init__(self, context, league_id):
        self.context = context
        self.league_id = league_id
        self.runtime = context.runtime if context is not None else None
        if self.runtime is not None:
            self.generations = dict(self.runtime.source_generations)
            self.data = self.runtime.state.get('data')
            self.revision = self.runtime.fois_publication_revision
            self.ready = context.fois_state == 'ready'

    @asynccontextmanager
    async def guard(self):
        if self.runtime is None:
            yield
        else:
            async with self.runtime.fois_publication_lock:
                yield

    def qualification(self, intrinsic):
        if self.runtime is None:
            return intrinsic
        runtime = self.runtime
        current = runtime.canonical_context
        if (runtime.league_id != self.league_id or current is None
                or current.league_id != self.league_id
                or str(runtime.status) in {'evicting', 'closed'}
                or not runtime.state.get('data')):
            return None
        unchanged = (current is self.context and self.ready and current.fois_state == 'ready'
            and runtime.source_generations == self.generations
            and runtime.state.get('data') is self.data
            and runtime.fois_publication_revision == self.revision)
        return intrinsic if unchanged else 'retained_not_revalidated'


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


async def _publication_envelope(executor, stream, spec):
    task = asyncio.ensure_future(asyncio.get_running_loop().run_in_executor(
        executor, stream.readline, PUBLICATION_ENVELOPE_BYTES + 1))
    try:
        value = await asyncio.shield(task)
    except asyncio.CancelledError:
        await _drain(task)
        raise
    if len(value) > PUBLICATION_ENVELOPE_BYTES or not value.endswith(b'\n'):
        raise ValueError('Invalid historical publication envelope')
    envelope = json.loads(value)
    if (not isinstance(envelope, dict) or envelope.get('league_id') != spec['league_id']
            or envelope.get('gm_id') != spec['gm_id']
            or not isinstance(envelope.get('metadata'), dict)
            or 'evidence_state' in envelope['metadata']
            or not isinstance(envelope.get('evidence_state'), str)):
        raise ValueError('Invalid historical publication identity')
    return envelope


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
                 kind: str, metadata: dict, retained: bool, publication=None):
        super().__init__(media_type=self.media_type)
        self.spec = {'database': str(database.resolve()), 'league_id': league_id,
                     'gm_id': gm_id, 'kind': kind, 'metadata': metadata, 'retained': retained}
        self.publication = publication or HistoryPublication(None, league_id)

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
                try:
                    envelope = await _publication_envelope(reader, spool, self.spec)
                except (ValueError, UnicodeError, OSError):
                    envelope = None
                async with self.publication.guard():
                    qualification = (self.publication.qualification(envelope['evidence_state'])
                                     if envelope is not None else None)
                    if qualification is not None:
                        prefix = json.dumps({**envelope['metadata'], 'evidence_state': qualification},
                            ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()[:-1]
                        size = size - spool.tell() + len(prefix)
                        # Refresh cannot change qualification between this
                        # final check and successful header commitment.
                        await send({'type': 'http.response.start', 'status': 200,
                                    'headers': [(b'content-type', b'application/json'),
                                                (b'content-length', str(size).encode())]})
                        # Also hand off the bounded prefix: ASGI servers may
                        # defer committing headers until the first body event.
                        await send({'type': 'http.response.body', 'body': prefix, 'more_body': True})
                if qualification is None:
                    await JSONResponse({'detail': 'Full FOIS history could not be qualified for the current league context. '
                        'Please retry; historical grades have not been revalidated.',
                        'history_status': 'unavailable'}, status_code=503,
                        headers={'Retry-After': '5'})(scope, receive, send)
                    return
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
