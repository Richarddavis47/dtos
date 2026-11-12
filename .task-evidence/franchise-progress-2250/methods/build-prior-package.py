"""Seal observed nonfinal stages; preserve originals without reconstructing logs."""
import hashlib,json,re,zipfile,datetime
from pathlib import Path
B=Path(__file__).resolve().parent;s=json.loads((B/'source.json').read_text());files={}
notes='''# Earlier attempts and boundaries

The baseline replay ran on clean production source05c717e50b47683963ed40d66946e9f6eea76694/treec60f914d2a0b6b34c2d3e87cdce8eae4560d0b49. It establishes a retained-source customer gap, not live or exhaustive franchise coverage.

Development controls passed86 methods on an uncommitted working tree. Their original HEAD/tree were the baseline; the dirty paths are recorded. The exact working-tree contents were not sealed at every edit, so this is not final-candidate proof. Final88 controls on f40bf83/tree21b31e05 are separate.

The first publisher control run executed141 methods with3 subtest errors in the existing collector-wiring fixture: it intentionally supplied a noncanonical placeholder ZIP and mocked older independent guards, but did not yet mock the new family guard. The original console is preserved. The failed publisher working tree was not committed or byte-sealed before formatting; its exact original source snapshot is unavailable. The diagnosis is supported by the original traceback and the final one-line fixture correction; no reconstructed source or log is described as original. Real release collection still executes the new guards, which have independent positive/negative tests. Corrected141-method consoles remain distinct, including the later version with clearer attachment naming and validation receipt fields.

A newly created --no-checkout publisher worktree initially had an empty index. Its four new tooling files were preserved before index initialization. The controller was then aligned to production application bytes, as required by the existing allowlist; the application feature worktree/commit were never reset. Tooling and metadata probes (including a missing global Ruff module) were not application gates. Existing repository Ruff completed successfully. No credentials, source policy or production data changed.

No mandatory application validation was failed, cancelled or skipped at the time of this prior-stage seal. Running local/hosted validation is not passing evidence. Any later failed/cancelled attempt must be separately retained and incorporated before publication. Older releases' immutable evidence remains untouched.
'''
files['PRIOR_ATTEMPTS.md']=notes.encode();(B/'PRIOR_ATTEMPTS.md').write_text(notes)
for name in ['baseline-probe-original.log','baseline-probe-invocation.json','baseline-probe.py','baseline-probe.json','focus-working-invocation.json','focus-working-runner.py','publisher-controls-original.log','publisher-controls-final-original.log','publisher-controls-2-original.log','publisher-controls-reconciled.json','publisher-format-original.log','publisher-format-2-original.log','publisher-ruff-original.log','publisher-ruff-2-original.log','publisher-base-alignment.json']:
 p=B/name;assert p.is_file(),name;files[name]=p.read_bytes()
for folder in ['focus-working','publisher-bootstrap-preserved']:
 for p in sorted((B/folder).rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:files[folder+'/'+str(p.relative_to(B/folder))]=p.read_bytes()
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')
for n,raw in files.items():
 if Path(n).suffix not in ['.png','.zip']:assert not pattern.search(raw),n
rows=[dict(name=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(files.items())]
files['prior-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='prior-attempts-only',files=rows),indent=2)+'\n').encode();p=B/'prior-package.zip';assert not p.exists()
with zipfile.ZipFile(p,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,raw in sorted(files.items()):z.writestr(n,raw)
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 for r in rows:raw=z.read(r['name']);assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
r=dict(source=s,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),members=len(files),scope='prior-attempts-only',sealed_at=datetime.datetime.now(datetime.timezone.utc).isoformat());(B/'prior-package-complete.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
