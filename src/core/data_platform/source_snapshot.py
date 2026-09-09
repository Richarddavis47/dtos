"""Short-lived, size-admitted source snapshots for background ingestion only.

Download before taking a database write lock. Hash decoded source bytes so
resumption cannot combine two changing provider responses. No raw feed survives
the context, whether download, normalization, or publication fails.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import httpx


@dataclass(frozen=True)
class SourceSnapshot:
    path: Path
    sha256: str
    bytes_downloaded: int


@contextmanager
def download_snapshot(client: httpx.Client, url: str, *, directory: Path,
                      maximum_bytes: int = 32 * 1048576,
                      reserve_bytes: int = 128 * 1048576) -> Iterator[SourceSnapshot]:
    """Caller supplies an approved public source URL, never a user URL.

    Limits apply to decoded bytes (including compressed transfer responses).
    The configured directory is temporary workspace, not permanent history.
    """
    if maximum_bytes <= 0 or reserve_bytes < 0:
        raise ValueError("Invalid source snapshot budget.")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < reserve_bytes + maximum_bytes:
        raise OSError("Insufficient disk reserve for source snapshot.")
    with tempfile.TemporaryDirectory(prefix="global-source-", dir=directory) as temporary:
        path = Path(temporary) / "source.csv"
        digest = hashlib.sha256()
        size = 0
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with path.open("wb") as target:
                for chunk in response.iter_bytes(chunk_size=65536):
                    size += len(chunk)
                    if size > maximum_bytes:
                        raise ValueError("Source exceeds admitted decoded-byte budget.")
                    if shutil.disk_usage(directory).free < reserve_bytes + len(chunk):
                        raise OSError("Source download would violate disk reserve.")
                    target.write(chunk)
                    digest.update(chunk)
        if not size:
            raise ValueError("Source snapshot is empty.")
        yield SourceSnapshot(path, digest.hexdigest(), size)
