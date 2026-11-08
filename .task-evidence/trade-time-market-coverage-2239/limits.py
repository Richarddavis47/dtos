"""Disposable-container measurement only, never serving-process state."""
from pathlib import Path
from datetime import datetime,timezone
import json,platform
base=Path('/sys/fs/cgroup')
report={'observed_at':datetime.now(timezone.utc).isoformat(),'runtime':platform.python_version(),
    'scope':'Separate disposable audit container, not production or the serving application process',
    'memory_max':int((base/'memory.max').read_text()),'swap_max':(base/'memory.swap.max').read_text().strip(),
    'memory_current':int((base/'memory.current').read_text()),
    'memory_events':dict(line.split() for line in (base/'memory.events').read_text().splitlines())}
assert report['memory_max']==2147483648 and report['swap_max']=='0'
Path('/evidence/container.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
