"""Daily background collection of committed, aggregate storage counters.

No application initialization, schema changes or raw evidence persistence.
Per-league history is a conservative retained-payload estimate (including the
bounded FOIS operational tail), not an attribution of shared pages or indexes.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
from threading import Lock

from src.platform.durable_storage_monitor import COUNTERS, DurableStorageMonitor
from src.platform.storage_gate import connect

_lock = Lock()
_checked = {}
_status = {'status': 'not_collected'}


def collect(*, projection, fois, events, cache_paths, disk_root):
    totals = dict.fromkeys(COUNTERS, 0)
    leagues = {}

    def scope(league):
        return leagues.setdefault(str(league), {'current_bytes': 0, 'canonical_history_bytes': 0, 'event_count': 0})

    for kind, path in (('projection', projection), ('fois', fois), ('event', events)):
        path = Path(path)
        if not path.exists():
            # Absence is not reported as a healthy zero for a required store.
            raise ValueError('Required accounting store unavailable: ' + kind)
        with closing(connect(path, readonly=True)) as db:
            db.execute('BEGIN')
            totals[kind + '_bytes'] = db.execute('PRAGMA page_count').fetchone()[0] * db.execute('PRAGMA page_size').fetchone()[0]
            if kind == 'projection':
                from src.core.projection_intelligence.state_storage import decode
                totals['projection_rows'] = db.execute('SELECT count(*) FROM projection_snapshots').fetchone()[0]
                totals['projection_provenance_rows'] = db.execute('SELECT count(*) FROM projection_source_history').fetchone()[0]
                for league, payload in db.execute(
                    'SELECT s.league_id,s.payload FROM projection_snapshots s JOIN projection_publication_heads h ON h.snapshot_id=s.snapshot_id'
                ):
                    scope(league)['current_bytes'] += len(json.dumps(decode(db, payload), separators=(',', ':')).encode())
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'projection_checkpoint_roots' in tables:
                    for league, payload in db.execute(
                        'SELECT DISTINCT s.league_id,s.payload FROM projection_snapshots s JOIN projection_checkpoint_roots r ON r.snapshot_id=s.snapshot_id'
                    ):
                        scope(league)['canonical_history_bytes'] += len(json.dumps(decode(db, payload), separators=(',', ':')).encode())
            elif kind == 'fois':
                totals['fois_observations'] = db.execute('SELECT count(*) FROM fois_snapshot_history').fetchone()[0]
                for league, size in db.execute('SELECT league_id,sum(length(CAST(payload AS BLOB))) FROM fois_scores_v2 GROUP BY league_id'):
                    scope(league)['current_bytes'] += size
                for table in ('fois_snapshot_history', 'fois_semantic_states'):
                    for league, size in db.execute(f'SELECT league_id,sum(length(CAST(payload AS BLOB))) FROM {table} GROUP BY league_id'):
                        scope(league)['canonical_history_bytes'] += size
            else:
                totals['event_count'] = db.execute('SELECT count(*) FROM intelligence_checkpoints').fetchone()[0]
                for league, count, size in db.execute(
                    'SELECT league_id,count(*),sum(length(CAST(observations_json AS BLOB))) FROM intelligence_checkpoints WHERE league_id IS NOT NULL GROUP BY league_id'
                ):
                    scope(league)['event_count'] = count
                    # Payload estimate only. Physical event cost is measured in
                    # rehearsal; do not pretend these bytes include indexes.
                    scope(league)['canonical_history_bytes'] += size
    totals['cache_bytes'] = sum(path.stat().st_size for path in set(map(Path, cache_paths)) if path.is_file())
    disk = shutil.disk_usage(disk_root)
    totals['disk_used'], totals['disk_free'] = disk.used, disk.free
    return totals, leagues


def periodic_storage_accounting():
    """Called by existing resident-league maintenance, never on a page read."""
    global _status
    from config import (HISTORY_STORAGE_ROOT, PROJECTION_DATABASE_FILE,
                        INTELLIGENCE_CHECKPOINT_FILE, SLEEPER_SEASON_CACHE_ROOT,
                        CACHE_FILE, METADATA_DATABASE_FILE)
    from services.fois import _database_path
    from src.platform.cache_budget import json_family
    path = Path(HISTORY_STORAGE_ROOT) / '.storage-accounting.json'
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    with _lock:
        if _checked.get(str(path)) == day:
            return
        try:
            monitor = DurableStorageMonitor(path)
            if monitor.due(now=now):
                metadata = Path(METADATA_DATABASE_FILE)
                caches = [*json_family(CACHE_FILE), *Path(SLEEPER_SEASON_CACHE_ROOT).glob('*/*.json.gz'),
                          *metadata.parent.glob(f'.{metadata.stem}.asset-market-*.sqlite3')]
                totals, leagues = collect(projection=PROJECTION_DATABASE_FILE, fois=_database_path(),
                                          events=INTELLIGENCE_CHECKPOINT_FILE, cache_paths=caches,
                                          disk_root=path.parent)
                _status = monitor.record(totals, leagues, now=now)
            else:
                _status = monitor.review(monitor.read())
        except Exception as exc:
            # Do not turn successful intelligence publication into a failure.
            # Operational diagnostics explicitly expose collection failure.
            _status = {'status': 'collection_failed', 'error_type': type(exc).__name__,
                       'canonical_deletion_authorized': False}
            logging.getLogger('dtos.storage').warning('durable_storage_monitor %s', _status)
        _checked[str(path)] = day
        while len(_checked) > 32:
            _checked.pop(next(iter(_checked)))


def health():
    return dict(_status)
