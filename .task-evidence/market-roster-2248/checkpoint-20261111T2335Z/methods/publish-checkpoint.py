"""Append a clearly partial recovery checkpoint, without application/release changes."""
from pathlib import Path
import json,hashlib,shutil,subprocess,datetime,re,zipfile
B=Path('/workspace/2248-market-needs-final');O=Path('/workspace/2248-market-needs');C=Path('/workspace/cache-sharing-handoff');P=Path('/workspace/dtos-publisher-2248');prefix='.task-evidence/market-roster-2248/checkpoint-20261111T2335Z';T=C/prefix;assert not T.exists();T.mkdir(parents=True);s=json.loads((B/'source.json').read_text())
def copy(p,n):
 raw=p.read_bytes();q=T/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw)
for n in ['source.json','source-transition.json','candidate.patch','FEATURE_METHOD.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','WORK_STATUS.json','NEXT_ACTIONS.md','focused-ready.json','focused-code-fingerprint-proof.json','focused-original-proof-4373.json','preservation.json','canonical-budget-reconciliation.json','resource-preservation-verified.json','resource-invocation.json','resource-native-guards.json','live-access-boundary.json','pr-metadata-update.json']:copy(B/n,n)
for p in sorted(B.glob('*.py')):copy(p,'methods/'+p.name)
for folder in ['startup-r3-scratch-failure','anchor-probe']:
 for p in sorted((B/folder).rglob('*')):
  if p.is_file() and p.suffix in {'.json','.log','.py','.png'}:copy(p,folder+'/'+str(p.relative_to(B/folder)))
for n in ['result.json','duration-analysis.json','integrity-classification.json','canonical-trace.jsonl','manifest.json','SHA256SUMS','job-transfer.json','canonical-failed-4373.receipt.json']:copy(O/'failed-final-hosted'/n,'failed-hosted-4373/'+n)
for p,n in [(B/'focused-exact-console.log','focused-console'),(O/'failed-final-hosted/job-original.log','failed-hosted-4373/job-console')]:
 raw=p.read_bytes();chunks=[];start=0
 while start<len(raw):
  end=min(start+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  chunks.append(raw[start:end]);start=end
 for i,r in enumerate(chunks,1):q=T/n/f'part-{i:03}.log';q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(r)
 (T/n/'parts.json').write_text(json.dumps(dict(source=p.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),parts=[dict(name=f'part-{i:03}.log',bytes=len(r),sha256=hashlib.sha256(r).hexdigest()) for i,r in enumerate(chunks,1)]),indent=2)+'\n')
# Unfinished publisher source is recoverable, explicitly disabled, and not deployed.
with zipfile.ZipFile(T/'UNFINISHED-publisher-source.zip','x',zipfile.ZIP_DEFLATED) as z:
 for n in ['.github/workflows/canonical-release-recovery.yml','.github/release-plans/2248.json','.github/release-plans/README.md','tools/release/publish.py','tests/test_release_publisher.py']:z.writestr(n,(P/n).read_bytes())
(T/'README.md').write_text(f'''# Partial recovery checkpoint — not a released build\n\nRecorded {datetime.datetime.now(datetime.timezone.utc).isoformat()}. Candidate `{s['candidate']}`, tree `{s['tree']}`, PR337. Production remainsv1.22.32/build2247. Exact54focused controls and finalsource constrained resource/anchor controls passed. Ten of13hostedjobs were complete as23:31UTC; Product/canonical remainedrunning.\n\nPrevious4373hostedcanonical hit4800seconds after4272/4399completions withzero recordedtesterrors/failures/skips. Its6preliminarygates passed; regression incomplete/final3gatesunexecuted. Native originalAPI SHA and fullmanifest verified; linkedGitHubartifact13899173695 is subject toretention. Source999changesonlyworkflow elapsed-time budget, no product/test bytes or resource/assertion policy.\n\nOriginal4373localcontainercontinues separately, lastreported4185completed, nofailure. Final999localstartup exitedbeforetests atunchanged8GiBscratchcheck; source/head/originalfailurepreserved. Restart onlymissingfullcanonical afteroldworkfinishes/releasesownedresources. No fullpass isclaimed.\n\nPublisher archive is unfinished tooling only, plan`finalized:false`, oldtemplateIDs: DO NOTDISPATCH/merge. NEXT_ACTIONS.md andWORK_STATUS.json give exactcontinuation. Allapp/release/deployactions remainheld. Noauthenticated ownerlive/physicalSafariacceptance; no externalinspection401retry orproductiondata changes.\n''')
files=[];pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')
for p in sorted(T.rglob('*')):
 if p.is_file():
  raw=p.read_bytes();assert len(raw)<100*1024**2
  if p.suffix in {'.py','.json','.log','.md','.patch','.txt','.jsonl'}:assert not pattern.search(raw),p
  files.append(dict(name=str(p.relative_to(T)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
(T/'manifest.json').write_text(json.dumps(dict(source=s,status='PARTIAL_NOT_RELEASED',files=files),indent=2)+'\n');files.append(dict(name='manifest.json',sha256=hashlib.sha256((T/'manifest.json').read_bytes()).hexdigest()));(T/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in files));print(json.dumps(dict(path=str(T),files=len(files)+1,scope='Partial recovery only; no source/release/deployment mutation')))
