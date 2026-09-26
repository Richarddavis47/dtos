"""Explicit FOIS-only publication of a prebuilt, verified compact database.

Never called by startup. Preparation and durable off-volume rollback backup
must precede this command. Existing pending files fail closed for operator
inspection; this command never guesses whether interrupted work is disposable.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from src.platform.storage_gate import database_gate
from tools.storage_migration import digest

MIB = 1024**2
CAP = 72 * MIB
RESERVE = 128 * MIB
ADMISSION = 232 * MIB


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def checked_path(value):
    path = Path(value).absolute()
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError('Expected an existing regular file without linked parents')
    return path


def require_no_sidecars(path):
    for suffix in ('-wal', '-shm', '-journal'):
        if path.with_name(path.name + suffix).exists():
            raise ValueError('SQLite sidecar present; reviewed quiescent boundary required')


def proof(path):
    require_no_sidecars(path)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        if conn.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
            raise ValueError('Expected DELETE journal boundary')
        if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity failed')
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'fois_scores_v2', 'fois_snapshot_history', 'fois_semantic_states'} <= tables:
            raise ValueError('Not the expected FOIS store')
        return digest(conn, 'fois')


def sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def publish(live, candidate, backup, *, source_sha256, candidate_sha256,
            rollback=False):
    for expected in (source_sha256, candidate_sha256):
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Explicit lowercase SHA256 identities are required')
    if source_sha256 == candidate_sha256:
        raise ValueError('No-op or already-published migration is not permitted')
    live, candidate, backup = map(checked_path, (live, candidate, backup))
    if any(os.path.samefile(a, b) for a, b in
           ((live, candidate), (live, backup), (candidate, backup))):
        raise ValueError('Live, candidate and rollback evidence must be distinct files')
    pending = live.with_name(live.name + '.staged-fois-pending')
    # Source hash pins the operator-reviewed generation; second invocation
    # after a successful cutover fails rather than silently migrating again.
    with database_gate(live, exclusive=True):
        if pending.exists() or pending.is_symlink():
            raise RuntimeError('Interrupted pending file requires explicit review')
        if sha256(live) != source_sha256:
            raise ValueError('Source generation changed')
        if sha256(candidate) != candidate_sha256:
            raise ValueError('Candidate checksum mismatch')
        if sha256(backup) != source_sha256:
            raise ValueError('Rollback backup does not match live source')
        size = candidate.stat().st_size
        maximum = size if rollback else CAP
        required = maximum + RESERVE if rollback else ADMISSION
        if size > maximum or shutil.disk_usage(live.parent).free < required:
            raise RuntimeError('Insufficient staged migration headroom or target exceeds cap')
        before = proof(live)
        if proof(candidate) != before or proof(backup) != before:
            raise ValueError('FOIS logical equivalence failed')
        # Recheck admission after CPU-intensive equivalence work.
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
            for path in (live, backup, pending):
                require_no_sidecars(path)
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
        return {'kind': 'fois', 'rollback': rollback, 'logical_equivalence': True,
                'published_sha256': sha256(live), 'after_bytes': size,
                'backup_preserved': True, 'tables': before}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('backup', type=Path)
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
