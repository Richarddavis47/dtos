"""Relocate closed exact historical evidence; no source/guard changes; restore before capture/publishing."""
from common import *
import shutil,os,datetime,sys
S=load_source();mode=sys.argv[1];root=Path('/tmp/dtos-2253-final-source-closed-evidence')
def inv(p):
 out=[]
 for f in sorted(p.rglob('*')):
  assert not f.is_symlink(),str(f)
  if f.is_file():out.append(dict(path=str(f.relative_to(p)),bytes=f.stat().st_size,sha256=digest(f),mode=f.stat().st_mode&0o777,mtime_ns=f.stat().st_mtime_ns))
 return out
if mode=='preserve':
 assert not root.exists();assert not (BASE/'canonical-invocation.json').exists();root.mkdir();rows=[]
 folders=[Path('/workspace/2252-customer-experience'),Path('/workspace/cache-sharing-handoff'),BASE/'attempt-c11-local-complete-hosted-market-deferral',BASE/'attempt-c12-complete-validation-home-wording-gap',BASE/'attempt-c10-complete-failed/local-canonical',BASE/'attempt-prior-before-c11',BASE/'normalized-customer-acceptance']
 for i,p in enumerate(folders):
  assert p.is_dir();q=root/str(i);before=inv(p);shutil.copytree(p,q,copy_function=shutil.copy2);assert inv(q)==inv(p)==before;shutil.rmtree(p);rows.append(dict(original=str(p),temporary=str(q),files=before));write_json(BASE/'closed-evidence-temporarily-preserved.json',dict(source=S,scope='Closed exact evidence/worktree only, no active runtimes. All bytes/modes/times restored before final captures and publisher.',records=rows))
 # Reuse the original four archive identities from the just-preserved C12 receipt.
 c12=next(r for r in rows if r['original'].endswith('attempt-c12-complete-validation-home-wording-gap'));old=json.loads((Path(c12['temporary'])/'scratch-recovery-completed.json').read_text());ars=[]
 for i,r in enumerate(old['preserved_archives']):
  p=Path(r['original']);q=root/('archive-'+str(i));assert digest(p)==r['sha256'];shutil.copy2(p,q);assert digest(q)==digest(p);p.unlink();ars.append(r|dict(preserved=str(q)));write_json(BASE/'scratch-recovery-completed.json',dict(source=S,preserved_archives=ars,scope='Four exact historical closed original archives; no test/input modifications.'))
 print('Preserved closed originals, free workspace',shutil.disk_usage(BASE).free,flush=True)
 assert shutil.disk_usage(BASE).free>8*1024**3+2400000000
elif mode=='restore':
 assert json.loads((BASE/'local-container-cleanup.json').read_text())['container_absent_after_removal']
 ars=json.loads((BASE/'scratch-recovery-completed.json').read_text())['preserved_archives']
 for r in ars:
  p=Path(r['original']);q=Path(r['preserved']);assert not p.exists() and digest(q)==r['sha256'];shutil.copy2(q,p);assert digest(p)==r['sha256'];p.chmod(r['mode']);os.utime(p,ns=(r['atime_ns'],r['mtime_ns']));q.unlink()
 write_json(BASE/'preserved-archives-restored.json',dict(all_original_bytes_restored=True,rows=ars,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 for r in json.loads((BASE/'closed-evidence-temporarily-preserved.json').read_text())['records']:
  p=Path(r['original']);q=Path(r['temporary']);assert not p.exists() and inv(q)==r['files'];shutil.copytree(q,p,copy_function=shutil.copy2);assert inv(p)==r['files'];shutil.rmtree(q)
 write_json(BASE/'closed-evidence-restored.json',dict(all_original_bytes_modes_times_restored=True,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 print('All original paths, bytes, modes and times restored.',flush=True)
else:raise ValueError(mode)
