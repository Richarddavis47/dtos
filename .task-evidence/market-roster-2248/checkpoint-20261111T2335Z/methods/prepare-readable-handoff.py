"""Make completed exact-source originals directly readable; no rewriting console text."""
from pathlib import Path
import json,shutil,hashlib,re
B=Path('/workspace/2248-market-needs-final');T=Path('/workspace/cache-sharing-handoff/.task-evidence/market-roster-2248');s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'];assert local['tests']==host['tests']==4399
T.mkdir(exist_ok=True)
def copy(src,target):
 assert src.is_file() and not src.is_symlink(),src;target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():assert target.read_bytes()==src.read_bytes(),'Do not overwrite an earlier published artifact: '+str(target)
 else:shutil.copyfile(src,target)
def split(src,target):
 target.mkdir(parents=True,exist_ok=True);raw=src.read_bytes();chunks=[];start=0
 while start<len(raw):
  end=min(start+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  chunks.append(raw[start:end]);start=end
 for i,r in enumerate(chunks,1):
  p=target/f'part-{i:03}.log'
  if p.exists():assert p.read_bytes()==r
  else:p.write_bytes(r)
 assert b''.join(chunks)==raw
 meta=dict(source=src.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),parts=[dict(name=f'part-{i:03}.log',bytes=len(r),sha256=hashlib.sha256(r).hexdigest()) for i,r in enumerate(chunks,1)])
 (target/'parts.json').write_text(json.dumps(meta,indent=2)+'\n')
files=['source.json','candidate.patch','FEATURE_METHOD.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','preservation.json','focused-ready.json','focused-code-fingerprint-proof.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','host-canonical-verified.json','hosted-artifacts-verified.json','hosted-final-records.json','validation-runs.json','artifact-download-queue.json','product-test-counts.json','resource-preservation-verified.json','resource-native-guards.json','prior-package-complete.json','production-baseline.json','live-access-boundary.json','checkpoint-published-verified.json','ready-native-integrity.json','publisher-attachment-rename-controls.log','publisher-current-final-ruff.log']
for name in files:copy(B/name,T/name)
for src,target in [('host-canonical-readable','hosted-canonical'),('readable-console','local-console'),('market-browser','market-browser'),('anchor-probe','anchor-probe')]:
 for p in sorted((B/src).rglob('*')):
  if p.is_file():copy(p,T/target/p.relative_to(B/src))
for name in ['canonical.log','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:copy(B/'local-canonical'/name,T/'local-canonical'/name)
split(B/'focused-exact-console.log',T/'focused-console')
for p in sorted((B/'hosted-decoded-originals').glob('*-transfer.json')):
 r=json.loads(p.read_text());job=str(r['job']);copy(p,T/'job-consoles'/job/'transfer.json');split(p.with_name(job+'.log'),T/'job-consoles'/job)
for folder in [*[f'focus-{i}' for i in range(1,12)],'before-replay','before-replay-2']:
 for name in ['result.json','invocation.json','container-state-original.json']:
  p=B/folder/name
  if p.is_file():copy(p,T/'prior-attempts'/folder/name)
 p=B/folder/'original-console.log'
 if p.is_file():split(p,T/'prior-attempts'/folder/'console')
for name in ['source.json','candidate.patch','incomplete-canonical-stop.json','superseded-hosted-final-status.json','artifacts-final-metadata.json']:
 copy(B/'superseded-a38'/name,T/'prior-attempts/superseded-a38'/name)
split(B/'superseded-a38/local-canonical/unittest-console.log',T/'prior-attempts/superseded-a38/local-console')
for p in sorted((B/'superseded-a38/hosted-decoded-originals').glob('*-transfer.json')):
 job=str(json.loads(p.read_text())['job']);split(p.with_name(job+'.log'),T/'prior-attempts/superseded-a38/jobs'/job)
print(json.dumps(dict(destination=str(T),files=sum(p.is_file() for p in T.rglob('*')),scope='Completed source validation copied for review; publication/deployment receipts are still separate')))
