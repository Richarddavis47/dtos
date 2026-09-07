"""Cooperative cross-process connection fence for atomic storage maintenance.

Normal Linux connections share the fence. Maintenance holds it exclusively,
so no connection can retain an old inode across compact-file publication.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import time


@contextmanager
def database_gate(path: Path, *, exclusive: bool = False):
    lock_path = path.with_name(path.name + '.storage-lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            deadline = time.monotonic() + 120
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Storage maintenance fence timeout') from None
                    time.sleep(.02)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class _Connection(sqlite3.Connection):
    _gate = None

    def close(self):
        try:
            super().close()
        finally:
            if self._gate is not None:
                gate, self._gate = self._gate, None
                gate.__exit__(None, None, None)


def connect(path: Path, *, timeout: float = 30, readonly: bool = False):
    gate = database_gate(path)
    gate.__enter__()
    try:
        target = path.resolve().as_uri() + '?mode=ro' if readonly else str(path)
        connection = sqlite3.connect(target, uri=readonly, timeout=timeout, factory=_Connection)
        connection._gate = gate
        return connection
    except BaseException:
        gate.__exit__(None, None, None)
        raise
