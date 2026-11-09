"""Publish original evidence only after verified immutable release/deployment."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
b=Path('/workspace/2242-trade-partner-history-link');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/trade-partner-history-link-2242-final';out=repo/prefix
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());pub=json.loads((b/'published-publication.json').read_text());merged=json.loads((b/'merged-source.json').read_text());prod=json.loads((b/'production-readonly-smoke.json').read_text());release=json.loads((b/'publication-verified.json').read_text())['release']
assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['candidate']==host['candidate']==pub['candidate']==s['candidate'] and local['tree']==host['tree']==pub['tree']==merged['tree']==s['tree'];assert pub['immutable'] and not pub['draft'] and release['immutable'] and prod['production_ready']['deployment']['commit']==merged['merge_commit'];assert not out.exists() and not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
out.mkdir(parents=True);(out/'.gitattributes').write_text('* -text\n')
names=['source.json','baseline.json','branch-cleanup.json','final-workspace-check.json','candidate-production.patch','REPORT.md','SCOUT_HANDOFF.md','SCOUT_DEPLOYED_ACCEPTANCE.md','PUBLICATION_NOTES.md','recovery-size-reconciliation.json','PRIOR_ATTEMPTS.md','local-verified.json','local-container-cleanup.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','public-welcome-test-counts.json','evidence-count-reconciliation.json','focused-resource-verified.json','preservation-review.json','resource-qualification.json','pr-metadata-tooling-note.json','hosted-precanonical-artifacts-verified.json','precanonical-download-receipts.json','hosted-job-log-receipts.json','retained-history-feature.json','hosted-partner-history-verified.json','focused-commands.json','render-baseline.json','scratch-recovery.json','scratch-identical-inputs.json','download-orchestration-note.json','publisher-source.json','publisher-frozen-plan-tests.log','publisher-frozen-plan-lint.log','publisher-frozen-plan-compile.log','publisher-workflow-review.json','recovery-offline-verified.json','recovery-package.json','prior-package.json','invocation-final.json','live-access-limitation.json','prepared-publication.json','prepared-attachment-verification.json','published-publication.json','published-attachment-verification.json','merged-source.json','production-readonly-smoke.json','publisher-production-smoke.json','publication-verified.json','preparation-certificate.zip','publication-certificate.zip','preparation-certificate-metadata.json','publication-certificate-metadata.json']
for n in names:
 p=b/n;assert p.is_file(),n;shutil.copy2(p,out/n)
for n in ['publisher-frozen-plan-tests.log','publisher-frozen-plan-lint.log','publisher-ruff-install.log','publisher-tooling-reconciliation.json','render-deployed.json','render-normal-metrics.json','preparation-original-decoded.log','publication-original-decoded.log','canonical-final-original-decoded.log','publisher-workflow-review-prior-unnamed-step.log']:
 if (b/n).is_file():shutil.copy2(b/n,out/n)
# All original task-root logs, including failures/preliminary attempts, stay separate.
for p in b.glob('*.log'):
 if p.name not in {'scratch-recovery-verified-original.log','final-evidence-publication-original.log','final-public-readback-original.log'}:shutil.copy2(p,out/p.name)
for folder in ['browser-final-source','history-browser-final-source','hosted-decoded-originals','hosted-readable-parts','readable-console','readable-root-logs']:
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
for n in ['run-constrained.py','run-local-canonical.py','verify-local-canonical.py','verify-host-canonical.py','verify-focused-resource.py','run-local-resource.py','retained-history-probe.py','build-final-artifact-queue.py','make-recovery.py','package-prior.py','review-publisher-workflow.py','verify-certificate.py','verify-recovery-offline.py','verify-production.py','publish-final-evidence.py','readable-root-logs.py','readable-host-logs.py']:
 shutil.copy2(b/n,methods/n)
with __import__('zipfile').ZipFile(b/'publication-certificate.zip') as z:
 for n in ['assets/VALIDATION.json','assets/evidence-manifest.json','assets/SHA256SUMS','assets/prior-attempts.json']:
  q=out/'immutable-attachment-metadata'/Path(n).name;q.parent.mkdir(exist_ok=True);q.write_bytes(z.read(n))
(out/'README.md').write_text(f"""# Trade partner history links — original release evidence

