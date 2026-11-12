"""Reversible sparse materialization of already published original-byte copies."""
import hashlib,json,shutil,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent;P=Path('/workspace/cache-sharing-handoff')
def git(*args):return subprocess.check_output(['git',*args],cwd=P,text=True).strip()
assert not git('status','--porcelain')
names=['.task-evidence/draft-capital-2247','.task-evidence/market-roster-2248','.task-evidence/roster-source-scope-2249'];rows=[]
for name in names:
 tree=git('rev-parse','HEAD:'+name)
 listed=subprocess.check_output(['git','ls-tree','-r','-z','HEAD','--',name],cwd=P).split(b'\0');tracked={}
 for line in listed:
  if not line:continue
  info,path=line.split(b'\t');tracked[path.decode()]=info.split()[2].decode()
 files=[]
 for relative,oid in tracked.items():
  f=P/relative
  if not f.exists():continue
  raw=f.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
  files.append(dict(path=relative,bytes=len(raw),git_blob=oid,sha256=hashlib.sha256(raw).hexdigest()))
 rows.append(dict(prefix=name,git_tree=tree,files=files))
spec=Path(git('rev-parse','--git-path','info/sparse-checkout'))
if not spec.is_absolute():spec=P/spec
prior=spec.read_text();record=dict(head=git('rev-parse','HEAD'),prior_sparse_patterns=prior,rows=rows,scope='Only committed duplicate materializations of completed published evidence. Git originals, immutable server evidence, and all original task evidence roots remain unchanged; no source or active candidate is affected.')
(B/'evidence-scratch-originals.json').write_text(json.dumps(record,indent=2)+'\n')
subprocess.run(['git','sparse-checkout','set','--no-cone','--stdin'],cwd=P,input=prior+'\n'+'\n'.join('!/'+n+'/' for n in names)+'\n',text=True,check=True)
assert not git('status','--porcelain') and git('rev-parse','HEAD')==record['head']
record.update(verified=True,free_after=shutil.disk_usage(B).free,materialized_bytes_recovered=sum(f['bytes'] for r in rows for f in r['files']))
(B/'evidence-scratch-verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['verified','free_after','materialized_bytes_recovered']}))
