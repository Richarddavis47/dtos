"""Verify published readable originals before any application merge."""
from pathlib import Path
import subprocess,json,hashlib,base64,datetime
B=Path(__file__).resolve().parent;C=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/roster-source-scope-2249';T=C/prefix;E=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/Richarddavis47/dtos/'+path],text=True))
assert api('git/ref/heads/evidence/cache-string-sharing-2237')['object']['sha']==E;tree=api('git/commits/'+E)['tree']['sha']
for part in prefix.split('/'):
 matches=[x for x in api('git/trees/'+tree)['tree'] if x['path']==part and x['type']=='tree'];assert len(matches)==1;tree=matches[0]['sha']
r=api('git/trees/'+tree+'?recursive=1');assert not r['truncated'];remote={x['path']:x['sha'] for x in r['tree'] if x['type']=='blob'};local={}
for line in subprocess.check_output(['git','ls-tree','-r',E,'--',prefix],cwd=C,text=True).splitlines():
 info,name=line.split('\t');mode,kind,blob=info.split();assert mode=='100644' and kind=='blob';local[name[len(prefix)+1:]]=blob
assert local==remote
for name,blob in remote.items():
 raw=(T/name).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob
m=json.loads((T/'prepublication-readable-manifest.json').read_text());assert m['candidate']=='36fc76784d968fcd0917ce91821840649da1a7a4' and m['tree']=='c60f914d2a0b6b34c2d3e87cdce8eae4560d0b49'
for row in m['files']:
 raw=(T/row['name']).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
samples=['README.md','source.json','candidate.patch','resumed-original-reconciliation.json','prepublication-readable-manifest.json','PREPUBLICATION_SHA256SUMS']
for folder in ['local-canonical-unittest-console-log','hosted-canonical-unittest-console-log','focused-console']:
 parts=sorted((T/folder).glob('part-*.log'));assert parts;samples.extend(str(p.relative_to(T)) for p in [parts[0],parts[-1]])
receipts=[]
for name in dict.fromkeys(samples):
 obj=api('git/blobs/'+remote[name]);assert obj['encoding']=='base64';raw=base64.b64decode(obj['content']);assert raw==(T/name).read_bytes();receipts.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),remote_blob=remote[name]))
proof=dict(passed=True,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),evidence_commit=E,files=len(remote),all_git_blob_ids_equal_exact_original_bytes=True,stable_original_SHA256_manifest_verified=True,manifest_sha256=hashlib.sha256((T/'prepublication-readable-manifest.json').read_bytes()).hexdigest(),server_blob_samples=receipts,url='https://github.com/Richarddavis47/dtos/tree/'+E+'/'+prefix,scope='Published original logs and source before release; no merge/deployment/owner-live claim. All content identities and representative server bytes verified.');(B/'prepublication-published-verified.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:proof[k] for k in ['passed','evidence_commit','files','manifest_sha256','url']}))
