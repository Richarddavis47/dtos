"""One bounded numeric diagnostic per sync; no source facts or saved history."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from time import perf_counter

import psutil

from src.platform.lifecycle import memory_snapshot

logger = logging.getLogger('dtos.sync_profile')
PHASES = frozenset({
    'league_lock_wait', 'lifecycle_wait', 'source_acquisition', 'roster_identity',
    'market_normalization', 'initial_history', 'global_ranks', 'relevance',
    'provider_network', 'projections', 'team_strength', 'valuation',
    'calibration', 'final_history', 'checkpoints', 'cache_publication',
})
PROCESS_SAMPLE_LIMIT = 16


def _memory() -> dict:
    result = memory_snapshot()
    result.update(anonymous_bytes=None, file_bytes=None, cgroup_lifetime_peak_bytes=None)
    try:
        fields = dict(row.split() for row in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        result.update(anonymous_bytes=int(fields['anon']), file_bytes=int(fields['file']))
        result['cgroup_lifetime_peak_bytes'] = int(Path('/sys/fs/cgroup/memory.peak').read_text())
    except (OSError, ValueError, KeyError):
        pass
    return result


class SyncDiagnostics:
    """Stage clocks and point-in-time process/cgroup samples, not peak claims."""

    def __init__(self, league_id: str) -> None:
        self.league_scope = hashlib.sha256(str(league_id).encode()).hexdigest()[:16]
        self.started = self.checkpoint = perf_counter()
        self.phases: dict[str, float] = {}
        try:
            self.before = _memory()
        except (psutil.Error, OSError):
            self.before = {'state': 'unavailable'}

    def mark(self, name: str) -> None:
        if name not in PHASES:
            raise ValueError('Unsupported synchronization diagnostic phase')
        now = perf_counter()
        self.phases[name] = round((now - self.checkpoint) * 1000, 3)
        self.checkpoint = now
        from src.platform.request_diagnostics import sync_checkpoint
        sync_checkpoint(name, self.phases[name], self.league_scope)

    def finish(self, *, failed: bool) -> dict:
        """Diagnostics must not turn a valid publication into a source failure."""
        report = {
            'schema': 'sync-profile-v1', 'league_scope': self.league_scope,
            'status': 'failed' if failed else 'complete',
            'duration_ms': round((perf_counter() - self.started) * 1000, 3),
            'phase_ms': dict(self.phases), 'memory_before': self.before,
        }
        try:
            report['memory_after'] = _memory()
            parent = psutil.Process()
            processes = []
            candidates = [parent, *parent.children(recursive=True)]
            report['process_samples_truncated'] = len(candidates) > PROCESS_SAMPLE_LIMIT
            for process in candidates[:PROCESS_SAMPLE_LIMIT]:
                try:
                    info = process.memory_full_info()
                    processes.append({'pid': process.pid, 'parent': process.pid == parent.pid,
                                      'rss': info.rss, 'pss': getattr(info, 'pss', None),
                                      'uss': getattr(info, 'uss', None)})
                except (psutil.Error, OSError):
                    continue
            report['process_samples'] = processes
        except (psutil.Error, OSError):
            report['memory_state'] = 'unavailable'
        logger.info('sleeper_sync_profile %s', json.dumps(report, separators=(',', ':')))
        return report
