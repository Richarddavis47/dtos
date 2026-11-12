"""Publish readable originals after gates; does not merge or publish a release."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

B = Path(__file__).resolve().parent
E = Path('/workspace/cache-sharing-handoff')
prefix = Path('.task-evidence/franchise-progress-2250')
T = E / prefix
s = json.loads((B / 'source.json').read_text())
assert json.loads((B / 'local-verified.json').read_text())['all_local_gates_passed']
assert json.loads((B / 'host-canonical-verified.json').read_text())['all_gates_passed']
assert json.loads((B / 'hosted-artifacts-verified.json').read_text())['passed']


def write(name, raw):
    path = T / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == raw, 'Preserve earlier published bytes: ' + name
    else:
        path.write_bytes(raw)


for name in ['publisher-controller.json', 'publisher-final-integrity.json',
             'publisher-final-integrity-original.log', 'publisher-final-controls-original.log',
             'publisher-final-ruff-original.log', 'publisher-final-format-original.log',
             'final-release-plan.json', 'publisher-prepare-started.json',
             'hosted-checkout-identities-initial12.json', 'capture-extraction-initial.json']:
    write('publication/' + name, (B / name).read_bytes())
write('publication/methods/' + Path(__file__).name, Path(__file__).read_bytes())
text = f'''# Franchise Progress — verified source and readable original evidence

Candidate `{s['candidate']}`; validated tree `{s['tree']}`.
Baseline `{s['baseline']}` / v1.22.34 build2249. PR339 targets v{s['version']}
build{s['build']}. This snapshot precedes merge/publication. Later actual release
and deployment identities belong in the separately issued RELEASE_OUTCOME.md.
No authenticated owner live acceptance or physical iPhone/Safari is claimed.

- [Complete Scout acceptance prompt](SCOUT_HANDOFF.md)
- [Exact patch against production](candidate.patch)
- [Source identity](source.json) and [preserved application modules](preservation.json)
- [Local4435/allten gates](local-verified.json), [hosted4435/allten](host-canonical-verified.json)
- [Thirteen hosted job records](hosted-final-records.json) and [checkout tree identities](hosted-checkout-identities.json)
- [Fifteen verified original artifacts](hosted-artifacts-verified.json)
- [Focused103](focused-ready.json), [Product932](product-test-counts.json)
- [Local original console — readable parts](local-canonical-unittest-console-log/README.md)
- [Hosted original console — readable parts](hosted-canonical-unittest-console-log/README.md)
- [Local original test events](local-canonical-tests-jsonl/README.md)
- [Hosted original test events](hosted-canonical-tests-jsonl/README.md)
- [FOIS fixture review and attribution clarification](FOIS_FIXTURE_REVIEW.md)
- [All earlier attempt distinctions](PRIOR_ATTEMPTS.md)
- [Local resource limits/sampling](local-resource-measurements.json) and [hosted peak](hosted-resource-measurements.json)
- [Actual successful-container cleanup](local-container-cleanup.json)
- [Retained-source movement controls](retained-history-feature.json)

The original full-local run passed in112.60minutes; it was not restarted in this
continuation. Both final full runs reached the2GiB kernel cap with zeroOOM/oomkill.
The local observer's10000sample bound left1261.77seconds without periodic samples;
kernel enforcement/final counters remained authoritative. Finite controls do not
establish long-term leak freedom. The original542.77ms failure's cause is unproven.

Original consoles/events/memory are split at UTF8 boundaries into60KB parts, with
whole/part SHA256 and CR/LF preserved. Concatenation reproduces original bytes.
Tool-decoded job logs are labelled as such, not original HTTP wire bytes. Private
cache/database inputs, token values, reusable delivery URLs and private API actor
envelopes are excluded. Fixtures/replay/public deployment metadata/owner live
observations must remain separate. Missing history is never no activity.
'''
write('README.md', text.encode())
token = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')
rows = []
for path in sorted(T.rglob('*')):
    if not path.is_file():
        continue
    assert not path.is_symlink()
    raw = path.read_bytes()
    if path.suffix in {'.json', '.jsonl', '.log', '.md', '.txt', '.py', '.patch'}:
        assert not token.search(raw), str(path)
    rows.append(dict(path=str(path.relative_to(T)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
write('manifest-prepublication.json', (json.dumps(dict(source=s,
    at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='ALL_APPLICATION_GATES_VERIFIED_RELEASE_PREPARING', files=rows), indent=2) + '\n').encode())
write('SHA256SUMS-prepublication', ''.join(row['sha256'] + '  ' + row['path'] + '\n' for row in rows).encode())
subprocess.run(['git', '-c', 'core.autocrlf=false', 'add', '-f', '--sparse', '--', str(prefix)], cwd=E, check=True)
index = {}
for entry in subprocess.check_output(['git', 'ls-files', '-s', '-z', '--', str(prefix)], cwd=E).split(b'\0'):
    if entry:
        info, path = entry.split(b'\t')
        index[path.decode()] = info.split()[1].decode()
for path in T.rglob('*'):
    if path.is_file():
        raw = path.read_bytes()
        assert index[str(path.relative_to(E))] == hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
subprocess.run(['git', 'commit', '-m', 'Publish verified2250 original logs and prepublication source evidence'], cwd=E, check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=E, check=True)
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=E, text=True).strip()
branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=E, text=True).strip()
assert subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/' + branch], cwd=E, text=True).split()[0] == commit
receipt = dict(source=s, commit=commit, prefix=str(prefix),
    url='https://github.com/Richarddavis47/dtos/tree/' + commit + '/' + str(prefix),
    manifest_sha256=hashlib.sha256((T / 'manifest-prepublication.json').read_bytes()).hexdigest(),
    staged_blob_bytes_verified=True, remote_commit_verified=True,
    scope='Complete application validation/source originals accessible; release/deployment receipt remains separate')
(B / 'prepublication-evidence-published.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
