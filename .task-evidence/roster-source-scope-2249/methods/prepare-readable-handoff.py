"""Publishable exact-byte originals and bounded readable parts; never recreated logs."""
from pathlib import Path,PurePosixPath
import json,hashlib,zipfile,re
B=Path('/workspace/2249-sleeper-relevance');T=Path('/workspace/cache-sharing-handoff/.task-evidence/roster-source-scope-2249');s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'];assert local['tests']==host['tests']==4419;assert all(x['candidate']==s['candidate'] and x['tree']==s['tree'] for x in [local,host,native])
def write(raw,path):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():assert path.read_bytes()==raw,'Preserve already-published file: '+str(path)
 else:path.write_bytes(raw)
def copy(p,path):assert p.is_file() and not p.is_symlink();write(p.read_bytes(),path)
def split(raw,target,source):
 raw.decode('utf-8');target.mkdir(parents=True,exist_ok=True);parts=[];offset=0
 while offset<len(raw):
  end=min(offset+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  assert end>offset;parts.append(raw[offset:end]);offset=end
 for i,data in enumerate(parts,1):write(data,target/f'part-{i:03}.log')
 assert b''.join(parts)==raw
 manifest=dict(source=source,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),scope='Exactoriginalbytes split only atUTF8 boundaries; originalCR/LF preserved. Parts may split a logical line. Concatenation in lexicalorder recreates originalbytes, not a recreatedtest run.',parts=[dict(name=f'part-{i:03}.log',bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for i,data in enumerate(parts,1)])
 write((json.dumps(manifest,indent=2)+'\n').encode(),target/'parts.json')
 write(('# Original log parts\n\n'+source+'\n\nWholeoriginal SHA256: `'+manifest['sha256']+'`. Join `part-*.log` in lexicalorder to reproduce the exactoriginal bytes.\n\n'+'\n'.join(f'- [part-{i:03}.log](part-{i:03}.log)' for i in range(1,len(parts)+1))+'\n').encode(),target/'README.md')
names=['source.json','source-transition.json','candidate.patch','FEATURE_METHOD.md','EVIDENCE_BOUNDARIES.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','preservation.json','baseline-probe.json','baseline-probe-original.log','baseline-probe.py','focused-ready.json','focused-final-invocation.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','host-canonical-verified.json','hosted-artifacts-verified.json','hosted-final-records.json','validation-runs.json','artifact-download-queue.json','capture-extraction.json','product-test-counts.json','resource-preservation-verified.json','resource-native-guards.json','resource-invocation.json','prior-package-complete.json','prior-package-scope-correction.json','local-capital-capture-invocation.json','local-capital-capture-original.log','recovery-packaging-failure.json','recovery-build-first-incomplete-original.log','recovery-manifest-first-incomplete-original.json','publisher-local-capital-prefix-correction.json','recovery-component-precheck.json','recovery-component-precheck-original.log','prior-package-scope-correction-original.log','source-cleanup-verified.json','resumed-original-reconciliation.json','resumed-original-reconciliation-original.log','eligibility-boundary-review.json','production-baseline-resumed.json','recovery-packaging-interruption.json','recovery-build-interrupted-original.log','prior-manifest-unfinalized-scope-original.json','prior-package-unfinalized-scope-original.json','recovery-verified.json','production-baseline.json','live-access-boundary.json','checkpoint-published-verified.json','checkpoint-hosted-published-verified.json','canonical-invocation.json','canonical-runner-extraction.json','canonical-harness-schema-adaptation.json','retained-history-feature.json','retained-history-probe-invocation.json','publisher-source-clean-controls-original.log','publisher-source-clean-ruff-original.log','ready-native-integrity.json']
for name in names:copy(B/name,T/name)
for folder in ['market-browser','roster-browser','partner-history','team-need','protections','offer-comparison','activation','front-office-workflow','history-browser','local-capital-capture']:
 for p in sorted((B/folder).rglob('*')):
  if p.is_file():copy(p,T/folder/p.relative_to(B/folder))
for folder in ['local-preflight','local-restoration-unused','local-resident-refresh']:
 for p in sorted((B/folder).rglob('*')):
  if not p.is_file() or p.suffix not in ['.json','.jsonl','.log','.py','.md','.txt'] and p.name!='SHA256SUMS':continue
  rel=p.relative_to(B/folder)
  if p.suffix in ['.log','.jsonl'] and p.stat().st_size>60000:split(p.read_bytes(),T/'resource-originals'/folder/str(rel).replace('.','-'),'Exactnative original '+folder+'/'+str(rel))
  else:copy(p,T/'resource-originals'/folder/rel)
for folder,label in [('local-canonical','local-canonical'),('host-canonical-readable','hosted-canonical')]:
 for name in ['canonical.log','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:copy(B/folder/name,T/label/name)
 for name in ['unittest-console.log','tests.jsonl','memory.jsonl']:split((B/folder/name).read_bytes(),T/(label+'-'+name.replace('.','-')),'Exact original '+label+'/'+name)
copy(B/'focused-exact/result.json',T/'focused/result.json');split((B/'focused-exact/original-console.log').read_bytes(),T/'focused-console','Exact final123control original console, source'+s['candidate'])
for p in sorted((B/'hosted-decoded-originals').glob('*-transfer.json')):
 meta=json.loads(p.read_text());job=str(meta['job']);copy(p,T/'job-consoles'/job/'transfer.json');raw=(B/'hosted-decoded-originals'/(job+'.log')).read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['sha256'];split(raw,T/'job-consoles'/job,'OriginalMCPdecoded GitHubjob'+job+'; notHTTPwire-byte claim')
prior=json.loads((B/'prior-package-complete.json').read_text());archive=B/'prior-package.zip';assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==prior['sha256']
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name in z.namelist():
  p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts
  if name.endswith('/'):continue
  if p.suffix=='.log':split(z.read(name),T/'prior-attempts'/str(p.with_suffix('')),'Exact original prior archive member '+name)
  elif p.suffix in ['.json','.jsonl','.md','.patch','.py','.txt'] or p.name=='SHA256SUMS':
   raw=z.read(name)
   if len(raw)>60000:split(raw,T/'prior-attempts'/str(p).replace('.','-'),'Exact original prior archive member '+name)
   else:write(raw,T/'prior-attempts'/str(p))
for p in sorted(B.glob('*.py')):copy(p,T/'methods'/p.name)
print(json.dumps(dict(destination=str(T),files=sum(p.is_file() for p in T.rglob('*')),scope='Current mandatory originals, exactreadable console/metrics/event parts, nativecaptures and historicalfailed/cancelled records. Finalproduction/publicationreceipts andchecksummanifest are added separately.')))
