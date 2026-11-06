from pathlib import Path
import json,hashlib,zipfile,re
b=Path('/workspace/2233-release');m=json.loads((b/'source.json').read_text());files={}
for root,prefix in [(Path('/workspace/current-season-production'),'investigation'),(b/'prior-candidate-9772b2c','superseded-9772b2c'),(b/'prior-candidate-fb99f19','superseded-fb99f19'),(b/'prior-candidate-fa852ce','superseded-fa852ce')]:
 for p in sorted(root.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:
   files[prefix+'/'+str(p.relative_to(root))]=p.read_bytes()
for name in ['first-hosted-projection-failure.decoded.log','first-local-stop.log','second-local-stop.log','third-local-stop.log','before-after-initial.log','before-after-import-context.log','prior-hosted-status-final.json','fullback-qualification-before.log','focused-final-qualification.log','lint-final-qualification.log','retired-publisher-2227.json','bytecode-cleanup-before-final.json','focused-phone-correction.log','lint-phone-correction.log','projection-cross-version-corrected.log','focused-route-correction.log','lint-route-correction.log','publisher-focused.log','publisher-lint.log','publisher-focused-corrected.log','publisher-lint-corrected.log']:
 if (b/name).exists():files['prior-controls/'+name]=(b/name).read_bytes()
files['README.md']=b'''# Original prior attempts, not final mandatory acceptance

The source baseline was500d985d2f31c97680370a616a9303c47d60ca7f. Investigation logs include matched pre-fix failures, missing-stat controls, fixture setup mistakes, incorrect test-module names, API-shape/import corrections, and corrected focused results. Most were uncommitted working source; their passing counts are not exact-final-source mandatory gates.

Superseded candidate9772b2cac94d6731e70368427af80ea7bc5deb05/tree71f1182e4d01950d7b9a36ef78884e786628a641passed28focused tests but its hosted projection cross-version route failed because a fixture context lacked state. The route now uses its existing request-scoped state mapping. The old local full run was deliberately cancelled and has no final result.json; its retained console/events are incomplete, never counted as a pass. Outdated hosted runs were cancelled where still active; completed prior tooling/lifecycle successes are preserved but not reused for final-source acceptance. The decoded hosted failure log is connector-decoded text, not the raw canonical console. A later fb99f19 candidate was superseded after visual review found compressed phone columns. Its interrupted full run and original screenshots remain separate. The final candidate adds a bounded scrollable table and actual rendered-width assertion; no scoring or resource guard changed.

Publisher controls initially omitted the new artifact in the positive-plan fixture. The guard correctly rejected it; the fixture was updated and all44guards passed. A sparse publisher checkout lacked root Ruff configuration; use of the exact existing config revealed11new one-line compound statements, reformatted without relaxing rules. Read-only Ruff initially refused a cache write; final --no-cache preserved source. The host .venv path did not exist; actual tests ran non-root in the established2GiBcontainer. These attempts remain distinct, not erased or converted to passes.

Scratch recovery removed only explicitly inventoried redundant published copies/decoded copies and completed duplicate source checkouts with preserved Git objects. Unique original logs, canonical artifacts and current source were retained. Source deletion-only static states were recorded before safe sparse normalization and checkout retirement. No production settings or data changed.

Public league configuration/schema evidence is distinct from MainChat's supplied private observation. No real private roster cache is included, no authenticated live production recovery is claimed, and no old outcome is reconstructed from current values.
'''
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
for n,d in files.items():
 if Path(n).suffix in {'.log','.json','.jsonl','.md','.txt','.py','.patch'}:assert not pattern.search(d),n
rows=[{'name':n,'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()} for n,d in sorted(files.items())]
files['prior-manifest.json']=json.dumps({'candidate':m['candidate'],'tree':m['tree'],'scope':'prior-attempts-only','files':rows},indent=2).encode()+b'\n'
out=Path('/workspace/dtos-publisher-2233/.github/release-plans/2233-prior.zip');assert not out.exists()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,d in sorted(files.items()):z.writestr(n,d)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
(b/'package-prior-report.json').write_text(json.dumps({'archive':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'payloads':len(rows),'scope':'prior-attempts-only'},indent=2)+'\n')
print('Original prior payloads',len(rows),'archive bytes',out.stat().st_size)
