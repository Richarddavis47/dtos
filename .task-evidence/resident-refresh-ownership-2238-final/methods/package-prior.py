"""Seal existing prior bytes; they never substitute for final validation."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');m=json.loads((b/'source.json').read_text());files={}
for p in b.glob('superseded-*.json'):files['superseded-metadata/'+p.name]=p
for p in b.glob('superseded-generated-*.zip'):files['superseded-generated-originals/'+p.name]=p
for p in b.glob('invocation-superseded-*.json'):files['superseded-invocations/'+p.name]=p
files['source-and-fixture-prior/global-owner-before-fix.log']=b/'global-owner-before-fix.log'
for name in ['prior-108-product-original-decoded.log','prior-108-product-log-receipt.json','resident-host-prior-108-verified.json']:
 files['superseded-successes/'+name]=b/name
for pattern in ['global-owner-memory-prior-*.py','global-memory-*-prior-*.log']:
 for p in r.glob(pattern):files['source-and-fixture-prior/'+p.name]=p
for p in b.glob('resident-host-prior-*'):
 if p.is_file():files['hosted-resource-failure/'+p.name]=p
for p in (b/'prior-hosted-originals').glob('*.zip'):files['original-hosted-archives/'+p.name]=p
for folder in ['prior-local-canonical-509-cancelled','prior-local-canonical-108-cancelled','prior-local-checkout-generated-validation']:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[folder+'/'+str(p.relative_to(b/folder))]=p
for pattern in ['publisher-*-prior-*.log','publisher-tests-prior*.log']:
 for p in b.glob(pattern):files['publisher-prior/'+p.name]=p
for pattern in ['baseline-ownership-immediate-close-assertion.*','baseline-ownership-incomplete-fixture.*','incomplete-generation-fixture-*','memory-*-missing-generation.log','resource-tool-lint-before-format.log','regression-before-fix.log']:
 for p in r.glob(pattern):
  if p.is_file():files['source-and-fixture-prior/'+p.name]=p
for n in ['superseded-0a4-hosted-records.json','prior-0a4-public-readback.json','host-0a4-attempt1-timeout-analysis.json','canonical-0a4-attempt1-original-decoded.log','prior-0a4-local-verified.json','prior-0a4-invocation-final.json','prior-console-parts-retirement.json','focused-final-49.log','workflow-final-49-lint-prior-check-format.log','hosted-live-log-access.json','checkpoint-0a4-metadata-correction.json','verify-precano-originals-prior-return-shape.py','publisher-lint-final49-prior-host-missing-module.log','REPORT-before-final-gates.md']:
 files['prior-0a4-and-ci/'+n]=b/n
for n in ['result.json','manifest.json','SHA256SUMS','canonical.log','canonical-trace.jsonl','unittest-console.log','tests.jsonl','memory.jsonl']:
 files['prior-local-canonical-0a4-pass/'+n]=b/'prior-local-canonical-0a4-pass'/n
# Full failed original ZIP and readable fragments are independently published
# and read back. Keep the verified immutable pointer instead of nesting an
# additional78MiB ZIP into the existing63MiB archive (Git file-size bound).
note=b/'PRIOR_ATTEMPTS.md';note.write_text('''# Prior attempts, not final acceptance

Before-fix ownership controls:5 failures/2passes establish the bug. Incomplete asyncio test proxy and premature immediate-close assertion are fixture/setup errors; corrected controls allow event-loop cleanup. Missing fixture league display-name initialization caused a setupKeyError and dependent missing-file attempts; originals are retained. Ruff formatting/cache errors and a publisher fixture's obsolete twelve-job expectation were corrected without dropping assertions.

The first final-source509resource control passed locally on Python3.14, but hosted Python3.12 correctly deferred after old owner release. Logical release did not immediately free enough allocator pages; the fixture incorrectly assumed it did. The final resource fixture explicitly relieves only fixture-owned pressure and checks actual capacity before real execution. Product memory policy is unchanged. The failed hostedZIP and decoded original job log remain intact; no missing checksum sidecar is fabricated for that failed run.

Superseded509localcanonical and two hosted workflows were deliberately cancelled after this known focused failure. Two other509hosted workflows completed successfully, but are not used as final108acceptance. Local interrupted result is incomplete, not a passing full regression. Original trace/console and generated-validation records remain distinguishable. A first clean-checkout setup failed the existing8GiB scratch prerequisite before starting canonical; its command/AssertionError remain in the task transcript, with this note as an account rather than a reconstructed original log. Final108then exposed a separate source-backed global scheduler owner. Its local/hosted canonical runs were deliberately cancelled; its Product workflow had already completed successfully. Each actual outcome is preserved separately and none substitutes for final0a4gates. Final0a4adds the scalar-only global owner fix and must establish every final gate. Four global methods reproduce six failing scenarios before correction. A first global profiling harness kept its own cancelled task reference; its original script/log remain retained, and final controls drop that harness owner and settle before asserting cleanup.

An earlier509focused invocation mistakenly set a transcribed expected-head environment string. Unit tests did not use that variable to establish checkout identity. It is not relied upon: subsequent exact509and final108scopes passed, with separate source receipts. Matched full-lifecycle measurements were on509with a byte-identical product function in108; they are separately source-associated, not relabeled as108executions.

Download transport failures from the old hostGitHubCLI (unsupported log flag and forbidden signed redirect) are not application test failures. The existing GitHub connector retrieved the original hosted artifact with exact API SHA256; temporary download URLs and signatures are not published. No credentials were changed or bypassed.

All artifacts here are synthetic/source-validation evidence. Earlier release/study originals remain unchanged at their immutable published locations. The first509Docker invocationJSON was overwritten before it was separately copied; it is unavailable unchanged. Source-bound result, console, test/memory events and trace remain. No reconstructed original log is supplied. The108invocation was preserved before cancellation. Historical production payloads and logs are not fabricated.
''')
with note.open('a') as f:f.write('''

Final application source0a4 completed the local4261tests/allten gates. Its hosted canonical run42327699300 failed at4200s after4116complete/4117started tests, zero testfailures/errors/skips/OOM. Six gates completed; regression interrupted and three later gates did not execute. The last test was making normal admitted HTTP200progress. Original artifact13557519899 (78,533,715bytes, SHA732955933c685fad1c94cbfbd4a41a76915ad46d10471866df306275127552c4) and all readable original logs are preserved at the exact verified public location in prior-0a4-public-readback.json. The12other hosted jobs passed on0a4; they remain prior evidence. Matched tests of at least1local second ran median1.657x local; exact hardware/load cause is unknown. Final49changes only CI's validator allowance4200->4500s and bounded step/job artifact margins. It changes no application timeout, memory/reserve, test assertion or appcode. All final49mandatory workflows and local canonical must pass separately.

A first final49focused invocation added tooling tests to a read-only source mount; one tooling fixture correctly could not create a temporary checkout. The original123test/one-error console remains. The same123methods pass in the clean writable49checkout. An ad-hoc YAML verification incorrectly expected GNU --memory=2g rather than the unchanged workflow's --memory 2g form; its original assertion is retained and the correct structural check passes. These are harness checks, not application defects or waived assertions. Source logs and methodology remain original. An ad-hoc archive receipt collector initially expected every strict publisher helper to return a passed key; browser helpers instead return their original checked browser report. Its original helper script is retained. The unchanged strict browser guards assert source, exact rows, errors and screenshots internally; the corrected collector calls those guards without inventing a missing field. A host-only lint invocation lacked Ruff; its original missing-module log is retained and the unchanged lint passed in the established runtime. The first prior-archive public inventory excluded nested original manifest/SHA names; the two inventory rows were added without changing original payloads, both commits remain immutable, and all222publishedpayloads were read back. These packaging issues did not alter an application test or guard. An initial final49canonical launch failed the existing8GiB disk prerequisite before starting tests. Its launch-log path was reused for the successful launch before a separate copy was kept; that initial original console is unavailable unchanged. The task transcript retains the command, measuredfree8,481,259,520bytes versusrequired8,589,934,592and exit1. No original log is reconstructed. Exact-byte historical duplicate retirement and a subsequent passing prerequisite are recorded; the mandatory run starts from the clean final49source.
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
assert out.stat().st_size<100*1024**2
(b/'prior-package.json').write_text(json.dumps(dict(files=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest()),indent=2)+'\n');print('Preserved',len(rows),'prior files')
