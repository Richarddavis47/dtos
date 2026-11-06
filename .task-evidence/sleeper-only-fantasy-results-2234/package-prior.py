"""Preserve source-associated original failures; never count them as final acceptance."""
from pathlib import Path
import json,hashlib,zipfile,re
b=Path('/workspace/2234-release');m=json.loads((b/'source.json').read_text());files={}
for root in sorted(b.glob('prior-*')):
 if not root.is_dir():continue
 for p in sorted(root.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts and 'fixture' not in p.parts and 'hosted-originals' not in p.parts and p.name!='prior-checkout-ignored-state.zip':files[str(p.relative_to(b))]=p.read_bytes()
for name in ['prior-hosted-status-final.json','timestamp-token-focused.log','publisher-focused.log','publisher-focused-staged.log','gather-prior.py','gather-prior.log','additional-final.log','clock-and-readiness-focused.log','clock-provenance-focused.log','fixture-and-alert-focused.log','fixture-coherence-focused.log','focused-final-after-restoration.log','focused-final.log','focused-release.log','history-actual-contract-focused.log','history-denominator-controls.log','history-denominator-final.log','ruff-clock.log','ruff-final-review.log','ruff-final.log','ruff-fixture-correction.log','ruff-history-contract.log','ruff-unit-consistency.log','unit-consistency-final.log','unit-consistency-focused.log']:
 if (b/name).exists():files['prior-controls/'+name]=(b/name).read_bytes()
files['README.md']=b'''# Original earlier attempts, separate from final-source acceptance

Baseline38f23ecc607d38d986af5c1c20ae57fffeb8f827/build2233. Each superseded candidate has its original source identity/patch and focused or incomplete full-run evidence. No superseded result is substituted for final mandatory acceptance. The89cc local full run completed4216 tests with1failure: an unqualified6.31 substring matched a capture timestamp09:46:56.318Z. The full visible score was correctly unavailable. Final source corrects whole-numeric-token matching and retains every withholding assertion. Its later unexecuted gates remain unexecuted. The original partial/failing consoles and manifests are unchanged.

The initial781 source had a hosted historical-source failure:12 assertions in278tests after fixtures changed only the player-map score while leaving contradictory ordered starter scores. The new shared integrity guard correctly withheld those conflicts. Fixtures now update both explicit fields together where they intend coherent evidence; conflicting-field tests remain separate. Its workflow is canceled overall but the failed job remains failure. Superseded local full runs were deliberately interrupted; KeyboardInterrupt or absent final records are not passing completion. d65 had focused controls but no local full run was started.

Other original controls include initial source-contract assertion changes, fixture/import/module-name setup errors, nested asynchronous fixture setup, labels/units/history observation denominators, read-only Ruff cache context and staged publisher missing-plan/positive-fixture setup. They remain distinct from final source gates.44publisher controls pass against the explicitly unfinalized staged plan; final publisher admission also rejects such a plan until complete verified evidence is pinned.

One original hosted failure is retained as explicitly connector-decoded text, with its exact decoding/transport receipt; it is not claimed to be originalZIPbytes. Successful prior hosted ZIPs are retained unchanged locally and on their original Actions records, with metadata/checksum receipts here, but are not duplicated inside this archive. Original failed local consoles and all their diagnostic payloads remain included. Workflow and job conclusions are separately recorded, including failures, cancellations and skipped jobs. The standard Actions publisher separately retains raw original Product/failure job bytes.

Private disposable fixture databases, ignored scratch-state archives and real private rosters/credentials are not included. Those local scratch originals are retained locally, not deleted. No live owner production workload, preference or source mutation was performed.\n'''
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
for n,d in files.items():
 if Path(n).suffix in {'.log','.json','.jsonl','.md','.txt','.py','.patch','.html','.js'}:assert not pattern.search(d),n
rows=[{'name':n,'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()} for n,d in sorted(files.items())]
files['prior-manifest.json']=json.dumps({'candidate':m['candidate'],'tree':m['tree'],'scope':'prior-attempts-only','files':rows},indent=2).encode()+b'\n'
out=Path('/workspace/dtos-publisher-2234/.github/release-plans/2234-prior.zip');assert not out.exists()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,d in sorted(files.items()):z.writestr(n,d)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
(b/'package-prior-report.json').write_text(json.dumps({'archive':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'payloads':len(rows),'scope':'prior-attempts-only'},indent=2)+'\n')
print('Original prior payloads',len(rows),'archive bytes',out.stat().st_size)
