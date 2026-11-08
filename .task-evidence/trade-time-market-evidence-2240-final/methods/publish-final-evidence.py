"""Publish original evidence only after verified immutable release/deployment."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
b=Path('/workspace/2240-trade-time-market');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/trade-time-market-evidence-2240-final';out=repo/prefix
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());pub=json.loads((b/'published-publication.json').read_text());merged=json.loads((b/'merged-source.json').read_text());prod=json.loads((b/'production-readonly-smoke.json').read_text());release=json.loads((b/'publication-verified.json').read_text())['release']
assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['candidate']==host['candidate']==pub['candidate']==s['candidate'] and local['tree']==host['tree']==pub['tree']==merged['tree']==s['tree'];assert pub['immutable'] and not pub['draft'] and release['immutable'] and prod['production_ready']['deployment']['commit']==merged['merge_commit'];assert not out.exists() and not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
out.mkdir(parents=True);(out/'.gitattributes').write_text('* -text\n')
names=['source.json','baseline.json','candidate-production.patch','REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','local-verified.json','local-container-cleanup.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','focused-resource-verified.json','preservation-review.json','hosted-precanonical-artifacts-verified.json','precanonical-download-receipts.json','hosted-job-log-receipts.json','supplied-screen.json','feature.json','baseline-reproduction.json','publisher-source.json','publisher-final-tests.log','publisher-final-lint.log','publisher-final-compile.log','publisher-workflow-review.json','recovery-offline-verified.json','recovery-package.json','prior-package.json','invocation-final.json','live-access-limitation.json','prepared-publication.json','prepared-attachment-verification.json','published-publication.json','published-attachment-verification.json','merged-source.json','production-readonly-smoke.json','publisher-production-smoke.json','publication-verified.json','preparation-certificate.zip','publication-certificate.zip','preparation-certificate-metadata.json','publication-certificate-metadata.json']
for n in names:
 p=b/n;assert p.is_file(),n;shutil.copy2(p,out/n)
for n in ['publisher-frozen-plan-tests.log','publisher-frozen-plan-lint.log','publisher-ruff-install.log','publisher-tooling-reconciliation.json','render-deployed.json','render-normal-metrics.json','preparation-original-decoded.log','publication-original-decoded.log','canonical-final-original-decoded.log','publisher-workflow-review-prior-unnamed-step.log']:
 if (b/n).is_file():shutil.copy2(b/n,out/n)
# All original task-root logs, including failures/preliminary attempts, stay separate.
for p in b.glob('*.log'):
 if p.name != 'scratch-recovery-verified-original.log':shutil.copy2(p,out/p.name)
for folder in ['browser-final-source','phone-visibility','hosted-decoded-originals','hosted-readable-parts','readable-console','readable-root-logs']:
 shutil.copytree(b/folder,out/folder)
for folder in ['local-preflight','local-restoration-unused','local-resident-refresh']:
 for n in ['result.json','evidence/result.json','raw.log','SHA256SUMS','invocation.json']:
  p=b/folder/n
  if p.is_file():q=out/folder/n;q.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(p,q)
for folder,dest in [('canonical','local-canonical-readable'),('host-canonical-readable','host-canonical-readable')]:
 q=out/dest;q.mkdir()
 for n in ['result.json','manifest.json','SHA256SUMS','canonical.log','canonical-trace.jsonl','unittest-console.log','tests.jsonl','memory.jsonl']:
  shutil.copy2(b/folder/n,q/n)
 if folder=='host-canonical-readable':
  for p in sorted((b/folder).glob('console-*')):shutil.copy2(p,q/p.name)
methods=out/'methods';methods.mkdir()
for n in ['run-constrained.py','run-local-canonical.py','verify-local-canonical.py','verify-host-canonical.py','verify-focused-resource.py','run-local-resource.py','feature-probe.py','phone-visibility.py','build-final-artifact-queue.py','make-recovery.py','package-prior.py','review-publisher-workflow.py','verify-certificate.py','verify-recovery-offline.py','verify-production.py','publish-final-evidence.py','readable-root-logs.py','readable-host-logs.py']:
 shutil.copy2(b/n,methods/n)
with __import__('zipfile').ZipFile(b/'publication-certificate.zip') as z:
 for n in ['assets/VALIDATION.json','assets/evidence-manifest.json','assets/SHA256SUMS','assets/prior-attempts.json']:
  q=out/'immutable-attachment-metadata'/Path(n).name;q.parent.mkdir(exist_ok=True);q.write_bytes(z.read(n))
(out/'README.md').write_text(f'''# Trustworthy, readable trade-time Market evidence — completed release

DTOS v1.22.25 / build 2240 is published immutably and deployed. The existing completed-trade disclosure now selects the latest eligible compatible retained quote and displays each supported value with source, observation time and age. A newer incompatible or foreign-scope row no longer masks an older supported quote. Missing values remain specifically qualified, and partial packages preserve their individual supported values.

- PR: https://github.com/Richarddavis47/dtos/pull/329
- Immutable release: {release['html_url']}
- Validated candidate: `{s['candidate']}`; tree: `{s['tree']}`.
- Approved squash / deployed commit: `{merged['merge_commit']}`, exact validated tree.
- Local and hosted canonical: **4,290 tests each**, **all ten gates each**. All **13 hosted jobs** passed; Product recorded **803 executions**. Local manifest {local['local_manifest_entries']} entries; hosted {host['entries']}. Original payloads/checksums verified.

No package totals or seven-day cutoff are introduced. The owner's supplied bounded retained-reference screen supports individual evidence in10/26 Day Traders and3/11 Arkham sampled events, none of31 Granite samples. Codex did not reproduce that private observation. These counts do not establish full packages, historical league-format parity, exhaustive coverage or live quote acceptance. All numerical feature/browser controls use disposable source-shaped fixtures.

Read [REPORT.md](REPORT.md), [SCOUT_HANDOFF.md](SCOUT_HANDOFF.md) and [PRIOR_ATTEMPTS.md](PRIOR_ATTEMPTS.md). All failed/preliminary logs remain distinct. Full original regression consoles, per-test events, traces, memory records and manifest originals are directly readable. `readable-console`, `host-canonical-readable/console-*`, `hosted-readable-parts` and `readable-root-logs` contain <=60k-byte parts, verified to concatenate exactly. The immutable attachments retain full original ZIPs, screenshots and source-bound recovery evidence. Native Actions read back all23 attachments before and after publication; certificate and API checksums match.

Chromium320×432,375×667,390×844 and1280×900 controls cover keyboard, emulated touch, readable disclosure, no horizontal overflow and no extra disclosure requests. Separate scrolled viewport hit-tests verify that value/source/age can be read unobstructed above the unchanged fixed navigation. Physical Safari and comprehensive screen-reader acceptance remain unverified.

Authenticated live quote acceptance remains HELD because no connected owner browser or Render Shell executor is available to this session. Public production readiness/auth-boundary checks are distinct. No forced entry, sync, backfill, Trade search, FOIS rebuild, cache clear, restart, token workaround or preference/lineup mutation occurred. This diagnostic presentation release does not establish Granite recovery or an earlier503 cause. Use the bounded read-only Scout procedure and stop on deferral.

Original prior audit remains unchanged:
https://github.com/Richarddavis47/dtos/tree/c48d4a9fb96420c2aae397535d08b68dd1a461d9/.task-evidence/trade-time-market-coverage-2239

Use GitHub Raw/download for exact bytes. manifest.json and SHA256SUMS cover every delivered payload. A separate public readback receipt avoids a self-referential manifest.
''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(out.rglob('*')):
 if p.is_file():
  raw=p.read_bytes();assert not secret.search(raw),p;rows.append(dict(name=str(p.relative_to(out)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
(out/'manifest.json').write_text(json.dumps({'candidate':s['candidate'],'tree':s['tree'],'deployed_commit':merged['merge_commit'],'status':'Published/deployed; authenticated live acceptance held','files':rows},indent=2)+'\n');sha=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows)+sha+'  manifest.json\n');spec=b/'final-public-paths.nul';spec.write_bytes(b'\0'.join(str(p.relative_to(repo)).encode() for p in out.rglob('*') if p.is_file())+b'\0');subprocess.run(['git','add','--sparse','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Publish immutable trade-time Market evidence and original readable validation'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True);head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();r=dict(evidence_commit=head,prefix=prefix,manifest_sha256=sha,files=len(rows),url='https://github.com/Richarddavis47/dtos/tree/'+head+'/'+prefix);(b/'final-evidence-publication.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
