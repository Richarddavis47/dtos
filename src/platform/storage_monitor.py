"""Bounded, process-local operational samples; no source payloads or new store.

Samples reset on restart. Annual accounting uses explicit retained audit
baselines via storage_review, not extrapolation from these short intervals.
"""
from collections import OrderedDict
import logging
from pathlib import Path
import shutil
from threading import RLock

MIB = 1024 * 1024
_samples = OrderedDict()
_lock = RLock()
_logger = logging.getLogger('dtos.storage')
TABLES = {
    'projection': ('projection_snapshots', 'projection_source_history', 'projection_player_states'),
    'fois': ('fois_scores_v2', 'fois_snapshot_history', 'fois_semantic_states'),
}


def observe(db, kind):
    """Called inside existing publication transactions; never writes to SQLite."""
    path = Path(next(row[2] for row in db.execute('PRAGMA database_list') if row[1] == 'main'))
    rows = {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in TABLES[kind]}
    page_bytes = db.execute('PRAGMA page_count').fetchone()[0] * db.execute('PRAGMA page_size').fetchone()[0]
    free = shutil.disk_usage(path.parent).free
    sample = {'kind': kind, 'database_bytes': page_bytes, 'rows': rows, 'free_bytes': free}
    reasons = []
    if free < 128 * MIB:
        reasons.append('LOW_DISK_HEADROOM')
    with _lock:
        previous = _samples.get(str(path))
        if previous and page_bytes - previous['database_bytes'] > 50 * MIB:
            reasons.append('LARGE_PUBLICATION_GROWTH_REVIEW')
        # Count acceleration is a review signal, not permission to discard
        # canonical events. The actual delta is always included for inspection.
        sample['row_delta'] = {key: value - (previous or {}).get('rows', {}).get(key, value)
                               for key, value in rows.items()}
        if previous:
            for key, delta in sample['row_delta'].items():
                prior_delta = previous.get('row_delta', {}).get(key, 0)
                if delta > max(64, 4 * max(0, prior_delta)):
                    reasons.append('ROW_GROWTH_ACCELERATION_REVIEW')
                    break
        sample['reasons'] = reasons
        _samples[str(path)] = sample
        _samples.move_to_end(str(path))
        while len(_samples) > 128:
            _samples.popitem(last=False)
    if reasons and (not previous or reasons != previous.get('reasons')):
        _logger.warning('storage_review %s', sample)
    return sample


def health():
    """Sanitized samples: no paths, account IDs, source records or credentials."""
    with _lock:
        return {'scope': 'process_lifetime', 'stores': [dict(row) for row in _samples.values()]}
