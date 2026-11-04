"""One bounded, lazy sampler while existing cold/FOIS work is active.

No payloads, command lines, environment, paths, account IDs or new files. Samples
are best-effort hosted logs, not atomic snapshots or a durable history service.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import multiprocessing
import threading
from time import perf_counter
import weakref

import psutil

from src.platform.lifecycle import memory_snapshot
from src.platform.request_diagnostics import utcnow

PROCESS_LIMIT = 16
ACTIVITY_LIMIT = 8
PENDING_LIMIT = 16
SAMPLE_INTERVAL_SECONDS = 2.0
PER_ACTIVITY_SAMPLE_LIMIT = 60


def capture_memory(*, full: bool, fois_pids: set[int]) -> dict:
    started = perf_counter()
    result = memory_snapshot()
    result.update(anonymous_bytes=None, file_bytes=None, kernel_bytes=None,
                  shmem_bytes=None, cgroup_lifetime_peak_bytes=None)
    try:
        fields = dict(row.split() for row in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        for field, key in (('anonymous_bytes', 'anon'), ('file_bytes', 'file'),
                           ('kernel_bytes', 'kernel'), ('shmem_bytes', 'shmem')):
            result[field] = int(fields[key]) if key in fields else None
        result['cgroup_lifetime_peak_bytes'] = int(Path('/sys/fs/cgroup/memory.peak').read_text())
    except (OSError, ValueError):
        pass
    parent = psutil.Process()
    result['observer_pid'] = parent.pid
    result['observer_kind'] = 'main_process' if multiprocessing.parent_process() is None else 'spawned_worker'
    live, zombies = [parent], 0
    for child in parent.children(recursive=True):
        try:
            if child.status() == psutil.STATUS_ZOMBIE:
                zombies += 1
            else:
                live.append(child)
        except (psutil.Error, OSError):
            continue
    result.update(active_process_count=len(live), zombie_count=zombies,
                  process_samples_truncated=len(live) > PROCESS_LIMIT,
                  process_samples_are_sequential=True)
    processes = []
    for process in live[:PROCESS_LIMIT]:
        try:
            begin = perf_counter()
            try:
                info = process.memory_full_info() if full else process.memory_info()
            except psutil.AccessDenied:
                info = process.memory_info()
            processes.append({
                'pid': process.pid, 'role': (('application' if result['observer_kind'] == 'main_process' else 'worker_observer') if process.pid == parent.pid
                    else 'fois_worker' if process.pid in fois_pids else 'child'),
                'rss_bytes': info.rss, 'pss_bytes': getattr(info, 'pss', None),
                'uss_bytes': getattr(info, 'uss', None),
                'sample_offset_ms': round((begin - started) * 1000, 3),
                'sample_duration_ms': round((perf_counter() - begin) * 1000, 3),
            })
        except (psutil.Error, OSError):
            continue
    result['processes'] = processes
    result['capture_duration_ms'] = round((perf_counter() - started) * 1000, 3)
    result['pss_requested'] = full
    return result


class MemoryAttribution:
    def __init__(self):
        self.condition = threading.Condition()
        self.active: dict[int, dict] = {}
        self.pending: deque[dict] = deque(maxlen=PENDING_LIMIT)
        self.sequence = 0
        self.thread: threading.Thread | None = None
        self.runtime_manager = None
        self.fois_pids: set[int] = set()
        self.dropped = 0

    def register_runtime_manager(self, manager) -> None:
        # Diagnostics must not become another owner of an evicted runtime.
        self.runtime_manager = weakref.ref(manager)

    def register_fois_worker(self, pid: int) -> None:
        if isinstance(pid, int) and pid > 0:
            with self.condition:
                if len(self.fois_pids) >= PROCESS_LIMIT:
                    self.fois_pids.clear()
                self.fois_pids.add(pid)

    def unregister_fois_workers(self, pids) -> None:
        with self.condition:
            self.fois_pids.difference_update(pid for pid in pids if isinstance(pid, int))

    def begin(self, trace, name: str, span_id: int) -> int | None:
        with self.condition:
            if len(self.active) >= ACTIVITY_LIMIT:
                self.dropped += 1
                return None
            self.sequence += 1
            identity = self.sequence
            row = {'trace': trace, 'name': name, 'span_id': span_id, 'samples': 0}
            self.active[identity] = row
            self._enqueue(row, 'started')
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name='dtos-bounded-memory-sampler', daemon=True)
                try:
                    self.thread.start()
                except (RuntimeError, OSError):
                    self.thread = None
                    self.active.pop(identity, None)
                    self.pending.clear()
                    self.dropped += 1
                    return None
            self.condition.notify_all()
            return identity

    def _enqueue(self, row: dict, boundary: str):
        if len(self.pending) == PENDING_LIMIT:
            self.dropped += 1
        self.pending.append({**row, 'boundary': boundary, 'requested_at': utcnow()})

    def end(self, identity: int) -> None:
        with self.condition:
            row = self.active.pop(identity, None)
            if row is not None:
                self._enqueue(row, 'finished')
            self.condition.notify_all()

    def _run(self) -> None:
        last = 0.0
        sample = 0
        while True:
            with self.condition:
                if not self.pending and not self.active:
                    self.thread = None
                    return
                if not self.pending:
                    self.condition.wait(timeout=SAMPLE_INTERVAL_SECONDS)
                pending = list(self.pending)
                self.pending.clear()
                eligible = [row for row in self.active.values() if row['samples'] < PER_ACTIVITY_SAMPLE_LIMIT]
                if not pending and (not eligible or perf_counter() - last < SAMPLE_INTERVAL_SECONDS):
                    continue
                if not pending and eligible:
                    pending = [{**eligible[0], 'boundary': 'sampling', 'requested_at': utcnow()}]
                for row in eligible:
                    row['samples'] += 1
                activity = [{'request_id': row['trace'].request_id, 'name': row['name'],
                             'span_id': row['span_id']} for row in self.active.values()]
                pids = set(self.fois_pids)
            if not pending:
                continue
            sample += 1
            last = perf_counter()
            representative = pending[0]
            try:
                # Full PSS only at boundaries or every fifth periodic sample.
                memory = capture_memory(full=any(x['boundary'] != 'sampling' for x in pending) or sample % 5 == 0,
                                        fois_pids=pids)
                manager = self.runtime_manager() if self.runtime_manager is not None else None
                if manager is not None:
                    memory['runtime_residency'] = manager.diagnostic_residency()
                memory['sample_total_duration_ms'] = round((perf_counter() - last) * 1000, 3)
            except (psutil.Error, OSError, RuntimeError, ValueError):
                memory = {'state': 'unavailable'}
            representative['trace'].emit({
                'name': 'memory_sample', 'boundary': 'captured', 'timestamp': utcnow(),
                'sample_id': sample, 'span_id': representative['span_id'],
                'requested_boundaries': [{'name': x['name'], 'boundary': x['boundary'],
                    'span_id': x['span_id'], 'request_id': x['trace'].request_id,
                    'requested_at': x['requested_at']} for x in pending],
                'active_activities': activity, 'dropped_activity_or_boundary_count': self.dropped,
                'memory': memory,
            })


memory_attribution = MemoryAttribution()
