"""Constant-memory encrypted backup stream and independently signed receipts.

The sender writes only to a transport stream, never to a temporary archive.
The receiver retains ciphertext and verifies SQLite using local private scratch.
Transport pairing/credentials are deliberately absent from receipts.
"""
from contextlib import closing
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from tools.staged_fois_cutover import checked_path, require_no_sidecars, sha256

MAGIC = b'DTOSREC2'
CHUNK = 1024 * 1024


def body(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def write_all(output, data):
    remaining = memoryview(data)
    while remaining:
        written = output.write(remaining)
        if not written or written < 0:
            raise OSError('Backup transport stopped accepting bytes')
        remaining = remaining[written:]


def integrity(path):
    require_no_sidecars(path)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
            raise ValueError('Expected quiescent DELETE journal boundary')
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Backup SQLite integrity failed')


def allowed_source(path):
    """Never turn the recovery transfer into an arbitrary database exporter."""
    from tools.storage_migration import KINDS
    from tools.projection_retention_migration import ALLOWED
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if {'fois_scores_v2', 'fois_snapshot_history', 'fois_semantic_states'} <= names <= KINDS['fois'][2]:
        return 'fois'
    if {'projection_snapshots', 'projection_publication_heads', 'projection_player_states'} <= names <= ALLOWED:
        return 'projection'
    raise ValueError('Only reviewed FOIS/Projection stores may be transferred')


def stable_identity(source, guard):
    source = checked_path(source)
    guard.check()
    allowed_source(source)
    integrity(source)
    identity = sha256(source)
    stat = source.stat()
    return {'source_sha256': identity, 'source_bytes': stat.st_size,
            'stat': (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)}


def encrypt_stream(source, output, public_pem, guard, *, verified=None):
    """Called while maintenance and the database's exclusive gate are held.

    A transport may supply the preflight performed under that same fence so
    a network reactor never blocks waiting for an integrity scan mid-transfer.
    The streamed SHA proves the output is precisely the checked source bytes.
    """
    source = checked_path(source)
    verified = verified or stable_identity(source, guard)
    stat = source.stat()
    if (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) != verified['stat']:
        raise ValueError('Source changed since preflight')
    before, size = verified['source_sha256'], verified['source_bytes']
    public = serialization.load_pem_public_key(public_pem)
    secret, nonce = os.urandom(32), os.urandom(12)
    wrapped = public.encrypt(secret, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                                algorithm=hashes.SHA256(), label=None))
    metadata = body({'schema': 2, 'source_sha256': before, 'source_bytes': size})
    header = MAGIC + len(wrapped).to_bytes(4, 'big') + wrapped + nonce + len(metadata).to_bytes(4, 'big') + metadata
    encryptor = Cipher(algorithms.AES(secret), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    write_all(output, header)
    seen, count = hashlib.sha256(), 0
    with source.open('rb') as inp:
        while chunk := inp.read(CHUNK):
            seen.update(chunk)
            count += len(chunk)
            if count > size:
                raise ValueError('Source grew during streaming')
            if count % (16 * CHUNK) == 0:
                guard.check()
            write_all(output, encryptor.update(chunk))
    stat = source.stat()
    if (count != size or seen.hexdigest() != before
            or (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) != verified['stat']):
        raise ValueError('Source changed during streaming')
    guard.check()
    write_all(output, encryptor.finalize())
    write_all(output, encryptor.tag)
    return json.loads(metadata)


def verify_local(package, private_pem, scratch):
    """Only the local receiver uses plaintext scratch. Never run on Render."""
    if os.environ.get('RENDER') or str(Path(scratch).absolute()).startswith('/var/data'):
        raise ValueError('Local backup verification cannot run on Render')
    package, scratch = checked_path(package), Path(scratch).absolute()
    if scratch.exists() or scratch.is_symlink():
        raise ValueError('Verification scratch must be new')
    private = serialization.load_pem_private_key(private_pem, password=None)
    created = False
    try:
        with package.open('rb') as inp:
            magic, length = inp.read(len(MAGIC)), inp.read(4)
            n = int.from_bytes(length, 'big')
            if magic != MAGIC or not 256 <= n <= 1024:
                raise ValueError('Invalid encrypted backup header')
            wrapped, nonce, mlen = inp.read(n), inp.read(12), inp.read(4)
            nmeta = int.from_bytes(mlen, 'big')
            if not 1 <= nmeta <= 4096:
                raise ValueError('Invalid backup metadata length')
            encoded = inp.read(nmeta)
            metadata = json.loads(encoded)
            header = magic + length + wrapped + nonce + mlen + encoded
            start = inp.tell()
            remaining = package.stat().st_size - start - 16
            if remaining != metadata['source_bytes']:
                raise ValueError('Backup size mismatch')
            inp.seek(-16, 2)
            tag = inp.read(16)
            inp.seek(start)
            secret = private.decrypt(wrapped, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                                           algorithm=hashes.SHA256(), label=None))
            dec = Cipher(algorithms.AES(secret), modes.GCM(nonce, tag)).decryptor()
            dec.authenticate_additional_data(header)
            with scratch.open('xb') as out:
                created = True
                os.chmod(scratch, 0o600)
                while remaining:
                    chunk = inp.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ValueError('Truncated backup')
                    remaining -= len(chunk)
                    out.write(dec.update(chunk))
                out.write(dec.finalize())
                out.flush()
                os.fsync(out.fileno())
        if sha256(scratch) != metadata['source_sha256']:
            raise ValueError('Backup checksum mismatch')
        integrity(scratch)
        receipt = {**metadata, 'destination_sha256': sha256(scratch),
                   'destination_bytes': scratch.stat().st_size, 'sqlite_integrity': 'ok',
                   'encrypted_package_sha256': sha256(package), 'schema': 2}
        signature = private.sign(body(receipt), padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                          salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
        return {'receipt': receipt, 'signature': base64.b64encode(signature).decode()}
    finally:
        if created:
            scratch.unlink()


def receipt_verifier(public_pem):
    """Public key must be independently pinned to the approved local receiver."""
    public = serialization.load_pem_public_key(public_pem)

    def verify(signed, expected_sha, expected_bytes):
        receipt = signed['receipt']
        public.verify(base64.b64decode(signed['signature'], validate=True), body(receipt),
                      padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
        if (receipt.get('schema') != 2 or receipt.get('source_sha256') != expected_sha
                or receipt.get('destination_sha256') != expected_sha
                or receipt.get('source_bytes') != expected_bytes
                or receipt.get('destination_bytes') != expected_bytes
                or receipt.get('sqlite_integrity') != 'ok'):
            raise ValueError('Off-host backup verification mismatch')
        return receipt
    return verify
