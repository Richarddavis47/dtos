"""Bounded evidence readers. No application preparation or writable connections."""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.projection_reachability import InspectionLimit, analyze

MIB = 1024 * 1024
PROJECTION_TABLES = frozenset({
    'projection_snapshots', 'projection_player_states', 'projection_publication_heads',
    'projection_actuals', 'projection_checkpoint_roots', 'projection_source_roots',
    'projection_source_history', 'sleeper_projection_snapshots', 'projection_previous_heads',
    'projection_retention_policy', 'projection_source_expiry', 'projection_snapshot_quarantine',
})
FOIS_TABLES = frozenset({'fois_scores', 'fois_scores_v2', 'fois_gm_tenures',
                        'fois_takeover_snapshots', 'fois_snapshot_history', 'fois_evidence_links',
                        'fois_semantic_states', 'fois_retention_policy', 'fois_assessment_roots'})


@dataclass(frozen=True)
class InspectionStores:
    projection: Path
    fois: Path
    disk_root: Path
    known: dict[str, Path]
    cache: Path
    seasons: Path
    monitor: Path

    @classmethod
    def configured(cls):
        import config
        fois = config.fois_database_path()
        known = {'projection': config.PROJECTION_DATABASE_FILE, 'fois': fois,
                 'events': config.INTELLIGENCE_CHECKPOINT_FILE, 'history': config.HISTORY_DATABASE_FILE,
                 'metadata': config.METADATA_DATABASE_FILE, 'global_evidence': config.GLOBAL_EVIDENCE_FILE}
        return cls(config.PROJECTION_DATABASE_FILE, fois, config.PROJECTION_DATABASE_FILE.parent,
                   known, config.CACHE_FILE, config.SLEEPER_SEASON_CACHE_ROOT,
                   config.HISTORY_STORAGE_ROOT / '.storage-accounting.json')


@dataclass
class Budget:
    deadline: float
    max_decoded_bytes: int = 32 * MIB
    max_snapshots: int = 4096
    max_references: int = 250_000
    max_errors: int = 128
    rows: int = 0
    decoded_bytes: int = 0

    def check(self):
        if time.monotonic() >= self.deadline:
            raise InspectionLimit('Inspection time budget exceeded')

    def decoded(self, size):
        self.check()
        self.decoded_bytes += size
        if self.decoded_bytes > 512 * MIB:
            raise InspectionLimit('Inspection aggregate decoding budget exceeded')

    def row(self, value):
        self.check()
        self.rows += 1
        if self.rows > 5_000_000:
            raise InspectionLimit('Inspection row budget exceeded')
        return value


class _Cursor:
    def __init__(self, cursor, budget, maximum):
        self.cursor, self.budget, self.maximum = cursor, budget, maximum

    def __iter__(self):
        for index, row in enumerate(self.cursor):
            if index >= self.maximum:
                raise InspectionLimit('Inspection query row budget exceeded')
            yield self.validate(row)

    def validate(self, row):
        for column, value in zip(self.cursor.description, row, strict=True):
            if column[0] != 'payload' and isinstance(value, str) and len(value) > 128:
                raise InspectionLimit('Inspection metadata budget exceeded')
        return self.budget.row(row)

    def fetchone(self):
        row = self.cursor.fetchone()
        return self.validate(row) if row is not None else None


class _Reader:
    def __init__(self, db, budget):
        self.db, self.budget = db, budget

    def execute(self, sql, args=()):
        self.budget.check()
        maximum = 5_000_000 if sql == 'SELECT state_id,length(payload) FROM projection_player_states' else 100_000
        return _Cursor(self.db.execute(sql, args), self.budget, maximum)


def safe_path(path):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise InspectionLimit('Inspection store identity unavailable')
    return path


