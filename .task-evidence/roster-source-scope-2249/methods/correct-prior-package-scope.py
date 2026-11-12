"""Correct one unpublished container's schema label; retain original evidence bytes."""
from pathlib import Path
import json,hashlib,zipfile,importlib.util,datetime
B=Path(__file__).resolve().parent;s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());assert local['all_local_gates_passed'] and local['tests']==4419
old=B/'prior-package.zip';record=json.loads((B/'prior-package-complete.json').read_text());oldsha=hashlib.file_digest(old.open('rb'),'sha256').hexdigest();assert oldsha==record['sha256']=='764f8050e7780681a731842070abb1d5e475f8cd7e5a86a7b46148e82e51cfa9'
spec=importlib.util.spec_from_file_location('unchanged_prior_guard','/workspace/dtos-publisher-2249/tools/release/publish.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
try:g.verify_prior_evidence(old,dict(s,prior_evidence_sha256=oldsha))
except RuntimeError as exc:
 assert str(exc)=='Prior evidence association mismatch';before=dict(passed=False,error=str(exc),scope='Packaging metadata only; original test records remain unchanged')
else:raise AssertionError('Expected inspected original schema mismatch not reproduced')
with zipfile.ZipFile(old) as z:
 assert z.testzip() is None;files={n:z.read(n) for n in z.namelist()};oldmeta=files['prior-manifest.json'];m=json.loads(oldmeta);assert m['scope']=='Prior/superseded attempts only; no finalpass claim';m['scope']='prior-attempts-only';files['prior-manifest.json']=(json.dumps(m,indent=2)+'\n').encode()
new=B/'prior-package-scope-corrected.zip';assert not new.exists()
with zipfile.ZipFile(new,'x',zipfile.ZIP_LZMA) as z:
 for name,raw in files.items():z.writestr(name,raw)
with zipfile.ZipFile(new) as a,zipfile.ZipFile(old) as b:
 assert a.testzip() is None and a.namelist()==b.namelist()
 for name in a.namelist():
  if name!='prior-manifest.json':assert a.read(name)==b.read(name)
 assert {k:v for k,v in json.loads(a.read('prior-manifest.json')).items() if k!='scope'}=={k:v for k,v in json.loads(b.read('prior-manifest.json')).items() if k!='scope'}
sha=hashlib.file_digest(new.open('rb'),'sha256').hexdigest();g.verify_prior_evidence(new,dict(s,prior_evidence_sha256=sha));assert new.stat().st_size<100*1024**2
backup=B/'prior-package-unfinalized-scope-original.zip';assert not backup.exists();old.rename(backup);(B/'prior-package-complete.json').rename(B/'prior-package-unfinalized-scope-original.json');(B/'prior-manifest-unfinalized-scope-original.json').write_bytes(oldmeta);new.rename(old)
record.update(bytes=old.stat().st_size,sha256=sha,members=len(files),scope='prior-attempts-only; raw prior members preserved; unpublished schema-label correction separately recorded',unchanged_original_member_count=len(files)-1,prior_unfinalized_container_sha256=oldsha)
(B/'prior-package-complete.json').write_text(json.dumps(record,indent=2)+'\n');r=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),before=before,after=dict(passed=True,scope=m['scope'],bytes=record['bytes'],sha256=sha),original_container_preserved=backup.name,original_container_sha256=oldsha,original_manifest_preserved='prior-manifest-unfinalized-scope-original.json',raw_test_members_unchanged=len(files)-1,no_test_execution_or_source_change=True,publisher_guard_unchanged=True,scope='One unpublished packaging schema label corrected before any release dispatch; original failed/cancelled test records and native archives remain byte-identical.');(B/'prior-package-scope-correction.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
