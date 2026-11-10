"""Publish checksum-verifiable evidence, independently of release success."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

base = Path('/workspace/2243-my-team-trade-need')
repo = Path('/workspace/cache-sharing-handoff')
prefix = '.task-evidence/my-team-trade-need-2243-final'
target = repo / prefix
source = json.loads((base / 'source.json').read_text())
local = json.loads((base / 'local-verified.json').read_text())
hosted = json.loads((base / 'host-canonical-verified.json').read_text())
status = json.loads((base / 'completion-status.json').read_text())
assert local['all_local_gates_passed'] and hosted['all_gates_passed']
assert local['candidate'] == hosted['candidate'] == status['candidate'] == source['candidate']
assert local['tree'] == hosted['tree'] == status['tree'] == source['tree']
assert not target.exists()
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip()
target.mkdir(parents=True)
(target / '.gitattributes').write_text('* -text\n')
required = ['REPORT.md', 'SCOUT_HANDOFF.md', 'PRIOR_ATTEMPTS.md', 'source.json', 'baseline.json', 'candidate-production.patch',
            'completion-status.json', 'final-workspace-check.json', 'preservation-review.json', 'resource-qualification.json', 'focused-resource-verified.json', 'local-verified.json',
            'host-canonical-verified.json', 'hosted-final-records.json',
            'artifact-download-queue.json', 'hosted-artifacts-verified.json', 'local-hosted-manifest-reconciliation.json', 'product-test-counts.json', 'public-welcome-test-counts.json',
            'hosted-job-log-receipts.json', 'local-container-cleanup.json', 'local-container-enforcement.json', 'immutable-static-assets-after.json',
            'invocation-final.json', 'publisher-workflow-review.json', 'prior-package.json', 'local-manifest-population-reconciliation.json', 'production-baseline-final-smoke.json', 'authorization-boundary.json', 'resumed-cli-auth-status.json', 'resumed-cli-auth-unsupported-flag-original.json',
            'live-access-limitation.json', 'retained-history-feature.json', 'focused-commands.json', 'source-remote-recheck.json', 'RELEASE_RESUME.md']
optional = ['recovery-package.json', 'publisher-source.json', 'prepared-publication.json', 'published-publication.json', 'native-hosted-final-records.json',
            'merged-source.json', 'production-readonly-smoke.json', 'publication-verified.json', 'release-hold.json', 'publisher-reviewed-tooling.zip', 'publisher-reviewed-tooling.json', 'PRIOR_ORIGINALS_INDEX.json', 'prior-originals-publication.json', 'prior-originals-readback.json', 'canonical-attempt1-inner-integrity.json', 'canonical-attempt1-matched-timing.json', 'recovery-offline-verified.json', 'final-attachment-readback.json']
optional += ['preparation-certificate.zip', 'preparation-certificate-metadata.json', 'prepared-attachment-verification.json',
             'publication-certificate.zip', 'publication-certificate-metadata.json', 'published-attachment-verification.json',
             'preparation-run.json', 'publication-run.json', 'preparation-dispatch-request.json', 'publication-dispatch-request.json',
             'publication-dispatch-attempt1-request.json', 'publication-dispatch-recovery.json',
             'publication-dispatch-502-run-lookup.json', 'publication-dispatch-502-followup-run-lookup.json',
             'publisher-production-smoke.json', 'pr-final-review-rest-result.json', 'REPORT_VALIDATION_SEALED.md', 'SCOUT_VALIDATION_SEALED.md']
for name in required + optional:
    path = base / name
    if name in required:
        assert path.is_file(), name
    if path.is_file():
        shutil.copy2(path, target / name)
for path in base.glob('*.log'):
    if path.name not in {'final-evidence-publication-original.log', 'final-public-readback-original.log', 'final-readback-publication-original.log'}:
        shutil.copy2(path, target / path.name)
for folder in ['browser-final-source', 'history-browser-final-source', 'position-filter-layout', 'hosted-decoded-originals',
               'hosted-readable-parts', 'readable-console', 'readable-root-logs', 'prior-hosted-decoded-originals']:
    shutil.copytree(base / folder, target / folder)
for folder in ['local-preflight', 'local-restoration-unused', 'local-resident-refresh']:
    for name in ['result.json', 'evidence/result.json', 'raw.log', 'SHA256SUMS', 'invocation.json']:
        path = base / folder / name
        if path.is_file():
            out = target / folder / name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
for folder, dest in [('canonical', 'local-canonical-readable'), ('host-canonical-readable', 'host-canonical-readable')]:
    out = target / dest
    out.mkdir()
    for name in ['result.json', 'manifest.json', 'SHA256SUMS', 'canonical.log', 'canonical-trace.jsonl', 'unittest-console.log', 'tests.jsonl', 'memory.jsonl']:
        shutil.copy2(base / folder / name, out / name)
    if folder == 'host-canonical-readable':
        for path in (base / folder).glob('console-*'):
            shutil.copy2(path, out / path.name)
methods = target / 'methods'
methods.mkdir()
for name in ['run-constrained.py', 'run-local-canonical.py', 'verify-local-canonical.py', 'verify-host-canonical.py',
             'verify-focused-resource.py', 'run-local-resource.py', 'retained-history-probe.py', 'build-final-artifact-queue.py',
             'verify-native-originals.py', 'make-recovery.py', 'package-prior.py', 'review-publisher-workflow.py',
             'readable-root-logs.py', 'readable-host-logs.py', 'capture-layout.py', 'capture-touch.py', 'publish-evidence.py',
             'dispatch-guarded.py', 'verify-certificate.py', 'create-draft.py', 'finalize-plan.py', 'merge-approved.py',
             'verify-production.py', 'verify-final-publication.py', 'seal-validation-report.py', 'publish-readback.py']:
    shutil.copy2(base / name, methods / name)
prior = Path('/workspace/dtos-publisher-2243/.github/release-plans/2243-prior.zip')
assert hashlib.sha256(prior.read_bytes()).hexdigest() == json.loads((base / 'prior-package.json').read_text())['sha256']
shutil.copy2(prior, target / 'Prior-attempts.zip')
(target / 'README.md').write_text(
    '# My Team roster need → Recommended Trades\n\n' +
    'Status: **' + status['status'] + '**. Read [REPORT.md](REPORT.md), [completion-status.json](completion-status.json) and [SCOUT_HANDOFF.md](SCOUT_HANDOFF.md) before inferring publication or deployment.\n\n' +
    'PR: https://github.com/Richarddavis47/dtos/pull/332\n\n' +
    'Exact candidate `' + source['candidate'] + '`, tree `' + source['tree'] + '`. Production baseline v1.22.27/build2242.\n\n' +
    'The full patch, original focused/full/hosted consoles, gate traces, test events, memory measurements and manifest receipts are accessible here. Readable console folders contain ordered UTF8-safe ≤60k-byte parts; INDEX/checksum records prove exact recombination. Prior failures/cancellations are separate, including original hosted Product errors and the corrected inaccurate prior-success note. `Prior-attempts.zip` preserves the original earlier bytes and its own manifest.\n\n' +
    'All new feature controls are source-bound disposable authenticated fixtures. The unchanged retained-history replay is separate. No authenticated live owner handoff or physical iPhone/Safari acceptance is claimed. No production search, sync, FOIS rebuild or user-data mutation occurred. This handoff does not establish Granite recovery or available production memory.\n\n' +
    'Use Raw/download for exact bytes. manifest.json and SHA256SUMS cover every payload. Completed publication/readback command outputs are excluded from this first snapshot to avoid circular self-logs; a separate receipt records transport integrity. Independent Scout acceptance remains separate.\n')
secret = re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
rows = []
for path in sorted(target.rglob('*')):
    if path.is_file():
        raw = path.read_bytes()
        assert not secret.search(raw), path
        assert len(raw) < 100 * 1024**2
        rows.append(dict(name=str(path.relative_to(target)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
manifest = dict(candidate=source['candidate'], tree=source['tree'], deployed_commit=status.get('deployed_commit'), status=status['status'], files=rows)
(target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
digest = hashlib.sha256((target / 'manifest.json').read_bytes()).hexdigest()
(target / 'SHA256SUMS').write_text(''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows) + digest + '  manifest.json\n')
spec = base / 'final-public-paths.nul'
spec.write_bytes(b'\0'.join(str(path.relative_to(repo)).encode() for path in target.rglob('*') if path.is_file()) + b'\0')
subprocess.run(['git', 'add', '--sparse', '-f', '--pathspec-from-file=' + str(spec), '--pathspec-file-nul'], cwd=repo, check=True)
subprocess.run(['git', 'commit', '-m', 'Publish My Team need handoff source and original validation evidence'], cwd=repo, check=True)
subprocess.run(['git', 'push', 'origin', 'evidence/cache-string-sharing-2237'], cwd=repo, check=True)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
receipt = dict(evidence_commit=head, prefix=prefix, manifest_sha256=digest, files=len(rows), url='https://github.com/Richarddavis47/dtos/tree/' + head + '/' + prefix)
(base / 'final-evidence-publication.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
