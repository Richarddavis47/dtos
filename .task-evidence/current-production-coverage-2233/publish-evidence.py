"""Publish a sanitized, readable handoff only after guarded release/deployment verification."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2233-release');root=Path('/workspace/current-production-handoff/.task-evidence/current-production-coverage-2233')
root.mkdir(parents=True,exist_ok=True);assert not (root/'manifest.json').exists()
m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2233/.github/release-plans/2233.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree'] and local['tests']==host['tests']==4180
assert pub['release']['immutable'] and not pub['release']['draft'] and len(pub['release']['assets'])==20 and smoke['production_ready']['deployment']['commit']==merged['merge_commit']
required=['source.json','source-integrity.json','candidate-production.patch','baseline.json','preservation.json','harness-preservation.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','focused-exact.log','commands.md','run-clean.py','run-constrained.py','invocation.json','local-console.log','local-preflight-console.log','merged-source.json','publication-verified.json','production-readonly-smoke.json','publisher-production-smoke.json','render-deployed.json','SCOUT_HANDOFF.md','package-final.py','package-final.log','package-prior.py','package-prior-report.json','finalize-plan.py','verify-host-canonical.py','verify-production.py','verify-readable-publication.py','publish-evidence.py','publisher-focused-final.log','publisher-lint-final.log','publisher-source.json','preparation-run.json','publication-run.json','prepared-publication.json','published-publication.json','preparation-certificate.zip','publication-certificate.zip','preparation-certificate-metadata.json','publication-certificate-metadata.json','checkout-reuse.json','decoded-log-transport.json','resource-verified.json','lifecycle-verified.json','offline-publication-guards.json','offline-publication-guards-final.log','before-after.json','before-after.py','before-after.log','before-after-initial.log','before-after-import-context.log','retired-publisher-2227.json','bytecode-cleanup-before-final.json','certificate-reader-correction.json','preparation-certificate-verification.log','prepared-attachment-verification.json','publication-certificate-verification.log','recovery-offline-verified.json','recovery-offline-integrity.log','product-artifact-integrity.log','verify-product-artifacts.py','publisher-compilation.log','prior-hosted-status-final.json','published-raw-joblogs-verified.json','published-raw-job-logs.zip','published-raw-joblogs-download.log']
for name in required:shutil.copyfile(b/name,root/name)
for name in ['browser-final','local-preflight','readable-console','hosted-logs']:shutil.copytree(b/name,root/name,dirs_exist_ok=True)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 dest=root/label;dest.mkdir(exist_ok=True)
 for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copyfile(source/name,dest/name)
for name in ['2233-recovery.zip','2233-prior.zip','2233.json']:shutil.copyfile(Path('/workspace/dtos-publisher-2233/.github/release-plans')/name,root/name)
with zipfile.ZipFile(root/'2233-prior.zip') as z:
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts
  p=root/'prior-originals'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
resource=root/'hosted-resource';resource.mkdir(exist_ok=True)
for name in ['current-production-coverage-browser','market-history-coverage-browser','trade-resource-2g','league-entry-2g','linux-market-lifecycle-ordinary-summary','linux-market-lifecycle-archive-warmed-summary','linux-market-lifecycle-combined-read-summary']:
 with zipfile.ZipFile(b/'hosted-originals'/(name+'.zip')) as z:
  for member in ['browser.json','result.json','summary.json']:
   if member in z.namelist():(resource/(name+'-'+member)).write_bytes(z.read(member))
# Original Actions bytes, independently retrieved from the immutable release.
with zipfile.ZipFile(b/'published-raw-job-logs.zip') as z:
 assert z.testzip() is None
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name
  dest=root/'original-product-and-prior-job-logs'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
raw_index=[]
for log in (root/'original-product-and-prior-job-logs').glob('*.log'):
 job_id=int(log.stem);found=[]
 for group in [*json.loads((b/'hosted-final-records.json').read_text()),*json.loads((b/'prior-hosted-status-final.json').read_text())]:
  for job in group['jobs']:
   if job['id']==job_id:found.append(dict(job=job_id,name=job['name'],run=group['run']['id'],source=group['run']['head_sha'],conclusion=job['conclusion'],final_candidate=group['run']['head_sha']==m['candidate'],path=str(log.relative_to(root))))
 assert len(found)==1;raw_index+=found
(root/'original-hosted-job-index.json').write_text(json.dumps(raw_index,indent=2)+'\n')
def split(source,dest,prefix):
 data=source.read_bytes();parts=[];start=0
 while start<len(data):
  end=min(start+300000,len(data))
  while end<len(data) and data[end]&0xc0==0x80:end-=1
  assert end>start
  parts.append(data[start:end]);start=end
 assert b''.join(parts)==data
 dest.mkdir(exist_ok=True)
 for i,part in enumerate(parts,1):(dest/f'{prefix}-{i:03d}.log').write_bytes(part)
 (dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(part).hexdigest()+f'  {prefix}-{i:03d}.log\n' for i,part in enumerate(parts,1)))
split(b/'host-canonical-readable/unittest-console.log',root/'readable-host-console','host-console')
for log in (root/'hosted-logs').glob('*.log'):
 if log.stat().st_size>300000:split(log,root/('readable-job-'+log.stem),'job-'+log.stem)
for log in (root/'original-product-and-prior-job-logs').glob('*.log'):
 if log.stat().st_size>300000:split(log,root/('readable-original-job-'+log.stem),'original-job-'+log.stem)
for log in (root/'prior-originals').rglob('*.log'):
 if log.stat().st_size>300000:
  label=hashlib.sha256(str(log.relative_to(root)).encode()).hexdigest()[:12];split(log,root/('readable-prior-'+label),'prior-'+label)
index=['# Readable original validation evidence','','Numbered parts concatenate byte-identically to their full original. Original canonical console bytes are distinct from explicitly labelled connector-decoded hosted job logs. Parts are bounded for independent review.','']
for folder in sorted([root/'readable-console',root/'readable-host-console',*root.glob('readable-job-*'),*root.glob('readable-original-job-*'),*root.glob('readable-prior-*')]):
 index+=['## '+folder.name,'','| Download | Bytes | SHA256 |','|---|---:|---|']
 for p in sorted(folder.glob('*.log')):index.append(f'| [{p.name}]({p.relative_to(root)}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
 index.append('')
index+=['[Full local console](original-local-canonical/unittest-console.log?raw=1) · [Full hosted console](original-host-canonical/unittest-console.log?raw=1) · [Prior attempts](prior-originals)']
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
(root/'README.md').write_text(f'''# Current-season production coverage — v1.22.18 / build 2233

The shared canonical scoring and display boundaries are corrected. Supported individual NFL observations now survive irrelevant team-defense/zero-weight requirements and supported source fields reach canonical preparation. Market and dossiers show observed weeks, coverage, qualified per-observation averages and missing fields. Genuine applicable gaps still withhold fantasy-point windows and current-production values. Career History roster totals never replace canonical production.

Released through [PR322](https://github.com/Richarddavis47/dtos/pull/322) and the [immutable release]({pub['release']['html_url']}). Candidate `{m['candidate']}`; validated tree `{m['tree']}`; deployed merge `{merged['merge_commit']}`. [Patch](candidate-production.patch), [tree reconstruction](source-integrity.json), [production smoke](production-readonly-smoke.json), [Render deployment](render-deployed.json), [attachment verification](publication-verified.json), [complete Scout prompt](SCOUT_HANDOFF.md).

## Confirmed causes and source-to-screen flow

Existing NFLverse acquisition → explicit identity/season/week facts → canonical global store → selected-league component scoring → bounded current/prior-season preparation → cache save/restore → existing valuation consumers and Market/dossier rendering. The historical scorer and reference model coefficients are unchanged. The adapter now ignores only disabled or known individual-inapplicable team-defense categories, retains supported public kicking/return/big-play fields and refuses malformed active statistics. A 40-yard play is not a long touchdown. Unknown position and NFL fullback RB-bonus classification stay unknown.

Current-season completed-week filtering uses matching authoritative NFL state. Observed records, not calendar weeks or asserted games played, form the denominator. No zero is inserted for bye/DNP/missing weeks. Component-complete observations do not establish full-season acquisition or final game status. Incomplete windows retain their counts and missing fields; partial subtotals are never complete averages. Current and previous seasons remain distinct.

A failed or partial source check no longer marks old facts newly fresh. Retained values keep their original knowledge boundary and explicit qualification. Existing failed league refreshes are separately labelled, including cached Market HTML. Old caches reuse only already-retained same-generation sample counts; absent scored counts, weeks and field diagnostics stay unknown. Newly normalized fields require the next legitimate admitted publication; no forced production refresh was performed.

## Before/after evidence and limitations

[Matched fixture results](before-after.json) compare the original baseline and corrected boundaries on the same disposable QB record. Standard offensive scoring plus required team-defense fields recovers from unavailable to 18.00 points per observation. The Granite-coefficient fixture's missing categories narrow from 29 to 2, but its fantasy average remains withheld for player st_ff/st_fum_rec. Arkham/Day coefficient fixtures likewise retain missing required fields. These are synthetic values and field-count controls, not current live player totals. Some extra fixture fields are deliberately absent even when the provider has matching columns; the table must not be read as an actual upstream population audit.

Main Chat supplied the authenticated player:4984 observation with separate 2026 roster Weeks 1–8 / 183.82. Codex did not reproduce that private request and does not claim183.82 as a canonical total. Public authoritative league settings for Granite, Arkham and Day Traders and a bounded 256,000-byte existing-provider schema sample were inspected. No private roster was exported. Remaining player special-teams, long-TD, interception-return and unproved missed-kick semantics remain genuine or qualified gaps; no new source/fallback is introduced. This NFL-player source does not establish team-DEF season production. Existing forward K/DEF projections remain independent.

## Final validation

| Evidence | Result |
|---|---|
| New exact-source production controls |28 passed; 8 viewport/scope cases and 24 screenshots|
| Local full regression |4,180 passed; all 10 canonical gates passed|
| Hosted full regression |4,180 passed; all 10 canonical gates passed|
| Required hosted jobs |12 of 12 passed|
| Main Product executions |{plan['product_tests']} passed|
| Separate publisher security/integrity controls |44 passed|
| Verified canonical manifest payloads |{local['local_manifest_entries']} local / {host['entries']} hosted|

[Original readable logs/index](LOG_INDEX.md), [original Actions Product/prior log index](original-hosted-job-index.json), [local proof](local-verified.json), [hosted proof](host-canonical-verified.json), [hosted runs/artifacts](hosted-final-records.json), [browser controls](browser-final/browser.json). Earlier baseline assertions, fixture/import/API setup errors, hosted cross-version route failure and superseded partial runs remain separately manifested in [prior-originals](prior-originals) and [2233-prior.zip](2233-prior.zip). They are not counted as final-source successes. Supplemental before/after helper import failures are separately preserved and did not change application source.

The readable canonical folders mirror the original console/trace/result files. The complete 640-payload local tree is inside 2233-recovery.zip; the complete 644-payload hosted tree is in canonical-original.zip on the immutable release. Manifest paths resolve after extracting those full originals. Original Actions Product/prior log bytes are separately preserved beside explicitly labelled connector-decoded logs.

Both full runs enforce 2,147,483,648 bytes (2 GiB), no swap, two CPUs and no external network, with no OOM/OOM-kill. Measured local kernel peak: {local['kernel_peak']} bytes; hosted: {host['kernel_peak']} bytes. Existing Trade/FOIS/sync/league-entry completion, safe deferral, recovery, cancellation and cleanup proofs pass; the final local five-case preflight leaves no child or scratch state. Deliberately pressured fixture peaks are not ordinary-read demand and cleanup does not prove long-term leak freedom. The hosted canonical run took 4,187.76 seconds, close to the existing 4,200-second harness budget; no time limit was relaxed. Local time was 2,600.35 seconds. These are full-suite timings on different execution hosts, not page-response benchmarks or universal performance claims.

The original 8 GiB scratch prerequisite and all resource reserves remain intact. Scratch cleanup was inventoried and limited to exact redundant published copies, completed duplicate Git checkouts and regenerable ignored bytecode. Source objects and unique original logs remain preserved.

## Preservation and remaining live boundary

No Trade threshold, Neutral/Custom formula, reference valuation coefficient, saved ranking, preference, goal, exact pick, submitted lineup, legal-lineup calculation, historical/FOIS formula or admission policy changed. No new provider, persistent duplicate data store, background acquisition or page-render preparation was added. Existing source method/adapter versions identify the normalized publication and prevent stale semantic reuse.

Production readiness, exact Render deployment and bounded guest/authentication-boundary smoke are live checks. This session lacks an associated owner browser or Render Shell/SSH; private authenticated source-to-screen recovery is unverified and the previous external inspection 401 was not repeated. No production sync, Trade search, FOIS rebuild, cache clear, restart or saved-user-data mutation was initiated.

Phone/browser controls are disposable store/preparation/route fixtures in two isolated league scopes, not live league lineup claims. Public actual scoring configurations are separate tests. Viewports 320×432, 375×667, 390×844 and 1280×900 pass readable internal table width, keyboard focus, touch emulation, no document overflow and no disclosure acquisition. Physical iPhone/Safari and comprehensive screen-reader acceptance remain unverified. Shipping this correction does not establish Granite recovery, full-season acquisition, a qualified Trade recommendation or the cause of an earlier 503.

[Complete Scout acceptance prompt](SCOUT_HANDOFF.md) · [Checksums](SHA256SUMS) · [Manifest](manifest.json).
''')
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if p.is_file():
  data=p.read_bytes()
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
  rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],merge=merged['merge_commit'],status='RELEASED',files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows))
print('Sanitized payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),'manifest',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
