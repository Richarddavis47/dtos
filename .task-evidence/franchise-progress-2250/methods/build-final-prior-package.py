"""Additive prior-attempt seal; original earlier archive remains unchanged."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import zipfile

B = Path(__file__).resolve().parent
source = json.loads((B / 'source.json').read_text())
files = {}


def add(name, path):
    assert name not in files
    raw = path.read_bytes()
    if path.suffix in {'.json', '.jsonl', '.log', '.py', '.txt', '.md', '.patch'}:
        assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})', raw), name
    files[name] = raw


original = json.loads((B / 'prior-package-complete.json').read_text())
assert hashlib.sha256((B / 'prior-package.zip').read_bytes()).hexdigest() == original['sha256']
add('earlier-stage-original.zip', B / 'prior-package.zip')
with zipfile.ZipFile(B / 'prior-package.zip') as archive:
    assert archive.testzip() is None
    for name in archive.namelist():
        files['earlier-stage-readable/' + name] = archive.read(name)

for name in [
    'failed-local-f40-original.zip', 'failed-local-reconciled.json',
    'contextual-diagnostic-f40-original.zip', 'contextual-diagnostic-reconciled.json',
    'contextual-diagnostic-sealed.json', 'local-responsiveness-failure.json',
    'local-cancellation-invocation.json', 'profile-prefix-invocation.json',
    'profile-prefix-child-3.py', 'source-transition-f40-to-b522.json',
    'input-relocation-reconciliation.json', 'executor-transport-recovery.json',
    'reconciliation-checkpoint-published.json', 'cancelled-artifact-immutable-location.json',
    'publisher-controls-3-original.log',
    'publisher-ruff-3-original.log',
]:
    add(name, B / name)

# Public source-fixture logs only. Original private disposable databases/cache
# remain local and are never included. Native archives are preserved separately.
folders = {
    'failed-local-readable': B / 'prior-local-f40/local-canonical',
    'cancelled-hosted-readable': B / 'prior-source-f40/hosted-canonical-cancelled-originals',
    'failed-focused-harness': B / 'prior-focused-b522-unspawn-safe',
    'invalid-diagnostic-first': B / 'profile-prefix',
    'invalid-diagnostic-second': B / 'profile-prefix-2',
}
for prefix, root in folders.items():
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and (
            path.suffix in {'.json', '.jsonl', '.log', '.py', '.md', '.txt'}
            or path.name == 'SHA256SUMS'
        ):
            add(prefix + '/' + str(path.relative_to(root)), path)
for name in ['source.json', 'candidate.patch', 'preservation.json',
             'hosted-outcome-at-source-transition.json',
             'hosted-canonical-cancelled-reconciled.json', 'product-test-counts.json']:
    add('prior-source-f40/' + name, B / 'prior-source-f40' / name)

notes = '''# Earlier attempts — original outcomes remain distinct

The initial stage seal remains byte-for-byte in earlier-stage-original.zip.
Its statement that no application gate had failed applied only to that earlier
seal time. It does not describe later full-local or cancelled hosted validation.

The first f40 full local run failed the existing FOIS heartbeat assertion:
542.770149 ms against an unchanged 500 ms limit. It had no OOM/admission deferral.
Its already-failed remainder was deliberately interrupted. 1,840 stop events are
not a passing-test count: six gates passed, unit regression failed, and three
subsequent gates did not execute. The entire original failed archive, console,
events, memory, manifest and recorded cancellation are retained here.

The diagnostic replay ran the same 1,211 preceding methods and two real worker
operations. Both completed two records (114.12/78.62 ms heartbeat maxima).
An explicit collection between them found 940,075 unreachable objects and took
1.806 seconds. The original stall did not reproduce; its exact cause remains
unproven. The final fixture collects old garbage before creating/timing its own
50,000-player workload. GC stays enabled; admission, worker and 500 ms limit are
unchanged, with explicit two-record completion assertions added. Diagnostic
passes are never substituted for final full regression.

Two earlier diagnostic prototypes were unusable: the first failed before tests
on a nested-AST instrumentation lookup; the second was cancelled for extra held
TestCase references and missing discover-observer activation. The second owned
disposable container needed a stop after graceful interruption did not finish.
Neither establishes application cancellation/cleanup behavior. Original methods,
logs and limitations remain separate.

The f40 hosted canonical was cancelled by the new source head, with 3,828 starts
and 3,827 stops. Its result/trace/manifest were not finalized. All twelve other
required f40 jobs passed, but their results are not final b522-source evidence.
The cancelled original ZIP is retained separately at an immutable evidence Git
commit, with its API SHA256 and Actions artifact identity; original console/events are included here without alteration.

The first b522 supplemental 103-method focused run had one failure/five errors:
the earlier browser-only external runner lacked __main__ protection. A spawned
worker imported it, repeated root.mkdir(), raised FileExistsError and broke the
pool. This harness defect was corrected without application changes; originals
are retained and the corrected complete focused run is separate.

Read original publisher fixture failures and dirty-source development boundaries
in earlier-stage-readable/PRIOR_ATTEMPTS.md. No failed source/log is recreated.
Private fixture databases, raw cache contents, private API envelopes, credentials
and reusable delivery URLs are excluded. Finite cleanup is not leak-freedom proof.
'''
files['PRIOR_ATTEMPTS.md'] = notes.encode()
(B / 'PRIOR_ATTEMPTS.md').write_text(notes)
rows = [dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        for name, raw in sorted(files.items())]
files['prior-manifest.json'] = (json.dumps(dict(candidate=source['candidate'],
    tree=source['tree'], scope='prior-attempts-only', files=rows), indent=2) + '\n').encode()
destination = B / 'prior-package-final.zip'
assert not destination.exists()
with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, raw in sorted(files.items()):
        archive.writestr(name, raw)
with zipfile.ZipFile(destination) as archive:
    assert archive.testzip() is None
    for row in rows:
        raw = archive.read(row['name'])
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
assert destination.stat().st_size < 100_000_000
receipt = dict(source=source, file=destination.name, bytes=destination.stat().st_size,
    sha256=hashlib.sha256(destination.read_bytes()).hexdigest(), members=len(files),
    scope='prior-attempts-only', sealed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    previous_seal_preserved=original)
(B / 'prior-package-final-complete.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
