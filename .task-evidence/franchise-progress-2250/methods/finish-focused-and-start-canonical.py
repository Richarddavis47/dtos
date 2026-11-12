"""Sequential real acceptance: focused -> native resources -> complete validator."""
from pathlib import Path
import datetime
import fcntl
import json
import subprocess
import time

from common import BASE, assert_checkout, load_source, write_json

lock = (BASE / 'focused-to-canonical.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
source = load_source()
began = time.monotonic()
result_path = BASE / 'focused-exact/result.json'
log = BASE / 'focused-final-b522-spawn-safe-launch-original.log'
while not result_path.exists() or 'Final focused exit ' not in log.read_text():
    assert time.monotonic() - began < 15 * 60, 'Focused result incomplete; leave held'
    time.sleep(3)
result = json.loads(result_path.read_text())
assert result['commit'] == source['candidate'] and result['tree'] == source['tree']
assert result['passed'] and result['tests'] == 103
assert result['failures'] == result['errors'] == result['skipped'] == 0
assert result['memory_limit'] == 2147483648 and not result['dirty']
assert not any(int(result['events'].get(key, 0)) for key in ('oom', 'oom_kill'))
assert 'Final focused exit 0' in log.read_text()
assert_checkout(source)
write_json(BASE / 'focused-ready.json', dict(candidate=source['candidate'], tree=source['tree'],
    passed=True, tests=103, memory_limit=result['memory_limit'], peak=result['peak'],
    original='focused-exact/original-console.log',
    scope='Actual final-source focused methods, including15 real FOIS worker controls and88 history controls; no deferral counted as completion'))
print('FOCUSED_103_PASS; starting fresh native resource controls', flush=True)
with (BASE / 'resource-sequence-original.log').open('xb') as sink:
    subprocess.run(['python', str(BASE / 'run-local-resource.py')], stdout=sink,
                   stderr=subprocess.STDOUT, check=True)
resource = json.loads((BASE / 'resource-preservation-verified.json').read_text())
assert resource['all_native_guards_passed'] and resource['source']['candidate'] == source['candidate']
print('NATIVE_RESOURCE_3_PASS; starting unchanged complete canonical validator', flush=True)
with (BASE / 'canonical-launch-original.log').open('xb') as sink:
    subprocess.run(['python', str(BASE / 'start-release-canonical.py')], stdout=sink,
                   stderr=subprocess.STDOUT, check=True)
print('FULL_LOCAL_CANONICAL_STARTED; no success claim until final originals verified', flush=True)
with (BASE / 'local-completion-observer-original.log').open('xb') as sink:
    subprocess.run(['python', str(BASE / 'finish-local-originals.py')], stdout=sink,
                   stderr=subprocess.STDOUT, check=True)
print('FULL_LOCAL_AND_REQUIRED_SUPPLEMENTS_VERIFIED', flush=True)