@contextmanager
def read_connection(path, allowed, budget):
    path = safe_path(path)
    # Participate in the existing maintenance fence without creating/updating it.
    lock_path = safe_path(path.with_name(path.name + '.storage-lock'))
    with lock_path.open('rb') as fence:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(fence.fileno(), msvcrt.LK_NBRLCK, 1)
        else:
            import fcntl
            fcntl.flock(fence.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        try:
            # Read-only SQLite can create WAL/SHM on WAL stores. Fail closed;
            # never use immutable=1 on live data (it ignores SQLite locking).
            with path.open('rb') as handle:
                header = handle.read(100)
            if (header[:16] != b'SQLite format 3\0' or header[18:20] != b'\x01\x01'
                    or any(path.with_name(path.name + suffix).exists()
                           for suffix in ('-wal', '-shm', '-journal'))):
                raise InspectionLimit('Inspection store read state unavailable')
            db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.1)
            try:
                db.execute('PRAGMA query_only=ON')
                db.execute('PRAGMA trusted_schema=OFF')
                db.execute('PRAGMA temp_store=MEMORY')
                db.execute('PRAGMA cache_size=-2048')
                db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, budget.max_decoded_bytes)
                db.set_progress_handler(lambda: int(time.monotonic() >= budget.deadline), 1000)

                def authorize(action, first, second, database, trigger):
                    if trigger is not None:
                        return sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_SELECT:
                        return sqlite3.SQLITE_OK
                    if action == sqlite3.SQLITE_READ and database in {'main', None} and first in allowed | {'sqlite_master'}:
                        return sqlite3.SQLITE_OK
                    if action == sqlite3.SQLITE_FUNCTION and second in {'count', 'length', 'sum', 'coalesce', 'min', 'max', 'julianday'}:
                        return sqlite3.SQLITE_OK
                    if action == sqlite3.SQLITE_PRAGMA and first in {'page_count', 'page_size', 'freelist_count', 'quick_check'}:
                        return sqlite3.SQLITE_OK
                    if action == sqlite3.SQLITE_TRANSACTION and first in {'BEGIN', 'ROLLBACK'}:
                        return sqlite3.SQLITE_OK
                    return sqlite3.SQLITE_DENY

                db.set_authorizer(authorize)
                db.execute('BEGIN')
                yield _Reader(db, budget)
            finally:
                db.close()  # Rolls back/ends the bounded read transaction.
        finally:
            if os.name == 'nt':
                fence.seek(0)
                msvcrt.locking(fence.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fence.fileno(), fcntl.LOCK_UN)


def file_bytes(path):
    path = safe_path(path)
    return path.stat().st_size if path.is_file() else None


def storage(stores, budget):
    budget.check()
    root = safe_path(stores.disk_root)
    disk = shutil.disk_usage(root)
    inodes = None
    if hasattr(os, 'statvfs'):
        state = os.statvfs(root)
        inodes = {'total': state.f_files, 'free': state.f_ffree, 'available': state.f_favail}
    return {'capacity_bytes': disk.total, 'used_bytes': disk.used, 'free_bytes': disk.free,
            'inodes': inodes, 'stores': {key: {'file_bytes': file_bytes(path)} for key, path in stores.known.items()}}


def policy(db, tables, kind):
    name = kind + '_retention_policy'
    version = kind + '-retention-v1'
    admitted = name in tables and bool(db.execute(f'SELECT 1 FROM {name} WHERE version=? LIMIT 1', (version,)).fetchone())
    return {'policy': version if admitted else 'not_admitted', 'operational_window': 8 if admitted else None,
            'legacy_evidence_protected': True, 'canonical_deletion_authorized': False}


