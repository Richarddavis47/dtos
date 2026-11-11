"""Read-only per-test timings and console capture for isolated release validation."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest

if os.environ.get("DTOS_ATTRIBUTION_TEST_LOG") and "discover" in sys.argv:
    _console = open("/output/unittest-console.log", "a", buffering=1)
    _lock = threading.RLock()

    class _Tee:
        def __init__(self, original):
            self.original = original

        def write(self, value):
            with _lock:
                _console.write(value)
                _console.flush()
            return self.original.write(value)

        def flush(self):
            _console.flush()
            return self.original.flush()

        def __getattr__(self, name):
            return getattr(self.original, name)

    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)

    def record(event, test, error=None):
        pages = Path("/proc/self/statm").read_text().split()
        row = dict(event=event, test=test.id(), time=time.time(), pid=os.getpid(),
                   rss=int(pages[1]) * os.sysconf("SC_PAGE_SIZE"),
                   cgroup=int(Path("/sys/fs/cgroup/memory.current").read_text()))
        if error:
            row["error_type"] = error[0].__name__ if isinstance(error, tuple) else "skip"
            row["error_text"] = str(error[1])[:2000] if isinstance(error, tuple) else str(error)
        with open(os.environ["DTOS_ATTRIBUTION_TEST_LOG"], "a") as stream:
            stream.write(json.dumps(row) + "\n")

    _dtos_last_module = None

    for name, event in [("startTest", "start"), ("stopTest", "stop"),
                        ("addError", "error"), ("addFailure", "failure"),
                        ("addSkip", "skip")]:
        original = getattr(unittest.TestResult, name)

        def observed(self, test, *args, _original=original, _event=event):
            global _dtos_last_module
            if _event == "start":
                module = type(test).__module__
                if module != _dtos_last_module:
                    from fixture_cleanup import reclaim_completed_fixtures
                    reclaim_completed_fixtures(module, "/output/module-cleanup.jsonl")
                    _dtos_last_module = module
            record(_event, test, args[0] if args else None)
            return _original(self, test, *args)

        setattr(unittest.TestResult, name, observed)
