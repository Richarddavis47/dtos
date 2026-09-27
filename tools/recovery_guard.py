"""Fail-closed resource/quiescence checks for explicit recovery commands only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import urllib.request

MIB = 1024**2
ADMISSION = 232 * MIB
RESERVE = 128 * MIB
TMP_LIMIT = 2_000_000_000  # platform limit, not host filesystem capacity
TMP_CEILING = 256 * MIB


def allocated_tree(root):
    """Count allocated bytes, including hardlinks once; never follow symlinks."""
    seen, total = set(), 0
    def unreadable(error):
        raise error
    for folder, directories, files in os.walk(root, followlinks=False, onerror=unreadable):
        directories[:] = [n for n in directories if not (Path(folder) / n).is_symlink()]
        for name in files:
            path = Path(folder) / name
            if path.is_symlink():
                continue
            stat = path.stat()
            identity = stat.st_dev, stat.st_ino
            if identity not in seen:
                seen.add(identity)
                total += getattr(stat, 'st_blocks', (stat.st_size + 511) // 512) * 512
    return total


class RecoveryGuard:
    """Production checks cannot be replaced by a boolean CLI assertion.

    Local rehearsal is explicit, confined to an existing local root, and never
    admitted on Render or for its persistent mount. No process is stopped here.
    """

    def __init__(self, root, *, rehearsal=False, temporary_root=None):
        self.root = Path(root).resolve(strict=True)
        self.rehearsal = rehearsal
        self.temporary_root = Path(temporary_root or ('/tmp' if not rehearsal else self.root))
        if rehearsal and (os.environ.get('RENDER') or str(self.root).startswith('/var/data')):
            raise ValueError('Rehearsal cannot target production')
        if not rehearsal and (os.name != 'posix' or self.root != Path('/var/data/dtos')):
            raise ValueError('Production recovery requires the reviewed persistent root')
        if not rehearsal and self.temporary_root != Path('/tmp'):
            raise ValueError('Production temporary accounting cannot be redirected')

    def check(self, *, required=0, temporary_output=0):
        if temporary_output < 0 or temporary_output > 8 * MIB:
            raise RuntimeError('Large temporary output prohibited')
        usage = allocated_tree(self.temporary_root)
        if usage + temporary_output > TMP_CEILING:
            raise RuntimeError('Temporary-storage safety ceiling exceeded')
        if shutil.disk_usage(self.root).free < required:
            raise RuntimeError('Insufficient persistent headroom')
        if not self.rehearsal:
            port = int(os.environ.get('PORT', '10000'))
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=5) as response:
                health = json.load(response)
            if health != {'status': 'maintenance', 'application_ready': False}:
                raise RuntimeError('Isolated maintenance required')
            maintenance = 0
            for process in Path('/proc').iterdir():
                if not process.name.isdigit() or int(process.name) == os.getpid():
                    continue
                try:
                    command = (process / 'cmdline').read_bytes().split(b'\0')
                    if b'tools.storage_maintenance:app' in command:
                        maintenance += 1
                    elif command and any(b'python' in c or b'uvicorn' in c for c in command[:2]):
                        raise RuntimeError('Unreviewed Python/application process remains active')
                    for fd in (process / 'fd').iterdir():
                        target = os.readlink(fd)
                        if target.startswith(str(self.root) + '/'):
                            raise RuntimeError('Persistent file still open by another process')
                        if target.startswith('/tmp/') and target.endswith(' (deleted)'):
                            # Deleted-but-open temporary files evade directory accounting.
                            raise RuntimeError('Unaccounted deleted temporary file remains open')
                except (FileNotFoundError, ProcessLookupError):
                    continue
            if maintenance != 1:
                raise RuntimeError('Expected exactly one isolated maintenance process')
        return {'temporary_allocated_bytes': usage, 'temporary_ceiling_bytes': TMP_CEILING,
                'persistent_free_bytes': shutil.disk_usage(self.root).free,
                'rehearsal': self.rehearsal}
