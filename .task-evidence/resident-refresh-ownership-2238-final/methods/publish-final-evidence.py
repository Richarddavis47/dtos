"""Publish verified original task evidence after the guarded release completes."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,zipfile
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/resident-refresh-ownership-2238-final';out=repo/prefix
source=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());prod=json.loads((b/'production-readonly-smoke.json').read_text());pub=json.loads((b/'published-publication.json').read_text());merge=json.loads((b/'merged-source.json').read_text())
assert local['candidate']==host['candidate']==pub['candidate']==source['candidate'] and local['tree']==host['tree']==pub['tree']==merge['tree']==source['tree']
assert local['all_local_gates_passed'] and host['all_gates_passed'] and pub['immutable'] and not pub['draft'] and prod['production_ready']['deployment']['commit']==merge['merge_commit']
assert not out.exists();out.mkdir(parents=True);(out/'.gitattributes').write_text('* -text\n')
files=['source.json','candidate-production.patch','REPORT.md','OWNERSHIP.md','SCOUT_HANDOFF.md','measurement-source-association.json','final-app-byte-equivalence.json','focused-final-49-writable.log','workflow-final-49-lint.log','focused-and-resource-final49-verified.json','focused-resource-process-cleanup.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','product-final-original-decoded.log','resident-host-final-verified.json','publisher-source.json','prepared-publication.json','prepared-attachment-verification.json','published-publication.json','published-attachment-verification.json','merged-source.json','production-readonly-smoke.json','publication-verified.json','recovery-offline-verified.json','recovery-package.json','prior-package.json','PRIOR_ATTEMPTS.md','prior-0a4-public-readback.json','checkpoint-0a4-public-readback.json','production-retained-memory-samples.json','version-reservation-final49.json','publisher-tests-final49.log','publisher-lint-final49.log','publisher-compile-final49.log','invocation-final.json','local-container-enforcement.json','live-access-limitation.json','SEALED_PREPARATION_REPORT.md','preparation-certificate.zip','publication-certificate.zip','preparation-certificate-metadata.json','publication-certificate-metadata.json','preparation-original-decoded.log','publication-original-decoded.log']
for n in files:
 p=b/n;assert p.is_file(),n;shutil.copy2(p,out/n)
for n in ['render-deployed.json','render-normal-metrics.json']:
 if (b/n).is_file():shutil.copy2(b/n,out/n)
for n in ['global-owner-before-fix.log','global-owner-after-fix.log'] :shutil.copy2(b/n,out/n)
for pattern in ['memory-final-*.json','memory-final-*.log','memory-accounting-detail.json','global-memory-*.json','global-memory-*.log','global-fixture-metadata.json','baseline-global-evidence.py','baseline-periodic-refresh.py','baseline-ownership-reproduction.*']:
 for p in r.glob(pattern):
  if p.is_file():q=out/'matched-controls'/p.name;q.parent.mkdir(exist_ok=True);shutil.copy2(p,q)
for folder in ['resource-final-49','local-preflight-49','local-restoration-unused-49']:
 shutil.copytree(r/folder,out/folder)
shutil.copytree(b/'hosted-decoded-originals',out/'hosted-decoded-originals')
for name in ['retention_memory_acceptance.py','retention_memory_probe.py','retention_reproduction.py','run-constrained.py']:
 q=out/'methods'/name;q.parent.mkdir(exist_ok=True);shutil.copy2(r.parent/name,q)
shutil.copy2(r/'global-owner-memory.py',out/'methods/global-owner-memory.py')
for name in ['run-local-canonical.py','verify-local-canonical.py','verify-host-canonical.py','package-prior.py','make-recovery.py','verify-certificate.py','verify-recovery-offline.py','verify-production.py','publish-final-evidence.py'] :shutil.copy2(b/name,out/'methods'/name)
for folder,label,parts in [(b/'canonical','local-canonical-readable',b/'readable-console'),(b/'host-canonical-readable','host-canonical-readable',None)]:
 q=out/label;q.mkdir()
 for n in ['result.json','manifest.json','SHA256SUMS','canonical.log','canonical-trace.jsonl','unittest-console.log','tests.jsonl','memory.jsonl']:shutil.copy2(folder/n,q/n)
 if parts:shutil.copytree(parts,q/'console-parts')
 else:
  d=q/'console-parts';d.mkdir()
  for p in sorted(folder.glob('console-*.log')):shutil.copy2(p,d/p.name)
with zipfile.ZipFile(b/'publication-certificate.zip') as z:
 for n in ['assets/VALIDATION.json','assets/evidence-manifest.json','assets/SHA256SUMS','assets/prior-attempts.json']:
  q=out/'immutable-attachment-metadata'/Path(n).name;q.parent.mkdir(exist_ok=True);q.write_bytes(z.read(n))
release=json.loads((b/'publication-verified.json').read_text())['release']
(out/'README.md').write_text(f'''# Sleeping-maintenance ownership correction — completed release evidence

DTOS v1.22.23/build2238 is deployed and ready. The scoped lifecycle fix releases obsolete publication references held by sleeping maintenance; current contexts, legitimate readers, writers and persistent source evidence remain protected. This is not evidence of Granite recovery or the historical503cause.

- PR: https://github.com/Richarddavis47/dtos/pull/327
- Immutable release: {release['html_url']}
- Candidate: `{source['candidate']}`; validated tree: `{source['tree']}`.
- Normal squash merge / deployed commit: `{merge['merge_commit']}`; exact validated tree unchanged.
- Final local and hosted regression: {local['tests']} tests each, all ten gates each. All thirteen required hosted jobs pass. Product:757executions. Focused:123methods. Publisher guard suite:50methods. Original source-bound results and all manifests/checksums accompany the readable unedited consoles. Numbered parts concatenate to each original full console. Screenshots and complete original hosted archives are immutable release attachments.

Read [REPORT.md](REPORT.md), [SCOUT_HANDOFF.md](SCOUT_HANDOFF.md) and [PRIOR_ATTEMPTS.md](PRIOR_ATTEMPTS.md). Reported~55–56MiB settled savings are matched disposable measurements on their actual509/0a4sources with byte-identical application functions in final49; they are not relabeled49measurements or privateGranite measurements. Full restoration peaks are materially unchanged; no reserve/16xallowance/cap reduction. The two owners may reference the same graph; do not add their savings blindly. Active readers intentionally retain their source. Finite cleanup cycles do not establish long-term leak freedom.

The original progressing0a4hosted timeout remains FAILED, with six completed gates, interrupted regression and three unexecuted gates. Its78,533,715byte original ZIP/readable logs/checksums are preserved separately at:
https://github.com/Richarddavis47/dtos/tree/8591cdf8b0ef7cff4b706a375c2d105d777018d8/.task-evidence/resident-refresh-ownership-2238-prior-0a4
The final CI-only allowance70->75minutes keeps every assertion and resource control. Earlier failed, cancelled and incomplete attempts remain distinct; see the immutable Prior-attempts.zip and source receipts. Missing original launch receipts are explicitly disclosed, never reconstructed.

**Live Granite preflight, conditional entry and independent completed-week Sleeper actual-score parity remain HELD**: this session has Render management access but no attached authenticated Shell/SSH executor or connected owner browser. No external401retry, new credential, forced sync, private-cache decode, Trade search, cache clear, manual restart or saved-user-data mutation. MainChat's earlier localtoken200 is supplied evidence. The handoff gives one existing Render-local preflight and one conditional normal entry; stop on unknown/deferral. Fixtures, retained production logs and fresh public readiness are separately identified.

Download any file using GitHub's Raw/download control. manifest.json and SHA256SUMS cover every delivered payload. Native Actions independently read back all23release attachments before and after immutable publication; separate API digests/source checks agree. A public-byte readback receipt for this evidence commit is supplied separately, so it does not self-reference its own manifest.
''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(out.rglob('*')):
 if p.is_file() and p not in {out/'manifest.json',out/'SHA256SUMS'}:
  data=p.read_bytes();assert not secret.search(data),p;rows.append({'name':str(p.relative_to(out)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(out/'manifest.json').write_text(json.dumps({'candidate':source['candidate'],'tree':source['tree'],'deployed_commit':merge['merge_commit'],'status':'Published/deployed; liveGranite acceptance HELD','files':rows},indent=2)+'\n');sha=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in rows)+sha+'  manifest.json\n')
paths=[str(p.relative_to(repo)) for p in out.rglob('*') if p.is_file()];spec=b/'final-public-paths.nul';spec.write_bytes(b'\0'.join(x.encode() for x in paths)+b'\0');subprocess.run(['git','add','--sparse','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Publish exact-source sleeping-maintenance release evidence and original readable validation'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();receipt={'evidence_commit':head,'prefix':prefix,'manifest_sha256':sha,'files':len(rows),'url':'https://github.com/Richarddavis47/dtos/tree/'+head+'/'+prefix};(b/'final-evidence-publication.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
