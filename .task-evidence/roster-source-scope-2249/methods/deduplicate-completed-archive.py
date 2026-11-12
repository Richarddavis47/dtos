"""Deduplicate only the newly-created packaging container, preserving all originals."""
from pathlib import Path
import json,hashlib,zipfile,datetime,shutil
B=Path('/workspace/2249-sleeper-relevance');r=json.loads((B/'completed-archival-verified.json').read_text());old=Path(r['archive']);assert hashlib.file_digest(old.open('rb'),'sha256').hexdigest()==r['archive_sha256'];new=B/'completed-2246-originals-content-addressed.zip';assert not new.exists();by_hash={}
for row in r['files']:by_hash.setdefault(row['sha256'],row)
with zipfile.ZipFile(old) as source,zipfile.ZipFile(new,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
 for checksum,row in by_hash.items():
  raw=source.read(row['name']);assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==checksum;target.writestr('blobs/'+checksum,raw)
 target.writestr('original-member-map.json',json.dumps(dict(scope='All original member bytes are retained exactly once; repeated original paths map to the same content digest. This replaces an unpublished packaging ZIP, never an original validation artifact.',originals=r['files']),indent=2)+'\n')
with zipfile.ZipFile(new) as z:
 assert z.testzip() is None
 mapping=json.loads(z.read('original-member-map.json'))['originals'];assert mapping==r['files']
 for checksum,row in by_hash.items():
  raw=z.read('blobs/'+checksum);assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==checksum
proof=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_packaging_sha256=r['archive_sha256'],old_packaging_bytes=old.stat().st_size,new_packaging=str(new),new_packaging_bytes=new.stat().st_size,new_packaging_sha256=hashlib.file_digest(new.open('rb'),'sha256').hexdigest(),original_files=len(r['files']),unique_blobs=len(by_hash),all_original_member_bytes_verified=True,scope='Only an unpublished generated packaging container is replaced. Every original log/image/native ZIP stays byte-identical in content-addressed storage; prior immutable evidence and active source/fixtures are untouched.')
(B/'completed-archive-deduplication-before-removal.json').write_text(json.dumps(proof,indent=2)+'\n');old.unlink();proof['free_after']=shutil.disk_usage(B).free;(B/'completed-archive-deduplication-verified.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
