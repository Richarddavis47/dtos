"""Seal exact-source passing evidence only after all original guards pass."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

base = Path('/workspace/2243-my-team-trade-need')
controller = Path('/workspace/dtos-publisher-2243')
source = json.loads((base / 'source.json').read_text())
local = json.loads((base / 'local-verified.json').read_text())
hosted = json.loads((base / 'host-canonical-verified.json').read_text())
focused = json.loads((base / 'focused-resource-verified.json').read_text())
assert local['candidate'] == hosted['candidate'] == focused['candidate'] == source['candidate']
assert local['tree'] == hosted['tree'] == focused['tree'] == source['tree']
assert local['tests'] == hosted['tests'] == 4330 and local['all_local_gates_passed'] and hosted['all_gates_passed']
assert focused['all_native_guards_passed'] and focused['team_need_handoff']['passed']
assert json.loads((base / 'product-test-counts.json').read_text())['total'] == 831
files = {}
for folder, prefix in [('canonical', 'local-canonical'), ('local-preflight', 'local-preflight'),
                       ('local-restoration-unused', 'local-restoration-unused'), ('local-resident-refresh', 'local-resident-refresh'),
                       ('hosted-decoded-originals', 'hosted-decoded-originals')]:
    for path in (base / folder).rglob('*'):
        if path.is_file() and 'inputs' not in path.relative_to(base / folder).parts:
            files[prefix + '/' + str(path.relative_to(base / folder))] = path
for path in (base / 'browser-final-source').iterdir():
    if path.is_file():
        files['partner-history/' + path.name] = path
for path in (base / 'browser-final-source/team-need').iterdir():
    if path.is_file():
        files['team-need/' + path.name] = path
for path in (base / 'position-filter-layout').iterdir():
    if path.is_file():
        files['position-filter-layout/' + path.name] = path
files['feature/browser.json'] = base / 'history-browser-final-source/browser.json'
files['feature/feature.json'] = base / 'retained-history-feature.json'
for path in (base / 'history-browser-final-source').glob('*.png'):
    files['feature/' + path.name] = path
required = ['REPORT.md', 'SCOUT_HANDOFF.md', 'PRIOR_ATTEMPTS.md', 'source.json', 'baseline.json', 'candidate-production.patch',
            'preservation-review.json', 'resource-qualification.json', 'local-verified.json', 'host-canonical-verified.json', 'hosted-final-records.json',
            'product-test-counts.json', 'public-welcome-test-counts.json', 'focused-resource-verified.json',
            'final-source-focused.log', 'busy-filter-correction-focused-original.log', 'retained-history-probe.log',
            'publisher-final-tests.log', 'publisher-final-lint.log', 'publisher-final-compile.log', 'publisher-workflow-review.json',
            'prior-package.json', 'invocation-final.json', 'live-access-limitation.json', 'local-container-cleanup.json',
            'immutable-static-assets-after.json', 'local-container-enforcement.json', 'local-hosted-manifest-reconciliation.json', 'hosted-job-log-receipts.json', 'hosted-artifacts-verified.json', 'focused-commands.json', 'source-remote-recheck.json']
for name in required:
    path = base / name
    assert path.is_file(), name
    files[name] = path
for name in ['run-constrained.py', 'run-local-canonical.py', 'verify-local-canonical.py', 'verify-host-canonical.py',
             'verify-focused-resource.py', 'run-local-resource.py', 'retained-history-probe.py', 'build-final-artifact-queue.py',
             'make-recovery.py', 'package-prior.py', 'readable-root-logs.py', 'readable-host-logs.py', 'capture-layout.py', 'capture-touch.py',
             'dispatch-guarded.py', 'verify-certificate.py', 'create-draft.py', 'finalize-plan.py', 'merge-approved.py',
             'verify-production.py', 'verify-final-publication.py', 'seal-validation-report.py']:
    files['methods/' + name] = base / name
target = controller / '.github/release-plans/2243-recovery.zip'
secret = re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, path in sorted(files.items()):
        raw = path.read_bytes()
        assert not secret.search(raw), name
        archive.writestr(name, raw)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
assert target.stat().st_size < 100 * 1024**2
receipt = dict(candidate=source['candidate'], tree=source['tree'], files=len(files), bytes=target.stat().st_size,
               sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
               readable_original_logs='Full raw consoles are preserved. UTF8-safe <=60k parts are separately published, not redundantly duplicated in this bounded Git recovery ZIP.')
(base / 'recovery-package.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
