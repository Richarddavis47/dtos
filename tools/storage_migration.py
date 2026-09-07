"""Bounded, lossless FOIS/projection compaction; explicit operator invocation.

Run only on a deployment whose connections use storage_gate. No startup or
request handler invokes this tool. A failed/interrupted build leaves the source
untouched; a complete replacement is published only after logical equivalence.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from src.core.fois import state_storage as fois
from src.core.projection_intelligence import state_storage as projection
from src.platform.storage_gate import database_gate

KINDS = {
    'fois': (fois, 'fois_snapshot_history', {
        'fois_scores', 'fois_scores_v2', 'fois_gm_tenures', 'fois_takeover_snapshots',
        'fois_snapshot_history', 'fois_evidence_links', 'fois_semantic_states',
    }, 'fois_semantic_states'),
    'projection': (projection, 'projection_snapshots', {
        'projection_snapshots', 'projection_actuals', 'sleeper_projection_snapshots',
        'projection_player_states',
    }, 'projection_player_states'),
}


def _quote(value):
    return '"' + value.replace('"', '""') + '"'


def _tables(connection):
    return dict(connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"))


def _ordered_rows(connection, table):
    columns = list(connection.execute(f'PRAGMA table_info({_quote(table)})'))
    keys = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
    if not keys:
        raise ValueError('Migration requires an explicit stable primary key')
    return connection.execute(f'SELECT * FROM {_quote(table)} ORDER BY ' + ','.join(map(_quote, keys)))


def digest(connection, kind):
    codec, history, allowed, states = KINDS[kind]
    tables = _tables(connection)
    if set(tables) - allowed:
        raise ValueError('Unexpected storage table; migration requires review')
    results = {}
    for table in tables:
        if table == states:
            continue  # Physical representation; each reference is decoded below.
        columns = [row[1] for row in connection.execute(f'PRAGMA table_info({_quote(table)})')]
        sha = hashlib.sha256()
        count = 0
        for record in _ordered_rows(connection, table):
            row = list(record)
            if table == history:
                index = columns.index('payload')
                row[index] = codec.decode(connection, row[index])
            body = json.dumps(row, sort_keys=True, separators=(',', ':'), default=lambda b: {'bytes': base64.b64encode(b).decode()}).encode()
            sha.update(len(body).to_bytes(8, 'big'))
            sha.update(body)
            count += 1
        results[table] = {'count': count, 'sha256': sha.hexdigest()}
    return results


def migrate(path: Path, kind: str, *, maximum_bytes: int, reserve_bytes: int,
            restore_legacy: bool = False, before_publish=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Migration requires an existing regular database')
    path = path.resolve()
    if maximum_bytes <= 0 or reserve_bytes < 0:
        raise ValueError('Invalid migration budget')
    codec, history, allowed, states = KINDS[kind]
    # At most one compact output plus rollback journal for that bounded output.
    required = maximum_bytes * 2 + reserve_bytes
    with database_gate(path, exclusive=True):
        prefix = '.dtos-storage-migration-' + hashlib.sha256(str(path).encode()).hexdigest()[:12] + '-'
        # A killed process cannot publish its incomplete output. Recover only
        # this database's recognized scratch files, under its exclusive fence.
        for abandoned in path.parent.glob(prefix + '*'):
            if abandoned.is_symlink() or not abandoned.is_dir():
                raise RuntimeError('Unexpected migration scratch path')
            if any(p.is_symlink() or p.name not in {'compact.sqlite3', 'compact.sqlite3-journal'} or not p.is_file() for p in abandoned.iterdir()):
                raise RuntimeError('Unrecognized migration scratch contents')
            shutil.rmtree(abandoned)
        if shutil.disk_usage(path.parent).free < required:
            raise RuntimeError('Insufficient migration headroom')
        with tempfile.TemporaryDirectory(prefix=prefix, dir=path.parent) as folder:
            target = Path(folder) / 'compact.sqlite3'
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source:
                source.execute('PRAGMA query_only=ON')
                source.execute('BEGIN')
                if source.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
                    raise RuntimeError('Migration requires reviewed DELETE journal boundary')
                if source.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Source integrity check failed')
                before = digest(source, kind)
                with closing(sqlite3.connect(target)) as destination:
                    destination.execute('PRAGMA synchronous=FULL')
                    destination.execute(f'PRAGMA max_page_count={maximum_bytes // 4096}')
                    for sql in _tables(source).values():
                        destination.execute(sql)
                    destination.executescript(codec.SCHEMA)
                    # Retain existing states too; no orphan/unique data deletion.
                    for table in sorted(_tables(source), key=lambda name: name != states):
                        columns = [row[1] for row in source.execute(f'PRAGMA table_info({_quote(table)})')]
                        count = 0
                        for record in _ordered_rows(source, table):
                            row = list(record)
                            if table == history:
                                index = columns.index('payload')
                                payload = codec.decode(source, row[index])
                                row[index] = json.dumps(payload, sort_keys=True, separators=(',', ':')) if restore_legacy else codec.encode(destination, payload)
                            destination.execute(f'INSERT OR IGNORE INTO {_quote(table)} VALUES ({",".join("?" for _ in row)})', row)
                            count += 1
                            if count % 32 == 0:
                                destination.commit()
                        destination.commit()
                    for (sql,) in source.execute("SELECT sql FROM sqlite_master WHERE type IN ('index','trigger','view') AND sql IS NOT NULL ORDER BY type,name"):
                        destination.execute(sql)
                    destination.commit()
                    if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Compact integrity check failed')
                    after = digest(destination, kind)
                    if before != after:
                        raise RuntimeError('Migration logical equivalence failed')
            # Both SQLite connections are closed; the exclusive gate still
            # excludes old-inode readers/writers. Power loss sees old OR new DB.
            if before_publish:
                before_publish()
            size_before = path.stat().st_size
            size_after = target.stat().st_size
            if size_after > maximum_bytes:
                raise RuntimeError('Migration exceeded admitted compact size')
            os.chmod(target, path.stat().st_mode & 0o777)
            with target.open('r+b') as handle:
                os.fsync(handle.fileno())
            os.replace(target, path)
            if os.name != 'nt':
                fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            return {'kind': kind, 'before_bytes': size_before, 'after_bytes': size_after,
                    'reclaimed_bytes': size_before - size_after, 'integrity': 'ok',
                    'logical_equivalence': True, 'tables': after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=KINDS)
    parser.add_argument('database', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--maximum-mib', type=int, required=True)
    parser.add_argument('--reserve-mib', type=int, default=128)
    parser.add_argument('--restore-legacy', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        with closing(sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            report = {'dry_run': True, 'integrity': digest(connection, args.kind)}
            if args.kind == 'fois':
                report.update(fois.classify(connection))
        print(json.dumps(report, sort_keys=True))
        return
    print(json.dumps(migrate(args.database, args.kind,
        maximum_bytes=args.maximum_mib * 1048576, reserve_bytes=args.reserve_mib * 1048576,
        restore_legacy=args.restore_legacy), sort_keys=True))


if __name__ == '__main__':
    main()
