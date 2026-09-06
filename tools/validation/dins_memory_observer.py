"""Isolated post-failure allocator attribution; never a production entry point."""
import ctypes
import json
import os
import signal
from pathlib import Path

import psutil

if os.environ.get('RENDER') or os.environ.get('DTOS_DINS_ALLOCATOR_DIAGNOSTIC') != '1':
    raise RuntimeError('Allocator observer requires the isolated diagnostic fixture')

from dtos_app import app  # noqa: E402,F401 - exact production route inventory


def observe(_signal, _frame):
    process = psutil.Process()
    before = process.memory_info().rss
    trim = ctypes.CDLL(None).malloc_trim
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    released = trim(0)
    Path('/output/server-allocator.json').write_text(json.dumps({
        'diagnostic_only': True, 'before_rss_bytes': before,
        'after_rss_bytes': process.memory_info().rss, 'trim_result': released,
        'gc_invoked': False, 'caches_cleared': False,
    }))


signal.signal(signal.SIGUSR1, observe)
