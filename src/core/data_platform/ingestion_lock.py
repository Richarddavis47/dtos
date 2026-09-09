"""Nonblocking OS-owned ingestion flight lock, shared by app and explicit CLI."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def ingestion_lock(database: Path):
    # Keep this one-byte inode stable: unlinking it could allow two independent
    # locks on Linux. Kernel ownership is released even after process death.
    path = database.with_name(database.name + '.ingestion-lock')
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        acquired = False
        try:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, PermissionError):
                pass
            yield acquired
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
