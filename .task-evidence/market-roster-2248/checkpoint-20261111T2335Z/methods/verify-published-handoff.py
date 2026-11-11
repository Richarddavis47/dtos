"""Verify the published append-only evidence commit; download bounded representative blobs."""
from pathlib import Path
import subprocess,json,base64,hashlib,datetime
B=Path('/workspace/2248-market-needs-final');C=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/market-roster-2248';T=C/prefix
E=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()
def api(path):return json.loads(subprocess.run(['gh','api','repos/Richarddavis47/dtos/'+path],capture_output=True,text=True,check=True).stdout)
ref=api('git/ref/heads/evidence/cache-string-sharing-2237');assert ref['object']['sha']==E
commit=api('git/commits/'+E);tree=commit['tree']['sha']
for component in prefix.split('/'):
 entries=api('git/trees/'+tree)['tree'];matches=[r for r in entries if r['path']==component and r['type']=='tree'];assert len(matches)==1;tree=matches[0]['sha']
remote=api('git/trees/'+tree+'?recursive=1');assert not remote['truncated'];remote_files={r['path']:r['sha'] for r in remote['tree'] if r['type']=='blob'}
local=subprocess.run(['git','ls-tree','-r',E,'--',prefix],cwd=C,capture_output=True,text=True,check=True).stdout.splitlines();local_files={}
for line in local:
 info,path=line.split('\t',1);mode,kind,sha=info.split();assert mode=='100644' and kind=='blob';local_files[path[len(prefix)+1:]]=sha
assert local_files==remote_files
manifest=json.loads((T/'handoff-manifest.json').read_text());expected={r['name']:r['sha256'] for r in manifest['files']}
for name in ['handoff-manifest.json','SHA256SUMS']:expected[name]=hashlib.sha256((T/name).read_bytes()).hexdigest()
assert set(expected)==set(remote_files)
for name,digest in expected.items():assert hashlib.sha256((T/name).read_bytes()).hexdigest()==digest
samples=['README.md','REPORT.md','SCOUT_HANDOFF_DEPLOYED.md','candidate.patch','handoff-manifest.json','SHA256SUMS','release-verified.json','production-verified.json']
for directory,pattern in [('hosted-canonical','console-*.log'),('local-console','*.log'),('focused-console','part-*.log')]:
 paths=sorted((T/directory).glob(pattern));assert paths;samples.extend(str(p.relative_to(T)) for p in [paths[0],paths[-1]])
cases=sorted((T/'market-browser').glob('*.json'));assert cases;samples.append(str(cases[0].relative_to(T)))
receipts=[]
for name in dict.fromkeys(samples):
 obj=api('git/blobs/'+remote_files[name]);assert obj['encoding']=='base64';data=base64.b64decode(obj['content']);assert data==(T/name).read_bytes() and hashlib.sha256(data).hexdigest()==expected[name]
 receipts.append(dict(name=name,bytes=len(data),sha256=expected[name],remote_blob=remote_files[name]))
record=dict(passed=True,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),evidence_commit=E,evidence_root_tree=tree,files=len(remote_files),all_published_git_blob_ids_equal_preverified_exact_bytes=True,all_local_SHA256_manifest_entries_verified=True,manifest_sha256=expected['handoff-manifest.json'],server_blob_samples=receipts,url='https://github.com/Richarddavis47/dtos/tree/'+E+'/'+prefix,scope='All published content identities match local originals; representative server blobs byte/SHA256 checked. Immutable release attachment readbacks are separate. No independent Scout or owner-live acceptance claimed.')
(B/'evidence-published-verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['passed','evidence_commit','files','manifest_sha256','url']}))
