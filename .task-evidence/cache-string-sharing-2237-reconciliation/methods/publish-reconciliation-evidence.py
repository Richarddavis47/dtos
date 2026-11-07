from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,shutil,subprocess,zipfile
b=Path('/workspace/2237-cache-duplication');r=b/'reconciliation';c=Path('/workspace/cache-sharing-handoff');relative='.task-evidence/cache-string-sharing-2237-reconciliation';root=c/relative
assert not root.exists();root.mkdir()
for name in ['README.md','CORRIGENDUM.md','METHODS.md','SCOUT_HANDOFF.md']:shutil.copy2(r/name,root/name)
(root/'.gitattributes').write_text('* -text\n');(root/'results').mkdir();(root/'methods').mkdir()
for p in r.iterdir():
 if p.is_file() and p.suffix in ['.json','.log']:shutil.copy2(p,root/'results'/p.name)
for name in ['reconcile-restoration.py','run-reconciliation.py','clean-lifecycle-reconciliation.py','analyze-retained-components.py','reconciliation_analysis.py','test_reconciliation_analysis.py','reconcile-baseline-validation.py','write-reconciliation-report.py','run-constrained.py','publish-reconciliation-evidence.py']:
 shutil.copy2(b/name,root/'methods'/name)
for p in r.glob('*.py'):shutil.copy2(p,root/'methods'/p.name)
shutil.copy2(b/'profile-combined.py',root/'methods/original-confounded-profile.py')
shutil.copy2(b/'fixture-locations.json',root/'fixtures.json')
summary=json.loads((r/'verified-summary.json').read_text());assert summary['decoder_pairs']==12 and summary['new_controlled_restorations']==24 and summary['production_changes'] is False
assert re.search(rb'Ran 63 tests in [0-9.]+s\s+OK\s*$',(r/'focused-baseline-original.log').read_bytes());assert re.search(rb'Ran 12 tests in [0-9.]+s\s+OK\s*$',(r/'verifier-regression-original.log').read_bytes())
# Original bytes stay intact; only oversized logs get separately indexed parts.
index=['# Readable original logs','','Original full files remain unedited. Any numbered parts concatenate byte-for-byte. Earlier source-release attempts remain in the prior immutable package.','','| Original log | Bytes | SHA256 |','|---|---:|---|']
for p in sorted((root/'results').glob('*.log')):
 data=p.read_bytes();index.append(f'| [{p.name}](results/{p.name}?raw=1) | {len(data)} | `{hashlib.sha256(data).hexdigest()}` |')
 if len(data)>60000:
  folder=root/'readable-logs'/p.stem;folder.mkdir(parents=True);parts=[];block=bytearray()
  for line in data.splitlines(keepends=True):
   if block and len(block)+len(line)>60000:parts.append(bytes(block));block.clear()
   block.extend(line)
  if block:parts.append(bytes(block))
  assert b''.join(parts)==data
  for n,part in enumerate(parts,1):
   dest=folder/f'part-{n:03d}.log';dest.write_bytes(part);index.append(f'| [part{n}]({dest.relative_to(root)}?raw=1) | {len(part)} | `{hashlib.sha256(part).hexdigest()}` |')
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if p.is_file():
  data=p.read_bytes();assert not secret.search(data),p;rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
manifest={'status':'PARTIAL:measurement reconciliation complete;live admission/entry/parity HELD;no new release','baseline':summary['baseline'],'tree':summary['tree'],'application_changes':False,'observed_at':datetime.now(timezone.utc).isoformat(),'files':rows}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(root/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in rows)+hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()+'  manifest.json\n')
archive=root/'study-evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(root.rglob('*')):
  if p.is_file() and p!=archive:z.write(p,str(p.relative_to(root)))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
sha=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest();downloads=dict(archive='study-evidence.zip',bytes=archive.stat().st_size,sha256=sha,manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),scope='Sanitized disposable results and methods only. Original production data is absent. Original prior release evidence remains unchanged.')
(root/'DOWNLOADS.json').write_text(json.dumps(downloads,indent=2)+'\n');(root/'DOWNLOADS.SHA256SUMS').write_text(sha+'  study-evidence.zip\n'+hashlib.sha256((root/'DOWNLOADS.json').read_bytes()).hexdigest()+'  DOWNLOADS.json\n')
paths=[str(p.relative_to(c)) for p in root.rglob('*') if p.is_file()];spec=b/'reconciliation-pathspec.nul';spec.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
subprocess.run(['git','add','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=c,check=True);subprocess.run(['git','commit','-m','Reconcile build2237 decoder-only measurements and retain unresolved live boundaries'],cwd=c,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=c,check=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=c,text=True).strip();print(json.dumps(dict(evidence_commit=commit,files=len(rows),**downloads)))
(b/'reconciliation-publication.json').write_text(json.dumps(dict(evidence_commit=commit,files=len(rows),**downloads),indent=2)+'\n')
