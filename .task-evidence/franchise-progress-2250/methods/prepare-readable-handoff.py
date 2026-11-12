"""Readable original-byte handoff; no reconstructed or silently rewritten logs."""
from pathlib import Path,PurePosixPath
import hashlib,json,re,zipfile
B=Path(__file__).resolve().parent;T=Path('/workspace/cache-sharing-handoff/.task-evidence/franchise-progress-2250');s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed']
assert local['tests']==host['tests']==4435 and all(r['candidate']==s['candidate'] and r['tree']==s['tree'] for r in [local,host,native])
def write(raw,p):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==raw,'Preserve published original: '+str(p)
 else:p.write_bytes(raw)
def copy(p,target):assert p.is_file() and not p.is_symlink();write(p.read_bytes(),target)
def split(raw,target,provenance):
 raw.decode('utf-8');target.mkdir(parents=True,exist_ok=True);parts=[];offset=0
 while offset<len(raw):
  end=min(offset+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  assert end>offset;parts.append(raw[offset:end]);offset=end
 for i,part in enumerate(parts,1):write(part,target/f'part-{i:03}.log')
 assert b''.join(parts)==raw
 rows=[dict(name=f'part-{i:03}.log',bytes=len(part),sha256=hashlib.sha256(part).hexdigest()) for i,part in enumerate(parts,1)]
 meta=dict(source=provenance,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),parts=rows,scope='Original bytes split at UTF8 boundaries only; CR/LF preserved. Parts can split a logical line; concatenate in lexical order to reproduce original.')
 write((json.dumps(meta,indent=2)+'\n').encode(),target/'parts.json')
 write(('# Original log parts\n\n'+provenance+'\n\nWhole SHA256: `'+meta['sha256']+'`. Concatenate `part-*.log` in lexical order.\n\n'+'\n'.join('- ['+r['name']+']('+r['name']+')' for r in rows)+'\n').encode(),target/'README.md')
# Curated originals only. Private API envelopes and any temporary delivery URL are excluded.
names=['source.json','candidate.patch','FEATURE_METHOD.md','EVIDENCE_BOUNDARIES.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','preservation.json','baseline.json','baseline-probe.json','baseline-probe-original.log','baseline-probe.py','baseline-probe-invocation.json','pre-commit-baseline.json','production-baseline-and-access.json','focused-ready.json','focused-exact-invocation.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','host-canonical-verified.json','hosted-artifacts-verified.json','hosted-final-records.json','validation-runs.json','artifact-download-queue.json','capture-extraction.json','product-test-counts.json','resource-preservation-verified.json','resource-native-guards.json','resource-invocation.json','prior-package-final-complete.json','local-capital-capture-invocation.json','local-capital-capture-original.log','recovery-verified.json','canonical-invocation.json','canonical-runner-extraction.json','retained-history-feature.json','retained-history-probe-invocation.json','publisher-controls-reconciled.json','publisher-source-checkpoint.json','publisher-base-alignment.json','checkpoint-published.json','checkpoint-planning-correction.json','local-completion-observer.json']
names += ['source-transition-f40-to-b522.json','contextual-diagnostic-reconciled.json','contextual-diagnostic-sealed.json','input-relocation-reconciliation.json','executor-transport-recovery.json','reconciliation-checkpoint-published.json','cancelled-artifact-immutable-location.json','visual-review.json','fois-fixture-structural-review.json','resumption-baseline.json','observer-recovery.json','FOIS_FIXTURE_REVIEW.md','hosted-checkout-identities.json','hosted-resource-measurements.json','capture-extraction-scope-correction.json','observer-recovery-2.json','local-resource-measurements.json','pre-release-baseline.json']
for name in names:copy(B/name,T/name)
for p in sorted((B/'observer-recovery-2').glob('*')):
 if p.is_file():copy(p,T/'observer-recovery-2'/p.name)
for p in sorted((B/'observer-recovery').glob('*')):
 if p.is_file():copy(p,T/'observer-recovery'/p.name)
for folder in ['partner-history','team-need','protections','offer-comparison','market-browser','roster-browser','history-browser','local-capital-capture','focused-exact/franchise-progress']:
 for p in sorted((B/folder).rglob('*')):
  if p.is_file():copy(p,T/folder/p.relative_to(B/folder))
for folder in ['local-preflight','local-restoration-unused','local-resident-refresh']:
 for p in sorted((B/folder).rglob('*')):
  if not p.is_file() or p.suffix not in {'.json','.jsonl','.log','.py','.md','.txt'} and p.name!='SHA256SUMS':continue
  rel=p.relative_to(B/folder)
  if p.suffix in {'.log','.jsonl'} and p.stat().st_size>60000:split(p.read_bytes(),T/'resource-originals'/folder/str(rel).replace('.','-'),'Exact native original '+folder+'/'+str(rel))
  else:copy(p,T/'resource-originals'/folder/rel)
for folder,label in [('local-canonical','local-canonical'),('host-canonical-readable','hosted-canonical')]:
 for name in ['canonical.log','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:copy(B/folder/name,T/label/name)
 for name in ['unittest-console.log','tests.jsonl','memory.jsonl']:split((B/folder/name).read_bytes(),T/(label+'-'+name.replace('.','-')),'Exact original '+label+'/'+name)
copy(B/'focused-exact/result.json',T/'focused/result.json');split((B/'focused-exact/original-console.log').read_bytes(),T/'focused-console','Exact final103-control console, source '+s['candidate'])
for p in sorted((B/'hosted-decoded-originals').glob('*-transfer.json')):
 meta=json.loads(p.read_text());job=str(meta['job']);copy(p,T/'job-consoles'/job/'transfer.json');raw=(B/'hosted-decoded-originals'/(job+'.log')).read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['sha256'];split(raw,T/'job-consoles'/job,'Original MCP-decoded GitHub job '+job+'; not HTTP wire bytes')
prior=json.loads((B/'prior-package-final-complete.json').read_text());archive=B/'prior-package-final.zip';assert hashlib.sha256(archive.read_bytes()).hexdigest()==prior['sha256']
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name in z.namelist():
  p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts
  if name.endswith('/'):continue
  raw=z.read(name)
  if p.suffix=='.log' or len(raw)>60000 and p.suffix in {'.json','.jsonl','.md','.py','.txt','.patch'}:split(raw,T/'prior-attempts'/str(p).replace('.','-'),'Exact earlier archive member '+name)
  elif p.suffix in {'.json','.jsonl','.md','.py','.txt','.patch'}:write(raw,T/'prior-attempts'/str(p))
for p in sorted(B.glob('*.py')):copy(p,T/'methods'/p.name)
print(json.dumps(dict(destination=str(T),files=sum(p.is_file() for p in T.rglob('*')),scope='Source-bound originals/readable parts; final production/publication receipts and root checksum manifest are separately finalized.')))
