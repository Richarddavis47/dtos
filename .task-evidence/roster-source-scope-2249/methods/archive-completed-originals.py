"""Losslessly archive completed original evidence; no active source/private data."""
from pathlib import Path
import hashlib,json,zipfile,datetime,shutil
B=Path('/workspace/2249-sleeper-relevance')
roots=[Path('/workspace/2246-granite-activation/expansion/final'),Path('/workspace/2246-granite-activation/expansion/final-r2'),Path('/workspace/2246-granite-activation/expansion/final-r3')]
# All three are prior released/failed completed attempts. No container runs here.
archive=B/'completed-2246-originals.zip'
assert not archive.exists()
rows=[]
for root in roots:
 for p in sorted(root.rglob('*')):
  assert not p.is_symlink(),str(p)
  if p.is_file():
   rows.append(dict(path=str(p),name=str(p.relative_to(root.parent)),bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()))
assert len({r['name'] for r in rows})==len(rows)
record=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Byte-preserved completed2246 evidence only. Not a new test run. No active checkout, production cache, study input or running output removed.',free_before=shutil.disk_usage(B).free,files=rows,archive=str(archive))
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for row in rows:z.write(row['path'],row['name'])
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for row in rows:
  raw=z.read(row['name']);assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
record.update(archive_bytes=archive.stat().st_size,archive_sha256=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),all_original_bytes_verified=True)
(B/'completed-archival-before-removal.json').write_text(json.dumps(record,indent=2)+'\n')
# Keep readable top-level originals and sealed original archives; release only
# redundant loose members, each now verified in the new lossless archive.
for row in rows:
 p=Path(row['path'])
 root=next(r for r in roots if p.is_relative_to(r))
 if p.parent==root or p.stat().st_uid!=1000:continue
 assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==row['sha256']
 p.unlink()
record['free_after']=shutil.disk_usage(B).free
(B/'completed-archival-verified.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['archive_bytes','archive_sha256','free_before','free_after','all_original_bytes_verified']}))
