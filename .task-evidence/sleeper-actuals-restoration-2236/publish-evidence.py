"""Seal readable original evidence only after verified immutable publication."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2236-actuals-restoration');checkout=Path('/workspace/actuals-handoff');root=checkout/'.task-evidence/sleeper-actuals-restoration-2236'
m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree'] and local['tests']==host['tests']==4241
assert pub['release']['immutable'] and not pub['release']['draft'] and len(pub['release']['assets'])==22 and smoke['production_ready']['deployment']['commit']==merged['merge_commit']
assert not root.exists();root.mkdir(parents=True)
(root/'.gitattributes').write_text('* -text\n')
required=['REPORT.md','SCOUT_HANDOFF.md','source.json','source-integrity.json','candidate-production.patch','production-baseline-readiness.json','version-availability.json','pre-release-baseline-check.json','before-rendered.json','before-rendered.log','after-rendered.json','after-rendered.log','source-to-screen.py','restoration_fixture.py','read-boundary.json','read-boundary.log','verify-read-boundary.py','focused-exact.log','focused-coverage-index.json','cancellation-started-exact.log','worker-focused-source.json','cancellation-fixture-reconciliation.json','native-resource-final.log','commands.md','run-clean-final.py','run-constrained.py','invocation-final.json','revised-checkout.log','canonical-final-console.log','LIVE_ACCEPTANCE_STATUS.json','local-verified.json','host-canonical-verified.json','resource-verified.json','lifecycle-verified.json','product-test-counts.json','product-jobs.json','hosted-final-records.json','artifact-download-receipts.jsonl','scratch-reclamation.json','post-validation-source-clean.json','publisher-source.json','publisher-focused-final.log','publisher-finalized-plan-tests.log','publisher-lint-final.log','publisher-compilation.log','recovery-offline-verified.json','recovery-offline-integrity.log','local-canonical-integrity.log','host-canonical-integrity.log','product-artifact-integrity-final.log','lifecycle-artifact-integrity.log','package-final.py','package-final.log','package-prior.py','package-prior-report.json','package-prior.log','finalize-plan.py','finalize-plan.log','make-report.py','verify-local-canonical.py','verify-host-canonical.py','verify-product-artifacts.py','verify-lifecycle.py','verify-recovery-offline.py','verify-certificate.py','verify-production.py','verify-readable-publication.py','publish-evidence.py','draft-created.json','preparation-run.json','publication-run.json','prepared-publication.json','published-publication.json','prepared-attachment-verification.json','published-attachment-verification.json','publisher-production-smoke.json','merged-source.json','publication-verified.json','production-readonly-smoke.json','render-deployed.json','published-raw-joblogs-verified.json','published-raw-job-logs.zip']
for name in required:
 assert (b/name).is_file(),name
 shutil.copyfile(b/name,root/name)
for name in ['local-preflight','local-restoration-unused','native-resource-final','readable-console']:
 shutil.copytree(b/name,root/name)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 d=root/label;d.mkdir()
 for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copyfile(source/name,d/name)
for name in ['2236-recovery.zip','2236-prior.zip','2236.json']:shutil.copyfile(Path('/workspace/dtos-publisher-2236/.github/release-plans')/name,root/name)
with zipfile.ZipFile(root/'2236-prior.zip') as z:
 assert z.testzip() is None
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name
  if Path(name).suffix not in {'.log','.json','.jsonl','.md','.txt','.py','.patch','.html'} and Path(name).name!='SHA256SUMS':continue
  dest=root/'prior-originals'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
resource=root/'hosted-resource';resource.mkdir()
for a in json.loads((b/'product-artifact-metadata.json').read_text())['artifacts']+json.loads((b/'lifecycle-artifact-metadata.json').read_text())['artifacts']:
 with zipfile.ZipFile(b/'hosted-originals'/(a['name']+'.zip')) as z:
  for member in ['browser.json','result.json','summary.json','evidence/result.json']:
   if member in z.namelist():(resource/(a['name']+'-'+member.replace('/','-'))).write_bytes(z.read(member))
with zipfile.ZipFile(b/'published-raw-job-logs.zip') as z:
 assert z.testzip() is None
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name
  dest=root/'original-product-and-prior-job-logs'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
groups=json.loads((b/'hosted-final-records.json').read_text());old=json.loads((b/'prior-attempts/e10f-hosted-before-superseding.json').read_text())
for g in old:groups.append({'run':g['run'],'jobs':g['jobs']['jobs']})
index_rows=[]
for log in (root/'original-product-and-prior-job-logs').glob('*.log'):
 matches=[dict(job=j['id'],name=j['name'],run=g['run']['id'],source=g['run']['head_sha'],conclusion=j['conclusion'],final_candidate=g['run']['head_sha']==m['candidate'],path=str(log.relative_to(root))) for g in groups for j in g['jobs'] if j['id']==int(log.stem)]
 # A canceled job's pre-cancellation metadata is superseded by the retained final job record.
 if int(log.stem)==128059968698:
  final=next(j for j in json.loads((b/'prior-attempts/e10f-cancelled-canonical-jobs.json').read_text())['jobs'] if j['id']==int(log.stem))
  for x in matches:x['conclusion']=final['conclusion']
 assert len(matches)==1,log.name
 index_rows+=matches
(root/'original-hosted-job-index.json').write_text(json.dumps(index_rows,indent=2)+'\n')
def split(source,dest,prefix):
 data=source.read_bytes();parts=[];start=0
 while start<len(data):
  end=min(start+60000,len(data))
  while end<len(data) and data[end]&0xc0==0x80:end-=1
  assert end>start;parts.append(data[start:end]);start=end
 assert b''.join(parts)==data and all(len(p)<=60000 for p in parts)
 dest.mkdir(exist_ok=True)
 for i,part in enumerate(parts,1):(dest/f'{prefix}-{i:03d}.log').write_bytes(part)
 (dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(part).hexdigest()+f'  {prefix}-{i:03d}.log\n' for i,part in enumerate(parts,1)))
split(b/'host-canonical-readable/unittest-console.log',root/'readable-host-console','host-console')
for group in ['original-product-and-prior-job-logs','prior-originals']:
 for log in (root/group).rglob('*.log'):
  if log.stat().st_size>60000:
   label=hashlib.sha256(str(log.relative_to(root)).encode()).hexdigest()[:12];split(log,root/('readable-original-'+label),'original-'+label)
index=['# Readable original validation evidence','','Numbered parts concatenate byte-for-byte to the original. Original canonical and native Actions job bytes remain separate from connector-decoded count summaries. Failed, canceled and superseded attempts are not final acceptance.','']
for folder in sorted([root/'readable-console',root/'readable-host-console',*root.glob('readable-original-*')]):
 index+=['## '+folder.name,'','| Download | Bytes | SHA256 |','|---|---:|---|']
 for p in sorted(folder.glob('*.log')):index.append(f'| [{p.name}]({p.relative_to(root)}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
 index.append('')
index+=['[Full local console](original-local-canonical/unittest-console.log?raw=1) · [Full hosted console](original-host-canonical/unittest-console.log?raw=1) · [Raw job identity index](original-hosted-job-index.json) · [Prior original evidence](prior-originals)']
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
(root/'README.md').write_text(f'''# Sleeper actual-results restoration — v1.22.21 / build 2236

Released through [PR325](https://github.com/Richarddavis47/dtos/pull/325) and the [immutable release]({pub['release']['html_url']}). Production is ready on `{merged['merge_commit']}`. Exact validated candidate `{m['candidate']}`, application tree `{m['tree']}`. The normal expected-head squash merge preserved that tree. Native Actions publication independently read back every attachment; separate API/certificate digest checks passed.

Connected cache restoration omitted the native actual-results binding performed by default startup. The same frozen disposable source rows reproduce available18points on startup but unavailable actuals on the old connected path. Both paths now admit the same retained18points and generation before publication. Fresh preparation uses the same binding boundary. No fantasy scores are reconstructed, no provider is fetched, and missing/conflicting/incompatible evidence stays missing. This is a confirmed generic restoration defect, not proof of what was retained in the private live Granite cache.

**Live Granite actual-score parity remains HELD/unverified in this session.** Render management provides no Shell execution, the approved browser js runtime is not exposed, and no VPN/TCP grant is configured. Main Chat's prior Render-local token200 is supplied evidence; the unchanged external401 was not retried. [Exact existing Render-local procedure and complete Scout prompt](SCOUT_HANDOFF.md) permit one normal guarded entry only when fresh capacity evidence supports it, then comparison of a genuinely supported completed native player-week. No forced sync, Trade search, FOIS rebuild, cache clear, manual restart, credential export, settings or infrastructure mutation occurred. Projection21.00 or historic26.56 is not live parity.

| Evidence | Final result |
|---|---|
| Focused exact-source controls |71 passed|
| Actual worker cancellation/timeout controls |5 passed|
| Full local Python3.14.3 |4,241 passed; all ten gates passed|
| Original hosted canonical |4,241 passed; all ten gates passed|
| Required hosted jobs |12of12passed|
| Product executions |757 passed|
| Publisher controls |46 passed|
| Canonical manifest entries |{local['local_manifest_entries']}local / {host['entries']}hosted|
| Immutable attachments |22 verified by native byte readback and independent API digest checks|

[Report](REPORT.md) · [complete patch](candidate-production.patch) · [source/file hashes](source-integrity.json) · [original workflow records](hosted-final-records.json) · [original full logs and <=60,000-byte readable parts](LOG_INDEX.md) · [checksums](SHA256SUMS) · [manifest](manifest.json).

Both full canonical runs enforce2,147,483,648bytes/no swap,2CPUs,offline/non-root execution. Lifetime peaks include deliberate unsafe-pressure controls and are not normal restoration demand. The unchanged initial8GiB scratch prerequisite and canonical timeout remain. The separate native2GiB acceptance uses12teams/10,788synthetic catalog identities,2,592native observations, explicit zero/-2.125 parity, compatible generations, actual restoration, unsafe deferral, explicit recovery, FOIS reserve protection, worker exit and scratch cleanup. This is not a private Granite payload profile; matching serialized size cannot establish equivalent demand. The old sealed study archive is reused unchanged, not rerun or upgraded fromPARTIAL.

The2GiB cap,16× allowance, FOIS768MiB and Trade256+128MiB policies are unchanged. Scoring, forward projections, submitted/analytical lineups, Neutral/Custom formulas, exact picks, saved preferences, FOIS provenance and bilateral Trade thresholds remain unchanged. Ordinary restored-page reads have measured0binding calls and0central Sleeper provider calls; that explicit supplement is separate from the original probe's descriptive zero-request field. Known unavailable source/calendars/generations remain withheld; unknown completion does not become a final window. Other cached model decisions are not revalidated by rebinding actual-result disclosures.

Original failed local sourcee10f/treef499 executed4,241tests with one cancellation-fixture PID assertion failure. Six gates passed, unittest failed, three later gates did not execute. Its640manifest payloads verify and remain separately preserved. The fixture signaled submission without proving execution; it now waits for a real spawned-worker marker before cancellation, retaining all original exit/scratch/in-flight assertions and deadlines. Production lifecycle code is unchanged. Original scheduling state was not directly captured and is not reconstructed. The superseded hosted canonical was canceled with2,447starts/2,446stops and no final result; it is never called passing. [Exact reconciliation](cancellation-fixture-reconciliation.json), [original failed/canceled evidence](prior-originals) and2236-prior.zip preserve original bytes.

The complete local canonical payload tree is inside2236-recovery.zip/local-canonical; the original hosted artifact is attached ascanonical-original.zip. Their own manifests resolve after extracting those archives. This directory's manifest covers its published files separately. Numbered logs concatenate to original console hashes. Actions artifacts and source trees are distinct from this documentary evidence tree. Source checks, fixture acceptance, public guest smoke and authenticated live acceptance remain explicitly separated. Physical iPhone/Safari, private Granite peak, earlier503cause and long-term leak freedom are not established.
''')
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if p.is_file():
  data=p.read_bytes()
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
  rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],merge=merged['merge_commit'],status='RELEASED; live actual-score parity HELD',files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows) + hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()+'  manifest.json\n')
print('Sanitized payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),'manifestSHA256',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
