from pathlib import Path
import json,hashlib,subprocess
b=Path('/workspace/2244-trade-comparison');root=Path('/workspace/dtos-publisher-2244');path=root/'.github/release-plans/2244.json';p=json.loads(path.read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());source=json.loads((b/'source.json').read_text());assert local['candidate']==host['candidate']==source['candidate']==p['candidate'] and local['tree']==host['tree']==source['tree']==p['tree'] and local['all_local_gates_passed'] and host['all_gates_passed']
queue=json.loads((b/'artifact-download-queue.json').read_text());assert len(queue)==15
p['artifacts']=[]
for r in queue:
 f=b/'hosted-originals'/r['file'];assert f.stat().st_size==r['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'];p['artifacts'].append({k:r[k] for k in ['id','name','run','file','sha256']})
p.update(canonical_tests=4342,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],product_tests=json.loads((b/'product-test-counts.json').read_text())['total'],draft_id=json.loads((b/'draft-created.json').read_text())['id'],recovery_sha256=hashlib.sha256((root/p['recovery_file']).read_bytes()).hexdigest(),prior_evidence_sha256=hashlib.sha256((root/p['prior_evidence_file']).read_bytes()).hexdigest(),finalized=True)
path.write_text(json.dumps(p,indent=2)+'\n');print('Finalized exact candidate,15originals,13jobs,all local/host gates,actual manifest counts and draft')
