"""Seal existing prior bytes; they never substitute for final validation."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');m=json.loads((b/'source.json').read_text());files={}
for p in b.glob('superseded-*.json'):files['superseded-metadata/'+p.name]=p
for p in b.glob('resident-host-prior-*'):
 if p.is_file():files['hosted-resource-failure/'+p.name]=p
for p in (b/'prior-hosted-originals').glob('*.zip'):files['original-hosted-archives/'+p.name]=p
for folder in ['prior-local-canonical-509-cancelled','prior-local-checkout-generated-validation']:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[folder+'/'+str(p.relative_to(b/folder))]=p
for pattern in ['publisher-*-prior-*.log','publisher-tests-prior*.log']:
 for p in b.glob(pattern):files['publisher-prior/'+p.name]=p
for pattern in ['baseline-ownership-immediate-close-assertion.*','baseline-ownership-incomplete-fixture.*','incomplete-generation-fixture-*','memory-*-missing-generation.log','resource-tool-lint-before-format.log','regression-before-fix.log']:
 for p in r.glob(pattern):
  if p.is_file():files['source-and-fixture-prior/'+p.name]=p
note=b/'PRIOR_ATTEMPTS.md';note.write_text('''# Prior attempts, not final acceptance

Before-fix ownership controls:5 failures/2passes establish the bug. Incomplete asyncio test proxy and premature immediate-close assertion are fixture/setup errors; corrected controls allow event-loop cleanup. Missing fixture league display-name initialization caused a setupKeyError and dependent missing-file attempts; originals are retained. Ruff formatting/cache errors and a publisher fixture's obsolete twelve-job expectation were corrected without dropping assertions.

The first final-source509resource control passed locally on Python3.14, but hosted Python3.12 correctly deferred after old owner release. Logical release did not immediately free enough allocator pages; the fixture incorrectly assumed it did. Final108explicitly relieves only fixture-owned pressure and checks actual capacity before real execution. Product memory policy is unchanged. The failed hostedZIP and decoded original job log remain intact; no missing checksum sidecar is fabricated for that failed run.

Superseded509localcanonical and two hosted workflows were deliberately cancelled after this known focused failure. Two other509hosted workflows completed successfully, but are not used as final108acceptance. Local interrupted result is incomplete, not a passing full regression. Original trace/console and generated-validation records remain distinguishable. A first clean-checkout setup failed the existing8GiB scratch prerequisite before starting canonical; its command/AssertionError remain in the task transcript, with this note as an account rather than a reconstructed original log. Only final108runs establish release gates.

An earlier509focused invocation mistakenly set a transcribed expected-head environment string. Unit tests did not use that variable to establish checkout identity. It is not relied upon: subsequent exact509and final108scopes passed, with separate source receipts. Matched full-lifecycle measurements were on509with a byte-identical product function in108; they are separately source-associated, not relabeled as108executions.

Download transport failures from the old hostGitHubCLI (unsupported log flag and forbidden signed redirect) are not application test failures. The existing GitHub connector retrieved the original hosted artifact with exact API SHA256; temporary download URLs and signatures are not published. No credentials were changed or bypassed.

All artifacts here are synthetic/source-validation evidence. Earlier release/study originals remain unchanged at their immutable published locations. No historical production payload or recovered original log has been fabricated.
''')
files['PRIOR_ATTEMPTS.md']=note
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
rows=[]
for n,p in sorted(files.items()):
 data=p.read_bytes();assert not secret.search(data),n;rows.append(dict(name=n,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
out=Path('/workspace/dtos-publisher-2238/.github/release-plans/2238-prior.zip')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,p in sorted(files.items()):z.write(p,n)
 z.writestr('prior-manifest.json',json.dumps(dict(candidate=m['candidate'],tree=m['tree'],scope='prior-attempts-only',files=rows),indent=2)+'\n')
with zipfile.ZipFile(out) as z:assert z.testzip() is None
(b/'prior-package.json').write_text(json.dumps(dict(files=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest()),indent=2)+'\n');print('Preserved',len(rows),'prior files')
