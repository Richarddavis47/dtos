"""Preserve original attempts separately; none substitutes for final-source gates."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2235-restoration');m=json.loads((b/'source.json').read_text());files={}
for p in (b/'prior-attempts').rglob('*'):
 if p.is_file():files['prior-attempts/'+str(p.relative_to(b/'prior-attempts'))]=p.read_bytes()
for name in ['focused-first.log','focused-corrected.log','focused-final.log','focused-final-corrected.log','publisher-initial.log','lint-first.log','product-artifact-integrity.log']:
 if (b/name).is_file():files['earlier-controls/'+name]=(b/name).read_bytes()
files['README.md']=b'''# Original earlier attempts, not final acceptance\n\nThis archive belongs to the build2235 candidate/tree in prior-manifest.json. It preserves fixture-envelope and roster-schema setup errors from the first baseline probe, the first resource run that stopped at an overbroad no-child assertion (Python resource tracker), a mistyped focused module name, read-only Ruff-cache setup, the unchanged8GiB local scratch prerequisite and the publisher's positive-plan fixture missing the newly required recovery artifact. The first focused run included imported legacy TestCase methods twice; it is not the final count. Later final controls use the isolated fixture import and69tests on the exact clean candidate. The first Product artifact verifier printed an old eight-artifact label despite actually verifying nine rows; its JSON and final dynamic count resolve the presentation error without altering original artifact bytes.\n\nThe matched baseline control is separate in the final recovery evidence: its candidate-oriented script intentionally exits nonzero on the old source's expected HeavyWorkDeferred. It is not called a passing completion test or a failure of the final source. No deferred operation counts as execution. Original partial/superseded logs remain unchanged. No old publication or immutable historical record is replaced. Prior study evidence remains separately sealed at the referenced original public commit/checksum; it is not rerun or upgraded from PARTIAL.\n'''
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
for name,data in files.items():assert not pattern.search(data),name
rows=[dict(name=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest()) for n,d in sorted(files.items())]
files['prior-manifest.json']=json.dumps(dict(candidate=m['candidate'],tree=m['tree'],scope='prior-attempts-only',files=rows),indent=2).encode()+b'\n'
out=Path('/workspace/dtos-publisher-2235/.github/release-plans/2235-prior.zip');assert not out.exists()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,d in sorted(files.items()):z.writestr(n,d)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
(b/'package-prior-report.json').write_text(json.dumps(dict(bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),entries=len(rows),scope='prior-attempts-only'),indent=2)+'\n')
print('Preserved',len(rows),'earlier original payloads')
