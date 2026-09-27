"""Explicit guarded projection publication after compatible release and quiescence.

Never imported by application startup. A separately verified durable rollback
copy and stopped non-cooperative writers are operator prerequisites.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3

from src.core.projection_intelligence.retention import POLICY
from src.platform.storage_gate import database_gate
from tools.projection_retention_migration import verify_copy
from tools.staged_fois_cutover import MIB, RESERVE, checked_path, sha256, sync_directory

CAP = 112 * MIB
ADMISSION = 352 * MIB


def boundary(path, *, compact):
    for suffix in ('-wal', '-shm', '-journal'):
        if path.with_name(path.name + suffix).exists():
            raise ValueError('SQLite sidecar present; quiescent boundary required')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
            raise ValueError('Expected DELETE journal boundary')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'projection_snapshots', 'projection_publication_heads',
                'projection_player_states', 'projection_source_history'} <= tables:
            raise ValueError('Not the expected Projection store')
        policies = list(db.execute('SELECT version FROM projection_retention_policy')) if 'projection_retention_policy' in tables else []
        if policies != ([(POLICY,)] if compact else []):
            raise ValueError('Wrong Projection format/policy boundary')


def publish(live, candidate, backup, *, source_sha256, candidate_sha256, rollback=False):
    for expected in (source_sha256, candidate_sha256):
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Explicit lowercase SHA256 identities are required')
    if source_sha256 == candidate_sha256:
        raise ValueError('No-op or already-published migration is not permitted')
    live, candidate, backup = map(checked_path, (live, candidate, backup))
    if any(os.path.samefile(a, b) for a, b in
           ((live, candidate), (live, backup), (candidate, backup))):
        raise ValueError('Live, candidate and rollback evidence must be distinct')
    pending = live.with_name(live.name + '.staged-projection-pending')
    with database_gate(live, exclusive=True):
        if pending.exists() or pending.is_symlink():
            raise RuntimeError('Interrupted pending file requires explicit review')
        if sha256(live) != source_sha256 or sha256(backup) != source_sha256:
            raise ValueError('Source generation or rollback backup changed')
        if sha256(candidate) != candidate_sha256:
            raise ValueError('Candidate checksum mismatch')
        size = candidate.stat().st_size
        maximum = size if rollback else CAP
        required = size + RESERVE if rollback else ADMISSION
        if size > maximum or shutil.disk_usage(live.parent).free < required:
            raise RuntimeError('Insufficient projection headroom or target exceeds cap')
        boundary(live, compact=rollback)
        boundary(backup, compact=rollback)
        boundary(candidate, compact=not rollback)
        # Rollback restores the complete original; only compare the admitted
        # retained subset in the forward direction, never invent lost history.
        report = verify_copy(candidate, live) if rollback else verify_copy(live, candidate)
        if shutil.disk_usage(live.parent).free < required:
            raise RuntimeError('Headroom changed during verification')
        owned = False
        try:
            with candidate.open('rb') as inp, pending.open('xb') as out:
                owned = True
                written = 0
                while chunk := inp.read(MIB):
                    written += len(chunk)
                    if written > maximum:
                        raise RuntimeError('Candidate grew beyond admitted cap')
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if sha256(pending) != candidate_sha256:
                raise ValueError('Staged checksum mismatch')
            if sha256(live) != source_sha256 or sha256(backup) != source_sha256:
                raise ValueError('Source or rollback evidence changed')
            for path, compact in ((live, rollback), (backup, rollback), (pending, not rollback)):
                boundary(path, compact=compact)
            if shutil.disk_usage(live.parent).free < RESERVE:
                raise RuntimeError('Safety reserve consumed before publication')
            os.chmod(pending, live.stat().st_mode & 0o777)
            with pending.open('r+b') as handle:
                os.fsync(handle.fileno())
            sync_directory(live.parent)
            os.replace(pending, live)
            sync_directory(live.parent)
        finally:
            if owned and pending.exists():
                pending.unlink()
                sync_directory(live.parent)
        return {'kind': 'projection', 'rollback': rollback,
                'published_sha256': sha256(live), 'after_bytes': size,
                'backup_preserved': True, 'proof': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('live', 'candidate', 'backup'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--candidate-sha256', required=True)
    parser.add_argument('--apply', action='store_true', required=True)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    print(json.dumps(publish(args.live, args.candidate, args.backup,
                             source_sha256=args.source_sha256,
                             candidate_sha256=args.candidate_sha256,
                             rollback=args.rollback), sort_keys=True))


if __name__ == '__main__':
    main()
