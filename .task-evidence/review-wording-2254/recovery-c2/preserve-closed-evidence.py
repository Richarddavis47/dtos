from pathlib import Path
import shutil,hashlib,json,os,datetime,sys
B=Path(__file__).resolve().parent;root=Path('/tmp/dtos-2254-closed-originals');mode=sys.argv[1]
def inventory(p):
 rows=[]
 for q in sorted(p.rglob('*')):
  assert not q.is_symlink(),q
  if q.is_file():
   with q.open('rb')as f:h=hashlib.file_digest(f,'sha256').hexdigest()
   st=q.stat();rows.append(dict(path=str(q.relative_to(p)),bytes=st.st_size,sha256=h,mode=st.st_mode&0o777,mtime_ns=st.st_mtime_ns))
 return rows
if mode=='preserve':
 assert not root.exists();root.mkdir();rows=[]
 for i,p in enumerate(map(Path,['/workspace/2253-customer-acceptance','/workspace/2252-customer-experience','/workspace/cache-sharing-handoff'])):
  data=inventory(p);q=root/str(i);shutil.copytree(p,q,copy_function=shutil.copy2);assert inventory(q)==inventory(p)==data;shutil.rmtree(p);rows.append(dict(original=str(p),temporary=str(q),files=data));(B/'closed-originals-preserved.json').write_text(json.dumps(dict(records=rows,scope='Closed original evidence only; exact bytes/modes/times preserved on existing separate scratch volume. No active source/runtimes or production data moved.'),indent=2)+'\n');print('Preserved',str(p),flush=True)
 print('Free',shutil.disk_usage(B).free,flush=True);assert shutil.disk_usage(B).free>8*1024**3+2400000000
elif mode=='restore':
 d=json.loads((B/'closed-originals-preserved.json').read_text())
 for r in d['records']:
  p=Path(r['original']);q=Path(r['temporary']);assert not p.exists() and inventory(q)==r['files'];shutil.copytree(q,p,copy_function=shutil.copy2);assert inventory(p)==r['files'];shutil.rmtree(q)
 (B/'closed-originals-restored.json').write_text(json.dumps(dict(all_original_bytes_modes_times_restored=True,at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
else:raise ValueError(mode)
