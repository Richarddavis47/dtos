"""One-time Wormhole encrypted streaming; no sender-side database/archive copy.

Optional operator dependency only. Uses the existing Wormhole sender transport,
with a bounded pipe supplying ciphertext instead of a staged regular file.
No listening endpoint, persistent pairing credential, or application imports.
"""
import argparse
import os
from pathlib import Path
import threading
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization

from src.platform.storage_gate import database_gate
from tools.recovery_backup import MAGIC, body, encrypt_stream, stable_identity
from tools.recovery_guard import RecoveryGuard
from tools.staged_fois_cutover import checked_path, sha256


def encrypted_length(source_bytes, source_sha256, public_pem):
    public = serialization.load_pem_public_key(public_pem)
    metadata = body({'schema': 2, 'source_sha256': source_sha256, 'source_bytes': source_bytes})
    return len(MAGIC) + 4 + public.key_size // 8 + 12 + 4 + len(metadata) + source_bytes + 16


def pipe_sender(source, public_pem, guard, *, verified=None):
    """Caller keeps the exclusive source gate for the entire pipe lifecycle."""
    verified = verified or stable_identity(source, guard)
    read_fd, write_fd = os.pipe()
    errors = []

    def produce():
        try:
            with os.fdopen(write_fd, 'wb', buffering=0) as output:
                encrypt_stream(source, output, public_pem, guard, verified=verified)
        except BaseException as exc:
            errors.append(exc)

    reader = os.fdopen(read_fd, 'rb', buffering=0)
    worker = threading.Thread(target=produce, name='bounded-backup-stream', daemon=True)
    worker.start()

    def finish():
        reader.close()
        worker.join(timeout=30)
        if worker.is_alive():
            raise RuntimeError('Backup producer did not stop')
        if errors:
            raise RuntimeError('Encrypted backup stream failed') from errors[0]
    return reader, finish


class SizedPipe:
    """Support Wormhole's initial size probe, never fake a data rewind.

    The CLI seeks to EOF/tells/seeks to zero before FileSender reads. A pipe
    cannot seek, so answer that *metadata-only* probe from the pinned length.
    Any seek after consumption fails rather than silently resending bad bytes.
    """

    def __init__(self, reader, size):
        self.reader, self.size, self.position, self.started = reader, size, 0, False

    def seek(self, offset, whence=0):
        if self.started or offset != 0 or whence not in (0, 2):
            raise OSError('Encrypted stream cannot rewind')
        self.position = self.size if whence == 2 else 0
        return self.position

    def tell(self):
        return self.position

    def read(self, length):
        if not self.started and self.position:
            raise OSError('Stream size probe was not reset')
        self.started = True
        chunk = self.reader.read(length)
        self.position += len(chunk)
        if self.position > self.size:
            raise ValueError('Stream exceeded pinned size')
        return chunk

    def close(self):
        self.reader.close()


def send(source, public_pem, guard):
    # Keep imports optional: normal application and command discovery must not
    # initialize a reactor, contact a relay, or require this operator dependency.
    from wormhole.cli.cli import wormhole
    from wormhole.cli.cmd_send import Sender

    source = checked_path(source)
    guard.check()
    with database_gate(source, exclusive=True):
        guard.check()
        verified = stable_identity(source, guard)
        pinned = verified['source_sha256']
        size = encrypted_length(verified['source_bytes'], pinned, public_pem)
        handle, finish = pipe_sender(source, public_pem, guard, verified=verified)
        sized = SizedPipe(handle, size)

        def offer(_sender):
            return {'file': {'filename': 'rollback.enc', 'filesize': size}}, sized

        try:
            with patch.object(Sender, '_build_offer', offer):
                try:
                    wormhole.main(args=['send', '--no-listen', str(source)], standalone_mode=False)
                except SystemExit as exc:
                    if exc.code not in (None, 0):
                        raise
        finally:
            finish()
        if sha256(source) != pinned:
            raise RuntimeError('Source changed across transfer')
        guard.check()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('receiver_public_key', type=Path)
    parser.add_argument('--rehearsal', action='store_true')
    parser.add_argument('--temporary-root', type=Path, help='Local rehearsal temporary root only')
    args = parser.parse_args()
    guard = RecoveryGuard(args.source.absolute().parent, rehearsal=args.rehearsal,
                          temporary_root=args.temporary_root)
    send(args.source, args.receiver_public_key.read_bytes(), guard)


if __name__ == '__main__':
    main()