def tables_in(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 64")}


def fois_storage(stores, budget):
    with read_connection(stores.fois, FOIS_TABLES, budget) as db:
        tables = tables_in(db)
        required = {'fois_scores_v2', 'fois_snapshot_history', 'fois_semantic_states'}
        if not required <= tables or tables - FOIS_TABLES - {'sqlite_sequence'}:
            raise InspectionLimit('Unsupported FOIS store')
        rows = {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                for table in sorted(FOIS_TABLES & tables)}
        integrity = db.execute('PRAGMA quick_check(1)').fetchone()[0] == 'ok'
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
        return {'file_bytes': file_bytes(stores.fois),
                'physical_bytes': db.execute('PRAGMA page_count').fetchone()[0] * page_size,
                'freelist_bytes': db.execute('PRAGMA freelist_count').fetchone()[0] * page_size,
                'rows': rows, 'read_status': 'ok', 'integrity': {'quick_check_ok': integrity,
                'semantic_payload_validation': 'not_performed'}, 'retention': policy(db, tables, 'fois')}


def projection(stores, budget, *, inventory=None):
    with read_connection(stores.projection, PROJECTION_TABLES, budget) as db:
        return analyze(db, budget=budget, inventory=inventory)


def cache_footprint(stores, budget):
    total = entries = scanned = 0

    def measure(directory, predicate):
        nonlocal total, entries, scanned
        directory = safe_path(directory)
        if not directory.exists():
            return
        with os.scandir(directory) as children:
            for child in children:
                budget.check()
                scanned += 1
                if scanned > 4096:
                    raise InspectionLimit('Cache inventory budget exceeded')
                if child.is_file(follow_symlinks=False) and predicate(child.name):
                    entries += 1
                    total += child.stat(follow_symlinks=False).st_size

    base = stores.cache
    measure(base.parent, lambda name: name == base.name or name.startswith(base.stem + '.') and name.endswith(base.suffix))
    seasons = safe_path(stores.seasons)
    if seasons.exists():
        with os.scandir(seasons) as children:
            for child in children:
                budget.check()
                scanned += 1
                if scanned > 4096:
                    raise InspectionLimit('Cache inventory budget exceeded')
                if child.is_dir(follow_symlinks=False) and child.name.isdigit():
                    measure(Path(child.path), lambda name: name.endswith('.json.gz'))
    metadata = stores.known.get('metadata')
    if metadata is not None:
        measure(metadata.parent, lambda name: name.startswith('.' + metadata.stem + '.asset-market-') and name.endswith('.sqlite3'))
    return {'file_bytes': total, 'entries': entries}


def retention(stores, budget):
    from src.platform.cache_budget import JSON_BUDGET, MARKET_BUDGET, SEASON_BUDGET
    from src.platform.durable_storage_monitor import (
        COUNTERS,
        MAX_LEAGUES,
        MAX_PERIODS,
        MAX_YEARS,
        DurableStorageMonitor,
    )
    from src.platform.storage_monitor import health
    policies = {}
    for kind, path, allowed in (('projection', stores.projection, PROJECTION_TABLES), ('fois', stores.fois, FOIS_TABLES)):
        with read_connection(path, allowed, budget) as db:
            policies[kind] = policy(db, tables_in(db), kind)
    monitor_path = safe_path(stores.monitor)
    monitor = DurableStorageMonitor(monitor_path)
    payload = monitor.read()  # Existing bounded reader; never record()/collect().
    if len(payload['periods']) > MAX_PERIODS or len(payload['annual_baselines']) > MAX_YEARS:
        raise InspectionLimit('Monitoring period budget exceeded')
    for period in (*payload['periods'].values(), *payload['annual_baselines'].values()):
        budget.check()
        if len(period['sample']['leagues']) > MAX_LEAGUES:
            raise InspectionLimit('Monitoring scope budget exceeded')
    review = monitor.review(payload)
    growth = review.get('changes_since_baseline', {})
    if any(type(value) is not int for value in growth.values()):
        raise InspectionLimit('Invalid monitoring counters')
    latest = payload['periods'].get(max(payload['periods'], default=''), {}).get('sample', {}).get('totals', {})
    samples = health()['stores'][:128]
    # Export only counters; never paths, league/account identities or raw errors.
    return {'policies': policies, 'cache_footprint': cache_footprint(stores, budget),
            'cache_budgets': {k: asdict(v) for k, v in (('json', JSON_BUDGET), ('season', SEASON_BUDGET), ('market', MARKET_BUDGET))},
            'monitoring': {'status': review['status'] if review['status'] in {'uninitialized', 'review_required', 'within_review_budgets'} else 'unavailable',
                           'counters': {k: v for k, v in latest.items() if k in COUNTERS and type(v) is int},
                           'growth_since_baseline': {k: v for k, v in growth.items() if k in COUNTERS},
                           'periods': len(payload['periods']), 'annual_baselines': len(payload['annual_baselines']),
                           'process_samples': [{'kind': s['kind'], 'database_bytes': s['database_bytes'],
                                                'free_bytes': s['free_bytes']} for s in samples]}}


def identity():
    from app_metadata import BUILD_NUMBER, VERSION
    from src.platform.observability import runtime_metrics
    # Only commit identity is selected; never return an environment dictionary.
    commit = os.getenv('DTOS_GIT_COMMIT') or os.getenv('RENDER_GIT_COMMIT') or ''
    commit = commit.split(' ', 1)[0]
    return {'application': 'DTOS', 'version': VERSION, 'build': BUILD_NUMBER,
            'commit': commit if re.fullmatch(r'[0-9a-fA-F]{7,40}', commit) else None,
            'ready': runtime_metrics.ready, 'inspection_schema': 'dtos-operations-v1'}
