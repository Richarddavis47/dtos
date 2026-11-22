"""Compare the unchanged four-width journey with a fixed resident-memory charge."""
from datetime import datetime, timezone
import json
import mmap
from pathlib import Path
import sys
import unittest

root = Path('/sys/fs/cgroup')
assert int((root/'memory.max').read_text()) == 2147483648
assert int((root/'memory.swap.max').read_text()) == 0
charge = 856 * 1024 * 1024
with mmap.mmap(-1, charge, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS) as ballast:
    for offset in range(0, charge, mmap.PAGESIZE):
        ballast[offset] = 1
    print(json.dumps(dict(phase='charged', resident_control_bytes=charge,
                          cgroup_current=int((root/'memory.current').read_text()),
                          utc=datetime.now(timezone.utc).isoformat())), flush=True)
    sys.path.insert(0, '/app')
    module = 'tests.test_rebuild_roster_space_browser'
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(passed=result.wasSuccessful(), count=result.testsRun,
                          peak=int((root/'memory.peak').read_text()),
                          events=(root/'memory.events').read_text())), flush=True)
    sys.exit(0 if result.wasSuccessful() else 1)
