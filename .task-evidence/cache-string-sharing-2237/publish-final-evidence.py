"""Publish verified final receipts beside preserved original study/failed records."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, shutil, subprocess

b = Path('/workspace/2237-cache-duplication')
checkout = Path('/workspace/cache-sharing-handoff')
root = checkout / '.task-evidence/cache-string-sharing-2237'
source = json.loads((b/'source.json').read_text())
verified = json.loads((b/'publication-verified.json').read_text())
smoke = json.loads((b/'production-readonly-smoke.json').read_text())
merged = json.loads((b/'merged-source.json').read_text())
host = json.loads((b/'host-canonical-verified.json').read_text())
assert root.is_dir() and verified['tree'] == source['tree']
assert verified['release']['immutable'] and not verified['release']['draft']
assert smoke['production_ready']['deployment']['commit'] == merged['merge_commit']
assert smoke['production_ready']['version'] == '1.22.22' and smoke['production_ready']['build'] == 2237
assert host['all_gates_passed'] and host['tests'] == 4250

for folder, prefix in [('host-canonical-readable','host-canonical'),('hosted-originals','hosted-originals')]:
    shutil.copytree(b/folder,root/prefix,dirs_exist_ok=True)
names = ['REPORT.md','SCOUT_HANDOFF.md','LIVE_ACCEPTANCE_STATUS.json','LIVE_ACCEPTANCE_FINAL.json','commands.md',
 'host-canonical-verified.json','host-canonical-integrity.log','hosted-final-records.json',
 'canonical-artifact-metadata.json','package-final-report.json','fixture-locations.json',
 'recovery-offline-verified.json','recovery-offline-verification.log',
 'repository-final-sync.json','publisher-source.json','publisher-focused-final.log','publisher-lint-final.log','publisher-compilation.json',
 'preparation-run.json','preparation-certificate-metadata.json','preparation-certificate.zip',
 'prepared-publication.json','prepared-attachment-verification.json',
 'publication-run.json','publication-certificate-metadata.json','publication-certificate.zip',
 'published-publication.json','published-attachment-verification.json','merged-source.json',
 'merge-approved.py','merge-approved.log','preparation-certificate-verification.log','publication-certificate-verification.log','preparation-watch.log','publication-watch.log','production-readonly-smoke.log','production-readonly-smoke.json','publication-verified.json','publisher-production-smoke.json',
 'prior-readable-publication-verification.json','checkpoint-readable-verification.json',
 'staging-public-readback.json','readiness-during-host-retry.json','render-baseline-metadata.json','render-deployed-metadata.json',
 'publisher-sealed-validation.json','publisher-focused-sealed-plan.log','publisher-lint-sealed-plan.log','publisher-lint-sealed-host-unavailable.log','plan-finalization.log','draft-creation.log','host-watch-attempt2.log','packaging-precondition-note.json','hosted-records-capture.log','make-report.py','package-final.py','finalize-plan.py','verify-recovery-offline.py','verify-certificate.py',
 'verify-production.py','publish-final-evidence.py']
for name in names:
    assert (b/name).is_file(), name
    shutil.copy2(b/name, root/name)
shutil.copy2('/workspace/dtos-publisher-2237/.github/release-plans/2237-recovery.zip',root/'2237-recovery.zip')
shutil.copy2('/workspace/dtos-publisher-2237/.github/release-plans/2237.json',root/'release-plan.json')
receipt = dict(observed_at=datetime.now(timezone.utc).isoformat(),status='DEPLOYED / live Granite acceptance HELD',
 candidate=source['candidate'],tree=source['tree'],merge=merged['merge_commit'],
 publisher=json.loads((b/'publisher-source.json').read_text())['publisher'],
 version='1.22.22',build=2237,pr=326,release=verified['release']['html_url'],immutable=True,
 local_tests=4250,hosted_canonical_tests=4250,canonical_gates=10,hosted_jobs=12,product_executions=757,
 focused_tests=63,publisher_tests=49,local_manifest_entries=640,host_manifest_entries=host['entries'],
 live_granite_entry=False,independent_live_sleeper_actual_parity=False,
 live_boundary='No existing Render Shell/SSH executor or associated authenticated browser runtime in this session. Supplied Render-local identity200 is not reproduced; unchanged external401 was not retried.')
(root/'FINAL_STATUS.json').write_text(json.dumps(receipt,indent=2)+'\n')
lines=['# Readable original regression consoles','',
 'Both complete consoles are original, unedited test output. Numbered parts concatenate byte-for-byte; whole-console SHA256 values are in local-verified.json and host-canonical-verified.json. Earlier timed-out/failed attempts are separate, never passing full validation.','']
for folder,pattern in [('readable-console','*.log'),('host-canonical','console-*.log')]:
    lines += ['## '+folder,'','| Part | Bytes | SHA256 |','|---|---:|---|']
    for p in sorted((root/folder).glob(pattern)):
        lines.append(f'| [{p.name}]({folder}/{p.name}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
    lines.append('')
(root/'LOG_INDEX.md').write_text('\n'.join(lines)+'\n')
(root/'README.md').write_text(f'''# League restoration memory — final evidence

DTOS v1.22.22/build2237 is published immutably and production is ready on `{merged['merge_commit']}`. [PR326](https://github.com/Richarddavis47/dtos/pull/326) merged only after exact-source validation and native Actions attachment preparation. Candidate `{source['candidate']}` and merged source have identical tree `{source['tree']}`. The publisher is a tooling-only branch, never merged as application code.

Matched structural controls reduce the full restoration/publication kernel peak by about16–19MiB and retained memory by18–20MiB. They do not profile the private Granite payload or establish its exact demand. Decode time increases by roughly0.25seconds. The same cache bytes,16× admission basis,2GiB cap,FOIS/Trade reserves and all source/score contracts remain unchanged. Immutable strings share references within one read; mutable containers and all derived evidence remain independent and retained. No omitted representation is rebuilt behind a discounted admission basis.

[Final report](REPORT.md) · [exact patch](candidate-production.patch) · [source/protected hashes](source-integrity.json) · [final status](FINAL_STATUS.json) · [readable original full logs](LOG_INDEX.md) · [manifest](manifest.json) · [checksums](SHA256SUMS) · [Scout acceptance](SCOUT_HANDOFF.md) · [immutable release]({verified['release']['html_url']}).

Validation:63focused,4250local full regression and separately4250hosted full regression; ten canonical gates in each; twelve required hosted jobs;757Product executions;49scoped publisher tests. Canonical manifests contain640local and{host['entries']}hosted entries. Original ZIPs, source identities, per-test events, SHA256 checks and actual2GiB enforcement are retained. This does not claim physical iPhone/Safari testing or long-term leak freedom.

Authenticated Granite entry and independent live Sleeper actual-score parity remain HELD because this session lacks existing Render Shell/SSH and an associated signed-in browser runtime. A public readiness result or fixture parity is not live customer acceptance. Main Chat's Render-local token200 remains supplied evidence. The unchanged external401 was not retried. The Scout procedure uses one existing Render-local advisory preflight, then at most one normal guarded entry when fresh admission permits. No forced sync,cache clearing,restart,FOIS rebuild,Trade search or user-data mutation is authorized. A successful future entry alone does not establish recovery causality or earlier503cause.

The fixed historical checkpoint commit2fffaf5672202a27e155a4a9bdfeee62c9ff27b7 and checkpoint-status.json preserve the earlier HELD state. Original failed/canceled/timed-out attempts remain in2237-prior.zip,host-failed-attempt1 and the separately published prior-readable supplement. The first final-source hosted attempt timed out at4200seconds after4008completed tests; it is never counted as full regression. One identical-control fresh-runner recovery passed on the unchanged source. Missing earlier finals are not reconstructed.
''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
rows=[]
for p in sorted(root.rglob('*')):
    if not p.is_file() or p.name in {'manifest.json','SHA256SUMS'} and p.parent==root:continue
    assert p.stat().st_size < 100*1024**2,p
    data=p.read_bytes()
    if p.suffix in {'.json','.jsonl','.log','.md','.py','.patch','.txt','.html','.js'}:assert not secret.search(data),p
    rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=source['candidate'],tree=source['tree'],merge=merged['merge_commit'],status=receipt['status'],files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows)+hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()+'  manifest.json\n')
paths=[str(p.relative_to(checkout)) for p in root.rglob('*') if p.is_file()]
spec=b/'final-evidence-pathspec.nul';spec.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
subprocess.run(['git','add','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=checkout,check=True)
subprocess.run(['git','commit','-m','Publish build2237 final validation and immutable deployment receipts'],cwd=checkout,check=True)
subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=checkout,check=True)
print('Final evidence commit',subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip())
