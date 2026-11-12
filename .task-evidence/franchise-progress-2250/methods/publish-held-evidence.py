"""Publish the original failed/interrupted attempt and a precise recovery checkpoint."""
import datetime,hashlib,json,re,shutil,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent;E=Path('/workspace/cache-sharing-handoff');s=json.loads((B/'source.json').read_text());now=datetime.datetime.now(datetime.timezone.utc);prefix=Path('.task-evidence/franchise-progress-2250/checkpoints')/now.strftime('%Y-%m-%dT%H%MZ-HELD');T=E/prefix;assert not T.exists();T.mkdir(parents=True)
def write(p,raw):
 assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
def copy(name,prefix=''):
 p=B/name;assert p.is_file();raw=p.read_bytes()
 if p.suffix not in {'.png','.zip'}:assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})',raw),name
 write(T/(prefix or name),raw)
def split(name,target):
 raw=(B/name).read_bytes();raw.decode('utf-8');parts=[];offset=0
 while offset<len(raw):
  end=min(offset+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  chunk=raw[offset:end];parts.append(dict(name=f'part-{len(parts)+1:03}.log',bytes=len(chunk),sha256=hashlib.sha256(chunk).hexdigest()));write(T/target/parts[-1]['name'],chunk);offset=end
 assert b''.join((T/target/r['name']).read_bytes() for r in parts)==raw
 write(T/target/'parts.json',(json.dumps(dict(source=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),parts=parts,scope='Exact original bytes; split at UTF8 boundaries only. CR/LF preserved.'),indent=2)+'\n').encode())
 write(T/target/'README.md',('# Original failed-run log parts\n\n'+name+'\n\n'+'\n'.join('- ['+r['name']+']('+r['name']+')' for r in parts)+'\n').encode())
for name in ['WORK_STATUS.json','NEXT_ACTIONS.md','source.json','candidate.patch','failed-local-reconciled.json','failed-local-f40-original.zip','local-responsiveness-failure.json','local-cancellation-invocation.json','focused-ready.json','focused-exact/result.json','resource-native-guards.json','hosted-history-early-verified.json','profile-prefix-invocation.json','profile-prefix-child-3.py','profile-prefix-3/diagnostic-method.json','profile-prefix-2/METHOD_LIMITATION.json','profile-prefix-2/container-state-original.json','profile-prefix/bootstrap-failure.json','production-baseline-and-access.json','publisher-source-checkpoint.json']:copy(name)
for name in ['result.json','canonical.log','canonical-trace.jsonl','manifest.json','SHA256SUMS']:copy('prior-local-f40/local-canonical/'+name,'failed-local/'+name)
for name in ['unittest-console.log','tests.jsonl','memory.jsonl']:split('prior-local-f40/local-canonical/'+name,'failed-local-'+name.replace('.','-'))
raw=subprocess.check_output(['git','diff','--binary'],cwd='/workspace/dtos-publisher-2250');write(T/'publisher-current-uncommitted.patch',raw)
write(T/'README.md',f'''# HELD — original local failure and ongoing diagnosis

Source `{s['candidate']}` / tree `{s['tree']}` / PR339. Production remains v1.22.34/build2249; no merge/tag/draft/deploy. Focused88 and native3 pass, but the full local attempt failed an existing500msFOISliveness assertion at542.770149ms. Its remainder was interrupted, with1840recorded stop events(one actualfailure), seventhgatefailed andthreegatesunexecuted. Stop events are not passing-test counts.

The original sealed failed archive is25333473bytes, SHA256`0e8e6dc86b748bab5ea046df4ac697bb8dedeff17af57f8cf44ae047716aa560`. Original console/events/memory are directly readable in numbered parts; whole/part checksums are included. Private fixture databases/cache are not published. No logs were recreated.

The source-bound matched pre-failure prefix diagnostic is RUNNING, not release evidence. Two earlier prototypes are explicitly invalid/incomplete; their limitations are retained. No GC cause, source defect or correction is yet established.500ms/memory policies and app source remain unchanged. Follow current NEXT_ACTIONS; do not launch duplicate diagnostics or substitute isolated/hosted passes for the failed full-local gate.\n'''.encode())
rows=[dict(path=str(p.relative_to(T)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(T.rglob('*')) if p.is_file()];write(T/'manifest.json',(json.dumps(dict(source=s,status='HELD_WITH_ORIGINAL_FAILED_EVIDENCE',files=rows),indent=2)+'\n').encode());write(T/'SHA256SUMS',''.join(r['sha256']+'  '+r['path']+'\n' for r in rows).encode())
subprocess.run(['git','-c','core.autocrlf=false','add','-f','--sparse','--',str(prefix)],cwd=E,check=True)
index={}
for line in subprocess.check_output(['git','ls-files','-s','-z','--',str(prefix)],cwd=E).split(b'\0'):
 if line:
  info,path=line.split(b'\t');index[path.decode()]=info.split()[1].decode()
for p in T.rglob('*'):
 if p.is_file():
  raw=p.read_bytes();assert index[str(p.relative_to(E))]==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
subprocess.run(['git','commit','-m','Preserve original2250 local responsiveness failure and held recovery state'],cwd=E,check=True);subprocess.run(['git','push','origin','HEAD'],cwd=E,check=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=E,text=True).strip();receipt=dict(commit=commit,prefix=str(prefix),url='https://github.com/Richarddavis47/dtos/tree/'+commit+'/'+str(prefix),manifest_sha256=hashlib.sha256((T/'manifest.json').read_bytes()).hexdigest(),source=s,status='HELD_NO_RELEASE');(B/'held-checkpoint-published.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
