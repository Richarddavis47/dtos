"""Publish original diagnostic/cancelled records; explicitly not release proof."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
import zipfile

B = Path(__file__).resolve().parent
E = Path('/workspace/cache-sharing-handoff')
source = json.loads((B / 'source.json').read_text())
prefix = Path('.task-evidence/franchise-progress-2250/checkpoints') / (
    datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H%MZ-RECONCILING'))
T = E / prefix
assert not T.exists()
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=E)
T.mkdir(parents=True)
secret = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')


def write(name, raw):
    p = T / name
    assert not p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix not in {'.zip', '.png'}:
        assert not secret.search(raw), name
    p.write_bytes(raw)


def split(name):
    raw = (B / name).read_bytes()
    raw.decode('utf-8')
    destination = 'readable/' + name.replace('.', '-')
    rows = []
    offset = 0
    while offset < len(raw):
        end = min(offset + 60000, len(raw))
        while end < len(raw) and raw[end] & 0xc0 == 0x80:
            end -= 1
        part = raw[offset:end]
        part_name = f'part-{len(rows) + 1:03}.log'
        write(destination + '/' + part_name, part)
        rows.append(dict(name=part_name, bytes=len(part), sha256=hashlib.sha256(part).hexdigest()))
        offset = end
    assert b''.join((T / destination / row['name']).read_bytes() for row in rows) == raw
    write(destination + '/parts.json', (json.dumps(dict(source=name, bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(), parts=rows,
        scope='Original UTF8 bytes split only at codepoint boundaries; CR/LF preserved'), indent=2) + '\n').encode())
    write(destination + '/README.md', ('# Readable original parts\n\n' + name + '\n\n' +
        '\n'.join('- [' + row['name'] + '](' + row['name'] + ')' for row in rows) + '\n').encode())


for name in ['WORK_STATUS.json', 'NEXT_ACTIONS.md', 'source.json', 'candidate.patch',
             'source-transition-f40-to-b522.json', 'preservation.json',
             'contextual-diagnostic-reconciled.json', 'contextual-diagnostic-sealed.json',
             'contextual-diagnostic-f40-original.zip', 'profile-prefix-child-3.py',
             'profile-prefix-invocation.json', 'profile-prefix-3/diagnostic-prefix-result.json',
             'focused-ready.json', 'focused-exact/result.json', 'resource-native-guards.json',
             'canonical-invocation.json', 'input-relocation-reconciliation.json',
             'prior-focused-b522-unspawn-safe/HARNESS_FAILURE.json',
             'prior-source-f40/hosted-canonical-cancelled-reconciled.json',
             'prior-source-f40/hosted-outcome-at-source-transition.json',
             'prior-source-f40/hosted-originals/prior-canonical-f40-original.zip',
             'prior-source-f40/hosted-originals/prior-canonical-f40-original.zip.delivery.json']:
    path = B / name
    raw = path.read_bytes()
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            for member in archive.namelist():
                if Path(member).suffix in {'.json', '.jsonl', '.log', '.txt', '.py', '.md'}:
                    assert not secret.search(archive.read(member)), member
    write(name, raw)
for name in ['focused-exact/original-console.log',
             'prior-focused-b522-unspawn-safe/focused-exact/original-console.log',
             'prior-source-f40/hosted-canonical-cancelled-originals/unittest-console.log',
             'prior-source-f40/hosted-canonical-cancelled-originals/tests.jsonl']:
    split(name)
write('README.md', f'''# RECONCILING — not a release

PR339 final candidate `{source['candidate']}` / tree `{source['tree']}`.
Production remains v1.22.34/build2249. No merge/tag/draft/deployment.
Focused103 and three native2GiB protocols passed. Complete local and hosted
validation on this source are running, not passed. All gates remain mandatory.

Original failed-local evidence remains at the earlier immutable checkpoint:
https://github.com/Richarddavis47/dtos/tree/7efb96e7fca50246c9580ed3dde7f4bd7d5ed142/.task-evidence/franchise-progress-2250/checkpoints/2026-11-12T1744Z-HELD

This additive checkpoint preserves the completed diagnostic and cancelled old
hosted canonical ZIP, plus readable original logs and the external harness error.
The original542.77ms stall did not reproduce; prior-fixture cycles were measured,
not proven to be that stall's cause. Diagnostics never replace mandatory gates.
See WORK_STATUS/NEXT_ACTIONS for exact outcomes and the active original executor.
Private fixture databases/cache, actor envelopes, credentials and delivery URLs
are excluded. No live franchise recovery or owner acceptance is claimed.
'''.encode())
rows = [dict(path=str(p.relative_to(T)), bytes=p.stat().st_size,
             sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(T.rglob('*')) if p.is_file()]
write('manifest.json', (json.dumps(dict(source=source, status='RECONCILING_NOT_RELEASED', files=rows), indent=2) + '\n').encode())
write('SHA256SUMS', ''.join(row['sha256'] + '  ' + row['path'] + '\n' for row in rows).encode())
subprocess.run(['git', '-c', 'core.autocrlf=false', 'add', '-f', '--sparse', '--', str(prefix)], cwd=E, check=True)
for p in T.rglob('*'):
    if p.is_file():
        raw = p.read_bytes()
        oid = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        actual = subprocess.check_output(['git', 'rev-parse', ':' + str(p.relative_to(E))], cwd=E, text=True).strip()
        assert actual == oid
subprocess.run(['git', 'commit', '-m', 'Preserve2250 source reconciliation and cancelled originals'], cwd=E, check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=E, check=True)
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=E, text=True).strip()
branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=E, text=True).strip()
remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/' + branch], cwd=E, text=True).split()[0]
assert remote == commit
receipt = dict(source=source, commit=commit, prefix=str(prefix),
    url='https://github.com/Richarddavis47/dtos/tree/' + commit + '/' + str(prefix),
    manifest_sha256=hashlib.sha256((T / 'manifest.json').read_bytes()).hexdigest(),
    staged_blob_bytes_verified=True, remote_commit_verified=True, status='RECONCILING_NOT_RELEASED')
(B / 'reconciliation-checkpoint-published.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
