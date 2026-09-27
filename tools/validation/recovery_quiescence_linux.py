"""Disposable Linux-container guard proof; never run on a production host."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from tools.recovery_guard import RecoveryGuard


def main():
    if os.environ.get('RENDER') or os.environ.get('DTOS_DISPOSABLE_RECOVERY_TEST') != '1':
        raise RuntimeError('Explicit disposable container required')
    root = Path('/var/data/dtos')
    root.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, PORT='19891')
    os.environ['PORT'] = environment['PORT']
    maintenance = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tools.storage_maintenance:app',
                                    '--host', '127.0.0.1', '--port', environment['PORT']],
                                   env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    writer = None
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen('http://127.0.0.1:19891/health', timeout=1):
                    break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Synthetic maintenance process did not start')
        guard = RecoveryGuard(root)
        guard.check()
        writer = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        time.sleep(.1)
        try:
            guard.check()
        except RuntimeError as exc:
            if 'process remains active' not in str(exc):
                raise
        else:
            raise AssertionError('Live Python worker was not rejected')
        writer.terminate()
        writer.wait(timeout=10)
        writer = None
        guard.check()
        maintenance.terminate()
        maintenance.wait(timeout=10)
        try:
            guard.check()
        except OSError:
            pass
        else:
            raise AssertionError('Missing maintenance was not rejected')
        print('Linux maintenance/quiescence positive and negative checks passed.')
    finally:
        for process in (writer, maintenance):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
