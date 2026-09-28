"""Bounded aggregate accounting, not a source/evidence history store.

One daily collection at most; 24 monthly last samples and three annual start
baselines. Per-league counters are logical-byte estimates, never physical
database allocation claims. The first sample is explicitly a partial-year
baseline: no annualization of a short interval. Failed admission preserves the
previous monitor file and cannot authorize deletion of canonical evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from src.platform.storage_gate import database_gate

VERSION = 'storage-accounting-v1'
MAX_BYTES = 1024 * 1024
MAX_PERIODS = 24
MAX_YEARS = 3
MAX_LEAGUES = 512
MIB = 1024 * 1024
COUNTERS = frozenset({
    'projection_bytes', 'projection_rows', 'projection_provenance_rows',
    'fois_bytes', 'fois_observations', 'cache_bytes', 'event_bytes',
    'event_count', 'disk_used', 'disk_free',
})
LEAGUE_COUNTERS = frozenset({'current_bytes', 'canonical_history_bytes', 'event_count'})


class MonitoringAdmissionError(ValueError):
    """Review required; previous bounded accounting remains intact."""


def _counters(value, allowed):
    if set(value) != allowed:
        raise MonitoringAdmissionError('Monitoring counter contract mismatch')
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise MonitoringAdmissionError('Monitoring counters must be nonnegative integers')
    return dict(value)


class DurableStorageMonitor:
    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self):
        if not self.path.exists():
            return {'version': VERSION, 'periods': {}, 'annual_baselines': {}}
        if self.path.is_symlink() or self.path.stat().st_size > MAX_BYTES:
            raise MonitoringAdmissionError('Monitoring file budget or identity violation')
        payload = json.loads(self.path.read_text(encoding='utf-8'))
        if payload.get('version') != VERSION:
            raise MonitoringAdmissionError('Unknown monitoring methodology')
        return payload

    def due(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        self._time(now)
        payload = self.read()
        return payload.get('last_collection_day', '') < now.date().isoformat()

    @staticmethod
    def _time(now):
        if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
            raise MonitoringAdmissionError('Monitoring requires UTC time')

    def record(self, totals, leagues, *, now=None):
        now = now or datetime.now(timezone.utc)
        self._time(now)
        totals = _counters(totals, COUNTERS)
        if len(leagues) > MAX_LEAGUES:
            raise MonitoringAdmissionError('Monitoring league budget exceeded')
        scoped = {hashlib.sha256(str(key).encode()).hexdigest():
                  _counters(value, LEAGUE_COUNTERS) for key, value in leagues.items()}
        sample = {'totals': totals, 'leagues': scoped}
        day, month, year = now.date().isoformat(), now.strftime('%Y-%m'), str(now.year)
        with database_gate(self.path, exclusive=True):
            payload = self.read()
            if payload.get('last_collection_day', '') >= day:
                return self.review(payload)
            previous = payload['periods'].get(max(payload['periods'], default=''), {}).get('sample')
            # Same-period identical replay does not even rewrite a timestamp.
            if previous == sample and month in payload['periods']:
                return self.review(payload)
            payload['annual_baselines'].setdefault(year, {'observed_on': day, 'sample': sample})
            payload['periods'][month] = {'observed_on': day, 'sample': sample}
            payload['periods'] = dict(sorted(payload['periods'].items())[-MAX_PERIODS:])
            payload['annual_baselines'] = dict(sorted(payload['annual_baselines'].items())[-MAX_YEARS:])
            payload['last_collection_day'] = day
            raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
            if len(raw) > MAX_BYTES:
                raise MonitoringAdmissionError('Monitoring byte budget exceeded')
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return self.review(payload)

    @staticmethod
    def review(payload):
        periods = payload['periods']
        if not periods:
            return {'status': 'uninitialized', 'reasons': [], 'canonical_deletion_authorized': False}
        latest = periods[max(periods)]
        sample = latest['sample']
        year = latest['observed_on'][:4]
        baseline = payload['annual_baselines'][year]
        start = baseline['sample']
        reasons = []
        if sample['totals']['disk_free'] < 128 * MIB:
            reasons.append('LOW_DISK_HEADROOM')
        if sample['totals']['cache_bytes'] > (256 + 256 + 64) * MIB:
            reasons.append('CACHE_BUDGET_REVIEW')
        changes = {key: value - start['totals'][key] for key, value in sample['totals'].items()}
        for field, reason in (
            ('projection_provenance_rows', 'PROJECTION_PROVENANCE_GROWTH_REVIEW'),
            ('fois_observations', 'FOIS_HISTORY_GROWTH_REVIEW'),
            ('event_count', 'SPARSE_EVENT_GROWTH_REVIEW'),
        ):
            # Conservative review signal, not an activity/quality judgment.
            if changes[field] > max(1000, start['totals'][field]):
                reasons.append(reason)
        growth = []
        for league, counters in sample['leagues'].items():
            old = start['leagues'].get(league)
            delta = None if old is None else counters['canonical_history_bytes'] - old['canonical_history_bytes']
            growth.append({'scope': league, 'current_estimated_bytes': counters['current_bytes'],
                           'history_growth_since_baseline_bytes': delta})
            if delta is not None and delta > 50 * MIB:
                reasons.append('PER_LEAGUE_HISTORY_GROWTH_REVIEW')
        return {'status': 'review_required' if reasons else 'within_review_budgets',
                'reasons': sorted(set(reasons)), 'baseline_observed_on': baseline['observed_on'],
                'last_observed_on': latest['observed_on'], 'annualized': False,
                'changes_since_baseline': changes, 'leagues': growth,
                'retention': {'months': MAX_PERIODS, 'annual_baselines': MAX_YEARS,
                              'maximum_bytes': MAX_BYTES, 'maximum_leagues': MAX_LEAGUES},
                'canonical_deletion_authorized': False}
