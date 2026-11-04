"""Fresh, never-active compact targets with no full-size rollback staging.

Only the disposable output uses OFF journaling while under construction. A
crash may destroy that output, never the read-only source. It is restored to
DELETE, integrity/equivalence checked and fsynced before it can be admitted.
No application can discover the target via its normal configured live path.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3

from src.core.fois import state_storage as codec
from src.platform.storage_gate import database_gate
from tools.recovery_guard import ADMISSION, RESERVE, MIB
from tools.staged_fois_cutover import checked_path, require_no_sidecars, sha256, sync_directory, proof
from tools.storage_migration import _tables, _ordered_rows, _quote
from tools.projection_retention_migration import build_copy, verify_copy


def build_fois(source, target, guard, backup, verify_backup):
    source, target = checked_path(source), Path(target).absolute()
    if source.parent != guard.root or target.parent != guard.root:
        raise ValueError('Candidate construction must stay on the admitted persistent filesystem')
    if target.exists() or target.is_symlink():
        raise ValueError('Existing candidate requires explicit review')
    guard.check(required=ADMISSION)
    with database_gate(source, exclusive=True):
        guard.check(required=ADMISSION)
        require_no_sidecars(source)
        source_hash = sha256(source)
        verify_backup(backup, source_hash, source.stat().st_size)
        before = proof(source)
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as old:
            old.execute('PRAGMA query_only=ON')
            old.execute('PRAGMA temp_store=MEMORY')
            old.execute('BEGIN')
            with closing(sqlite3.connect(target)) as new:
                os.chmod(target, 0o600)
                new.execute('PRAGMA page_size=4096')
                new.execute(f'PRAGMA max_page_count={72 * MIB // 4096}')
                new.execute('PRAGMA temp_store=MEMORY')
                new.execute('PRAGMA journal_mode=OFF')
                new.execute('PRAGMA synchronous=FULL')
                for schema in _tables(old).values():
                    new.execute(schema)
                new.executescript(codec.SCHEMA)
                bases = {}
                for table in sorted(_tables(old), key=lambda name: name == 'fois_semantic_states'):
                    columns = [r[1] for r in old.execute(f'PRAGMA table_info({_quote(table)})')]
                    rows = (old.execute('SELECT * FROM fois_snapshot_history ORDER BY score_key,generated_at,snapshot_id')
                            if table == 'fois_snapshot_history' else _ordered_rows(old, table))
                    for count, record in enumerate(rows, 1):
                        row = list(record)
                        if table == 'fois_snapshot_history':
                            index = columns.index('payload')
                            value = codec.decode(old, row[index])
                            identity = value['score_key']
                            row[index] = codec.encode(new, value, base_payload=bases.get(identity))
                            bases[identity] = value
                        new.execute(f'INSERT OR IGNORE INTO {_quote(table)} VALUES ({",".join("?" for _ in row)})', row)
                        if count % 32 == 0:
                            new.commit()
                            guard.check(required=RESERVE)
                    new.commit()
                for (sql,) in old.execute("SELECT sql FROM sqlite_master WHERE type IN ('index','trigger','view') AND sql IS NOT NULL ORDER BY type,name"):
                    new.execute(sql)
                    new.commit()
                    guard.check(required=RESERVE)
                new.execute('PRAGMA journal_mode=DELETE')
        if sha256(source) != source_hash or proof(target) != before:
            raise ValueError('Source/equivalence changed during construction')
        guard.check(required=RESERVE)
        with target.open('r+b') as handle:
            os.fsync(handle.fileno())
        sync_directory(target.parent)
        return {'source_sha256': source_hash, 'candidate_sha256': sha256(target),
                'candidate_bytes': target.stat().st_size, 'equivalence': before,
                'admission_bytes': ADMISSION, 'source_unchanged': True}


def build_projection(source, target, guard, backup, verify_backup):
    source, target = checked_path(source), Path(target).absolute()
    if source.parent != guard.root or target.parent != guard.root:
        raise ValueError('Candidate construction must stay on the admitted persistent filesystem')
    guard.check(required=352 * MIB)
    with database_gate(source, exclusive=True):
        guard.check(required=352 * MIB)
        require_no_sidecars(source)
        source_hash = sha256(source)
        verify_backup(backup, source_hash, source.stat().st_size)
        report = build_copy(source, target, maximum_bytes=112 * MIB, reserve_bytes=RESERVE,
                            progress_check=lambda: guard.check(required=RESERVE))
        report['equivalence'] = verify_copy(source, target)
        if sha256(source) != source_hash:
            raise ValueError('Source changed during construction')
        guard.check(required=RESERVE)
        with target.open('r+b') as handle:
            os.fsync(handle.fileno())
        sync_directory(target.parent)
        return {**report, 'source_sha256': source_hash, 'candidate_sha256': sha256(target),
                'candidate_bytes': target.stat().st_size, 'admission_bytes': 352 * MIB}
