from pathlib import Path
import json,hashlib,zipfile
b=Path('/workspace/2236-actuals-restoration');m=json.loads((b/'source.json').read_text());meta=json.loads((b/'lifecycle-artifact-metadata.json').read_text());out=[]
for a in meta['artifacts']:
 p=b/'hosted-originals'/(a['name']+'.zip')
 assert a['workflow_run']['head_sha']==m['candidate'] and not a['expired']
 assert p.stat().st_size==a['size_in_bytes'] and 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()==a['digest']
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  row=json.loads(z.read('summary.json'))
  assert row['completed'] and row['passed'] and row['exit_code']==0
  assert row['memory_max']==2147483648 and row['container_restart_count']==0 and not row['errors']
  out.append(dict(artifact=a,summary=row,original_bytes_verified=True))
(b/'lifecycle-verified.json').write_text(json.dumps(out,indent=2)+'\n')
print('Three exact-source lifecycle artifacts passed with enforced2GiB, no restart and verified original SHA256/CRC.')
