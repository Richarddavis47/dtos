"""Package original final-source evidence only after the canonical run passes."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

b = Path('/workspace/2231-release')
c = b/'canonical'
meta = json.loads((b/'source.json').read_text())
r = json.loads((c/'result.json').read_text())
assert r['passed'] and r['exit_code'] == 0
assert r['head'] == meta['candidate'] and r['tree'] == meta['tree']
assert r['cgroup_limit'] == 2147483648 and r['cpus'] == 2 and r['network'] == 'none'
assert not r['final_memory']['cgroup_memory_events']['oom_kill']
console = (c/'unittest-console.log').read_bytes()
match = re.search(rb'Ran (\d+) tests in [0-9.]+s\s+OK\s*$', console)
assert match and int(match[1]) == 4136
counts = Counter(json.loads(x)['event'] for x in (c/'tests.jsonl').read_text().splitlines())
assert counts['start'] == counts['stop'] == 4136
assert not any(counts[x] for x in ['error', 'failure', 'skip'])
trace = [json.loads(x) for x in (c/'canonical-trace.jsonl').read_text().splitlines()]
gates = [x for x in trace if x.get('event') == 'validation_child_completed']
assert len(gates) == 10 and all(x['return_code'] == 0 for x in gates)
assert any(x.get('event') == 'validator_final_summary' and x.get('gates') == 10 for x in trace)
manifest = json.loads((c/'manifest.json').read_text())
for x in manifest:
    payload = (c/x['name']).read_bytes()
    assert len(payload) == x['bytes'] and hashlib.sha256(payload).hexdigest() == x['sha256']
summary = dict(candidate=meta['candidate'], tree=meta['tree'], tests=4136,
    all_local_gates_passed=True, local_manifest_entries=len(manifest),
    console_sha256=hashlib.sha256(console).hexdigest(), kernel_peak=r['kernel_peak'],
    elapsed_seconds=r['elapsed_seconds'], cgroup_limit=r['cgroup_limit'])
(b/'local-verified.json').write_text(json.dumps(summary,indent=2)+'\n')
parts = b/'readable-console'
parts.mkdir(exist_ok=True)
chunks = []
current = bytearray()
for line in console.splitlines(keepends=True):
    if current and len(current)+len(line)>400000:
        chunks.append(bytes(current)); current.clear()
    current.extend(line)
if current: chunks.append(bytes(current))
for i,data in enumerate(chunks,1):
    (parts/f'unittest-console-{i:03d}.log').write_bytes(data)
assert b''.join((parts/f'unittest-console-{i:03d}.log').read_bytes() for i in range(1,len(chunks)+1)) == console
(parts/'SHA256SUMS').write_text(''.join(hashlib.sha256((parts/f'unittest-console-{i:03d}.log').read_bytes()).hexdigest()+f'  unittest-console-{i:03d}.log\n' for i in range(1,len(chunks)+1)))
pre = json.loads((b/'local-preflight/result.json').read_text())
assert pre['passed'] and pre['complete'] and pre['head'] == meta['candidate'] and pre['tree'] == meta['tree']
# Do not create a publishable recovery archive without the original raw log.
for name in ('result.json','raw.log','SHA256SUMS'):
    assert (b/'local-preflight'/name).is_file(), 'Missing original preflight evidence: '+name
assert (b/'local-preflight/raw.log').read_bytes() == (b/'local-preflight-console.log').read_bytes()
pre_sums = dict(line.split('  ',1)[::-1] for line in (b/'local-preflight/SHA256SUMS').read_text().splitlines())
assert set(pre_sums) == {'result.json','raw.log'}
for name,sha in pre_sums.items():
    assert hashlib.sha256((b/'local-preflight'/name).read_bytes()).hexdigest() == sha
files = {}
for directory,prefix in [('canonical','local-canonical'),('local-preflight','local-preflight'),
        ('browser-final','history-followthrough'),('readable-console','readable-console')]:
    for path in sorted((b/directory).rglob('*')):
        if path.is_file(): files[prefix+'/'+str(path.relative_to(b/directory))] = path
for name in ['SCOUT_HANDOFF.md','source.json','candidate-production.patch','local-verified.json',
        'focused-exact.log','local-preflight-console.log','commands.md','run-clean.py','run-constrained.py',
        'invocation.json','local-console.log','preservation.json','baseline.json','source-integrity.json',
        'production-before-release.json','package-final.py','package-prior-report.json','harness-preservation.json','environment-reconnection.json',
        'publisher-focused.log','publisher-lint-corrected.log','checkout-reuse.json',
        'ci-budget-focused.log','worker-tail-focused.log','superseded-source-decision.json','packaging-correction.json']:
    files[name] = b/name
archive = Path('/workspace/dtos-publisher-2231/.github/release-plans/2231-recovery.zip')
saved = b/'recovery-before-scheduling.zip'
if archive.exists() and not saved.exists(): archive.replace(saved)
pattern = re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,p in sorted(files.items()):
        if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:
            assert not pattern.search(p.read_bytes()), str(p)
        z.write(p,name)
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
assert archive.stat().st_size < 100*1024**2
print(json.dumps(summary))
print('Recovery bytes',archive.stat().st_size,'SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
