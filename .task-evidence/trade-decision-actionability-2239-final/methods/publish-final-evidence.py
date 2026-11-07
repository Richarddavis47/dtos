"""Publish original evidence only after verified immutable release/deployment."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
b=Path('/workspace/2239-trade-actionability');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/trade-decision-actionability-2239-final';out=repo/prefix
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());pub=json.loads((b/'published-publication.json').read_text());merged=json.loads((b/'merged-source.json').read_text());prod=json.loads((b/'production-readonly-smoke.json').read_text());release=json.loads((b/'publication-verified.json').read_text())['release']
assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['candidate']==host['candidate']==pub['candidate']==s['candidate'] and local['tree']==host['tree']==pub['tree']==merged['tree']==s['tree'];assert pub['immutable'] and not pub['draft'] and release['immutable'] and prod['production_ready']['deployment']['commit']==merged['merge_commit'];assert not out.exists() and not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
out.mkdir(parents=True);(out/'.gitattributes').write_text('* -text\n')
names=['source.json','baseline.json','candidate-production.patch','REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','focused-resource-verified.json','preservation-review.json','hosted-precanonical-artifacts-verified.json','precanonical-download-receipts.json','hosted-job-log-receipts.json','renderer-recovery-focused.log','renderer-partial-regression.log','final-candidate-probe.log','final-decision-cases.log','final-phone-interaction.log','zero-result-original.log','final-focused-resource-integrity.log','fois-liveness-control-spawn-safe-original.log','fois-liveness-control.json','fois-liveness-source-boundary.json','publisher-source.json','publisher-final-tests.log','publisher-final-lint.log','publisher-final-compile.log','publisher-workflow-review.json','recovery-offline-verified.json','recovery-package.json','prior-package.json','checkpoint-publication.json','checkpoint-public-readback.json','prior-publication.json','prior-public-readback.json','invocation-final.json','live-access-limitation.json','prepared-publication.json','prepared-attachment-verification.json','published-publication.json','published-attachment-verification.json','merged-source.json','production-readonly-smoke.json','publisher-production-smoke.json','publication-verified.json','preparation-certificate.zip','publication-certificate.zip','preparation-certificate-metadata.json','publication-certificate-metadata.json']
for n in names:
 p=b/n;assert p.is_file(),n;shutil.copy2(p,out/n)
for n in ['publisher-frozen-plan-tests.log','publisher-frozen-plan-lint.log','publisher-ruff-install.log','publisher-tooling-reconciliation.json','render-deployed.json','render-normal-metrics.json','preparation-original-decoded.log','publication-original-decoded.log','canonical-final-original-decoded.log','publisher-workflow-review-prior-unnamed-step.log']:
 if (b/n).is_file():shutil.copy2(b/n,out/n)
for folder in ['phone','candidate','cases','zero-result','hosted-decoded-originals','hosted-readable-parts','readable-console']:
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
for n in ['run-constrained.py','run-local-canonical.py','verify-local-canonical.py','verify-host-canonical.py','verify-focused-resource.py','run-local-resource.py','candidate_probe.py','decision_case_probe.py','zero_result_probe.py','phone_interaction_probe.py','fois_liveness_control.py','build-final-artifact-queue.py','make-recovery.py','package-prior.py','review-publisher-workflow.py','verify-certificate.py','verify-recovery-offline.py','verify-production.py','publish-final-evidence.py']:
 shutil.copy2(b/n,methods/n)
with __import__('zipfile').ZipFile(b/'publication-certificate.zip') as z:
 for n in ['assets/VALIDATION.json','assets/evidence-manifest.json','assets/SHA256SUMS','assets/prior-attempts.json']:
  q=out/'immutable-attachment-metadata'/Path(n).name;q.parent.mkdir(exist_ok=True);q.write_bytes(z.read(n))
(out/'README.md').write_text(f'''# Trade decisions that are easier to act on — completed release evidence

DTOS v1.22.24 / build 2239 is deployed and ready. Recommendation cards and Evaluate lead with the recorded decision reason and next action. Preview appears after the exact package and main cost. Both teams' evidence remains available. Optional offers do not suppress a completed zero-qualified search diagnosis. Unsupported timing is not presented as urgency. No fantasy calculation, qualification threshold, saved setting or resource policy changed.

- PR: https://github.com/Richarddavis47/dtos/pull/328
- Immutable release: {release['html_url']}
- Validated candidate: `{s['candidate']}`; tree: `{s['tree']}`.
- Normal squash merge / deployed commit: `{merged['merge_commit']}`. Its tree matches validation exactly.
- Final local and hosted canonical: 4,271 tests each, all ten gates each. All thirteen hosted jobs passed; Product recorded 784 executions. Local manifest: {local['local_manifest_entries']} entries; hosted: {host['entries']} entries. Every original payload checksum was verified.

At 375 pixels, the same first fixture package's preview moved from 1,298 to 498 pixels below the card top. Longer evidence stays visible; total card height increased. Four viewport, keyboard, CDP touch, 44-pixel targets, 10.84:1 contrast and no-overflow controls passed. These are disposable Chromium controls, not physical Safari or live offers. Same-generation matched offers agree between recommendation and evaluation for Win Now, Retool and Rebuild. The 995/75 marginal gain remains rejected; unknown evidence remains unknown.

Read [REPORT.md](REPORT.md), [SCOUT_HANDOFF.md](SCOUT_HANDOFF.md) and [PRIOR_ATTEMPTS.md](PRIOR_ATTEMPTS.md). The original failed and cancelled source90 records remain separately downloadable at:
https://github.com/Richarddavis47/dtos/tree/b8a8b41527240db5da9f0e04dfebbb3f5d5343a4/.task-evidence/trade-decision-actionability-2239-prior90
The prior 548 ms FOIS heartbeat failure remains unexplained; the unchanged final full control passed. No 500 ms assertion or admission reserve was weakened. No cancelled or unexecuted scope counts as a pass.

Original local/hosted full regression consoles, traces, per-test events, memory records and manifests are directly readable here. Numbered <=60k-byte console parts concatenate exactly to each original. The `readable-console` folder contains local regression parts; `host-canonical-readable/console-*` contains hosted regression parts; `hosted-readable-parts` contains the other original job consoles. Complete original ZIPs, screenshots and source-bound recovery evidence are immutable release attachments. Native Actions read every attachment byte back before and after publication; certificate/API digests agree.

Authenticated live Trade acceptance is HELD because no connected owner browser or Render Shell executor is attached to this session. No production Trade search, sync, preference write, FOIS rebuild, private cache decode, restart or credential workaround occurred. The unchanged external401 was not retried. This release does not establish Granite recovery, the cause of an earlier503, or increased infrastructure capacity. Follow the bounded safe Scout procedure and stop on deferral.

Use GitHub Raw/download for exact files. manifest.json and SHA256SUMS cover every delivered byte. A separate public readback receipt follows to avoid a self-referential manifest.
''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(out.rglob('*')):
 if p.is_file():
  raw=p.read_bytes();assert not secret.search(raw),p;rows.append(dict(name=str(p.relative_to(out)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
(out/'manifest.json').write_text(json.dumps({'candidate':s['candidate'],'tree':s['tree'],'deployed_commit':merged['merge_commit'],'status':'Published/deployed; authenticated live acceptance held','files':rows},indent=2)+'\n');sha=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows)+sha+'  manifest.json\n');spec=b/'final-public-paths.nul';spec.write_bytes(b'\0'.join(str(p.relative_to(repo)).encode() for p in out.rglob('*') if p.is_file())+b'\0');subprocess.run(['git','add','--sparse','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Publish immutable Trade actionability release evidence and original readable validation'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True);head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();r=dict(evidence_commit=head,prefix=prefix,manifest_sha256=sha,files=len(rows),url='https://github.com/Richarddavis47/dtos/tree/'+head+'/'+prefix);(b/'final-evidence-publication.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
