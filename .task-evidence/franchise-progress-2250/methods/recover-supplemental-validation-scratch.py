"""Reversibly omit only clean committed duplicates in completed worktrees."""
import hashlib,json,shutil,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent
records=[]
def git(p,*args):return subprocess.check_output(['git',*args],cwd=p,text=True).strip()
paths=[Path('/workspace/dtos-2244-validated'),Path('/workspace/dtos-2245')]
for p in paths:
 assert not git(p,'status','--porcelain'),str(p)
 excludes=['!/static/'] if (p/'static').is_dir() else []
 files=[f for f in (p/'static').rglob('*') if f.is_file()] if excludes else []
 for f in (p/'.github/release-plans').glob('*'):
  if f.suffix in {'.part','.zip'}:
   excludes.append('!/'+str(f.relative_to(p)));files.append(f)
 if not excludes:continue
 rows=[]
 for f in files:
  relative=str(f.relative_to(p));raw=f.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  assert git(p,'rev-parse','HEAD:'+relative)==blob
  rows.append(dict(path=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),git_blob=blob))
 spec=Path(git(p,'rev-parse','--git-path','info/sparse-checkout'))
 if not spec.is_absolute():spec=p/spec
 prior=spec.read_text() if spec.exists() else '/*\n'
 record=dict(checkout=str(p),head=git(p,'rev-parse','HEAD'),tree=git(p,'rev-parse','HEAD^{tree}'),prior_sparse_patterns=prior,exclusions=excludes,files=rows)
 records.append(record)
 (B/'supplemental-scratch-originals.json').write_text(json.dumps(records,indent=2)+'\n')
 subprocess.run(['git','sparse-checkout','set','--no-cone','--stdin'],cwd=p,input=prior+'\n'+'\n'.join(excludes)+'\n',text=True,check=True)
 assert git(p,'rev-parse','HEAD^{tree}')==record['tree'] and not git(p,'status','--porcelain')
 assert all(not (p/r['path']).exists() for r in rows)
 record['verified']=True
(B/'supplemental-scratch-verified.json').write_text(json.dumps(dict(records=records,free_after=shutil.disk_usage(B).free,scope='Only materialized duplicate committed bytes in clean completed validation/publisher worktrees; original logs, source trees, Git objects and current candidate untouched. Restore by passing prior_sparse_patterns back to git sparse-checkout set --no-cone --stdin.'),indent=2)+'\n')
print(json.dumps(dict(worktrees=len(records),recovered_bytes=sum(x['bytes'] for r in records for x in r['files']),free=shutil.disk_usage(B).free)))
