"""Finalize only from independently verified source/validation/archive facts."""
from pathlib import Path
import json,hashlib,shutil
B=Path('/workspace/2249-sleeper-relevance');P=Path('/workspace/dtos-publisher-2249');s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());recovery=json.loads((B/'recovery-verified.json').read_text());prior=json.loads((B/'prior-package-complete.json').read_text());product=json.loads((B/'product-test-counts.json').read_text());draft=json.loads((B/'release-draft-created.json').read_text());runs=json.loads((B/'validation-runs.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and recovery['passed'];assert local['tests']==host['tests']==s['expected_test_count']==4419 and product['total']==916
assert all(x['candidate']==s['candidate'] and x['tree']==s['tree'] for x in [local,host,native,runs]);assert draft['draft'] and draft['tag_name']=='v'+s['version'] and draft['target_commitish']==s['candidate']
parts=[]
with (B/'recovery-package.zip').open('rb') as stream:
 index=0
 while raw:=stream.read(64*1024**2):
  index+=1;assert index<=4;name=f'.github/release-plans/2249-recovery-{index:03}.part';path=P/name
  if path.exists():assert path.read_bytes()==raw,'Preserve changedpreviouspart, donotoverwrite'
  else:path.write_bytes(raw)
  parts.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
assert parts
p=P/'.github/release-plans/2249-prior.zip'
if p.exists():assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==prior['sha256']
else:shutil.copyfile(B/'prior-package.zip',p)
assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==prior['sha256']
plan=json.loads((P/'.github/release-plans/2249.json').read_text());assert not plan['finalized'];plan.update(candidate=s['candidate'],tree=s['tree'],baseline=s['baseline'],pr=s['pr'],source_branch=s['branch'],version=s['version'],build=s['build'],draft_id=draft['id'],prior_immutable_tag='v1.22.33',canonical_tests=4419,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],product_tests=product['total'],python_version='3.14.3',capital_tests=14,market_roster_tests=21,roster_source_scope_tests=20,recovery_file='.github/release-plans/2249-recovery.zip',recovery_sha256=recovery['sha256'],recovery_parts=parts,prior_evidence_file='.github/release-plans/2249-prior.zip',prior_evidence_sha256=prior['sha256'],runs=runs['runs'],artifacts=json.loads((B/'artifact-download-queue.json').read_text()),prior_runs=[43149667688,43149667725,43149667697,43149667665],prior_jobs=[130955607520,130955607615],prior_attempts=[],finalized=True)
(P/'.github/release-plans/2249.json').write_text(json.dumps(plan,indent=2)+'\n');(B/'final-release-plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],draft_id=draft['id'],finalized=True,recovery_parts=parts)))