DTOS v1.22.27 / build 2242 is published immutably and deployed. Recommended Trades and Evaluate can open the exact other franchise’s existing descriptive completed-trade history and return through existing scoped navigation. The clicked recommendation returns as a retained preview, leaving the draft unchanged; Evaluate restores its current draft and assessment. Existing not-revalidated/reevaluation qualifications remain.

- PR: https://github.com/Richarddavis47/dtos/pull/331
- Immutable release: {release['html_url']}
- Validated candidate: `{s['candidate']}`; tree: `{s['tree']}`.
- Approved squash/deployed commit: `{merged['merge_commit']}`, exact validated application tree.
- Local and hosted canonical: **4,316 tests each, all ten gates each**. All **13 required hosted jobs** and **821 Product executions** passed. Local manifest: {local['local_manifest_entries']} entries; hosted: {host['entries']}; complete original checksums/payloads verified.

Read [REPORT.md](REPORT.md), [SCOUT_HANDOFF.md](SCOUT_HANDOFF.md) and [PRIOR_ATTEMPTS.md](PRIOR_ATTEMPTS.md). The complete patch, focused original logs, full original regression consoles, test events, gate traces, memory samples and manifests are directly readable. `readable-console`, `host-canonical-readable/console-*`, `hosted-readable-parts` and `readable-root-logs` contain <=60k-byte parts that concatenate exactly to originals. Immutable attachments retain the complete original workflow ZIPs, canonical records and source-pinned feature/resource evidence. Native Actions read all23 attachment bytes back before and after publication; certificate and API digests match.

Eight final-source focused tests plus existing retained-history controls verify safe identity resolution, recommendation-preview and evaluation-draft round trips, unknown history, and league-switch reauthorization. Four sizes (320×432,375×667,390×844,1280×900), keyboard/focus, touch emulation,44px targets, no overflow and no extra evaluation/search/provider acquisition during History/Back passed. See `browser-final-source/` for two actual four-row reports and16screenshots. The frozen native publisher independently verifies the matching hosted feature records. Physical iPhone/Safari remains unverified.

The October Day/Arkham retained replay under `history-browser-final-source/` and `retained-history-feature.json` verifies the unchanged descriptive destination. It is separate from the new disposable Trade packages and from live owner evidence. Unknown counts remain unknown. This link adds no new historical coverage, manager-intent/acceptance inference, Trade score, valuation, preference or source acquisition. Resource safeguards are unchanged.

Owner-browser authenticated live round trips remain **unverified**: the supported connector reported unavailable. Public readiness/static/authentication-boundary checks are distinct from private feature acceptance. No production entry/search/evaluation, forced sync, FOIS rebuild, cache clear, restart, credential workaround or user-data mutation was performed. Stop on capacity deferral; this release does not establish Granite recovery or spare production memory.

Use GitHub Raw/download for exact bytes. `manifest.json` and `SHA256SUMS` cover all delivered payloads. This first snapshot excludes its own publication/readback command outputs to avoid circular/incomplete self-logs; a small separate receipt preserves those originals and confirms the public bytes.
""")
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(out.rglob('*')):
 if p.is_file():
  raw=p.read_bytes();assert not secret.search(raw),p;rows.append(dict(name=str(p.relative_to(out)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
(out/'manifest.json').write_text(json.dumps({'candidate':s['candidate'],'tree':s['tree'],'deployed_commit':merged['merge_commit'],'status':'Published/deployed; authenticated live acceptance held','files':rows},indent=2)+'\n');sha=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows)+sha+'  manifest.json\n');spec=b/'final-public-paths.nul';spec.write_bytes(b'\0'.join(str(p.relative_to(repo)).encode() for p in out.rglob('*') if p.is_file())+b'\0');subprocess.run(['git','add','--sparse','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Publish Trade partner history links and original readable validation'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True);head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();r=dict(evidence_commit=head,prefix=prefix,manifest_sha256=sha,files=len(rows),url='https://github.com/Richarddavis47/dtos/tree/'+head+'/'+prefix);(b/'final-evidence-publication.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
