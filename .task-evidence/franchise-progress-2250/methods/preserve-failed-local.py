"""Preserve actual failed/cancelled originals before reclaiming a stopped test container."""
import collections,datetime,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
B=Path(__file__).resolve().parent;source=json.loads((B/'source.json').read_text());c=json.loads((B/'canonical-invocation.json').read_text())['container'];r=json.loads(subprocess.check_output(['docker','inspect',c],text=True))[0];state=r['State'];assert not state['Running'] and state['Pid']==0 and state['ExitCode']!=0 and not state['OOMKilled']
root=B/'prior-local-f40';root.mkdir();names=['canonical-invocation.json','canonical-launch-original.log','canonical-runner-extraction.json','local-responsiveness-failure.json','local-cancellation-invocation.json','local-failed-container-state-original.json','local-failed-container-console-original.log','local-failed-manifest-verified.json','responsiveness-failure-original-excerpt.log','local-completion-observer.json','local-completion-observer-original.log']
for name in names:
 p=B/name
 if p.exists():shutil.copyfile(p,root/name)
with (root/'docker-diff-original.log').open('xb') as f:subprocess.run(['docker','diff',c],stdout=f,stderr=subprocess.STDOUT,check=True)
original=B/'local-canonical';manifest=json.loads((original/'manifest.json').read_text())
for row in manifest:
 p=original/row['name'];assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
shutil.move(str(original),str(root/'local-canonical'))
# Keep original fixture inputs locally; never include their databases/cache in public evidence.
shutil.move(str(B/'fixture'),str(root/'fixture'))
rows=[json.loads(x) for x in (root/'local-canonical/tests.jsonl').read_text().splitlines()];counts=dict(collections.Counter(x['event'] for x in rows));trace=[json.loads(x) for x in (root/'local-canonical/canonical-trace.jsonl').read_text().splitlines()];gates=[x for x in trace if x.get('event')=='validation_child_completed']
record=dict(source=source,status='FAILED_RESPONSIVENESS_THEN_INTERRUPTED_REMAINDER',events=counts,planned_methods=4435,gate_results=[dict(name=x.get('gate') or x.get('name'),return_code=x['return_code']) for x in gates],gate_count_recorded=len(gates),unexecuted_gate_count=10-len(gates),normal_completion=False,normal_worker_cleanup_claim=False,actual_container_state=state,original_manifest_entries=len(manifest),original_manifest_bytes_verified=True,original_mount_path=str(B/'local-canonical'),preserved_path=str(root/'local-canonical'),fixture_inputs_preserved_locally=True,production_unchanged=True,recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
(root/'RECONCILIATION.json').write_text(json.dumps(record,indent=2)+'\n')
archive=B/'failed-local-f40-original.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(root.rglob('*')):
  if p.is_file() and 'fixture' not in p.relative_to(root).parts and '__pycache__' not in p.parts:z.write(p,str(p.relative_to(root)))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for p in sorted(root.rglob('*')):
  if p.is_file() and 'fixture' not in p.relative_to(root).parts and '__pycache__' not in p.parts:assert z.read(str(p.relative_to(root)))==p.read_bytes()
# Original output and fixture volumes persist; remove only this stopped disposable runtime copy.
subprocess.run(['docker','rm',c],check=True,stdout=subprocess.DEVNULL)
assert not subprocess.check_output(['docker','ps','-a','--filter','id='+c,'--format','{{.ID}}'],text=True).strip()
record.update(stopped_container_removed_after_original_byte_verification=True,container_absent_after=True,archive_bytes=archive.stat().st_size,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest());(B/'failed-local-reconciled.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['status','events','gate_count_recorded','unexecuted_gate_count','archive_bytes','archive_sha256','container_absent_after']}))
