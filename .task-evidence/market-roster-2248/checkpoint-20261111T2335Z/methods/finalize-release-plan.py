"""Finalize the existing two-phase Actions publisher from verified exact-source originals."""
from pathlib import Path
import json,hashlib,shutil
B=Path('/workspace/2248-market-needs-final');P=Path('/workspace/dtos-publisher-2248');s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());recovery=json.loads((B/'recovery-verified.json').read_text());prior=json.loads((B/'prior-package-complete.json').read_text());products=json.loads((B/'product-test-counts.json').read_text());release=json.loads((B/'release-draft-created.json').read_text());runs=json.loads((B/'validation-runs.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and recovery['passed'];assert local['tests']==host['tests']==4399 and products['total']==896
assert all(x['candidate']==s['candidate'] and x['tree']==s['tree'] for x in [local,host,native,runs]);assert release['draft'] and release['tag_name']=='v'+s['version'] and release['target_commitish']==s['candidate']
parts=[]
with (B/'recovery-package.zip').open('rb') as source:
 i=0
 while raw:=source.read(64*1024**2):
  i+=1;assert i<=4;name=f'.github/release-plans/2248-recovery-{i:03}.part';path=P/name;assert not path.exists();path.write_bytes(raw);parts.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
assert ''.join('x' for _ in parts)
p=P/'.github/release-plans/2248-prior.zip';assert not p.exists();shutil.copyfile(B/'prior-package.zip',p);assert hashlib.sha256(p.read_bytes()).hexdigest()==prior['sha256']
plan=dict(schema=1,repository='Richarddavis47/dtos',actor='Richarddavis47',publisher_ref='refs/heads/release/2248-actions-publisher',baseline=s['baseline'],candidate=s['candidate'],tree=s['tree'],pr=s['pr'],source_branch=s['branch'],version=s['version'],build=s['build'],draft_id=release['id'],prior_immutable_tag='v1.22.32',canonical_tests=4399,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],product_tests=products['total'],python_version='3.14.3',capital_tests=14,market_roster_tests=21,recovery_file='.github/release-plans/2248-recovery.zip',recovery_sha256=recovery['sha256'],recovery_parts=parts,prior_evidence_file='.github/release-plans/2248-prior.zip',prior_evidence_sha256=prior['sha256'],runs=runs['runs'],artifacts=json.loads((B/'artifact-download-queue.json').read_text()),prior_runs=[43104967523,43104967492,43104967536,43104967541],prior_jobs=[130805795739,130805794693,130805794782],prior_attempts=[],finalized=True)
(P/'.github/release-plans/2248.json').write_text(json.dumps(plan,indent=2)+'\n');(B/'final-release-plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],draft_id=release['id'],recovery_parts=parts,finalized=True)))
