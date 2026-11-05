"""Assemble a new handoff; never alter the earlier immutable held review."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import zipfile

b=Path('/workspace/2229-release/final-scheduled')
root=Path('/workspace/team-assessment-handoff/.task-evidence/franchise-history-2229-final')
root.mkdir(exist_ok=True)
s=json.loads((b/'source.json').read_text())
local=json.loads((b/'local-verified.json').read_text())
host=json.loads((b/'host-canonical-verified.json').read_text())
merged=json.loads((b/'merged-source.json').read_text())
smoke=json.loads((b/'production-readonly-smoke.json').read_text())
published=json.loads((b/'publication-verified.json').read_text())
assert smoke['production_ready']['deployment']['commit']==merged['merge_commit']
assert published['release']['immutable'] and not published['release']['draft']
assert local['candidate']==host['candidate']==s['candidate']
for name in ['source.json','source-integrity.json','candidate-production.patch','local-verified.json',
        'host-canonical-verified.json','hosted-final-records.json','resource-diagnosis.json',
        'resource-verified.json','assertion-preservation.json','preservation.json',
        'baseline-reference.json','focused.log','history-browser.log','replay.log','commands.md',
        'run-clean.py','invocation.json','capture.py','preflight-driver.log','local-console.log',
        'resource-scope-check.log','prior-scope-check.log','publisher-preliminary.log',
        'publisher-preliminary-lint.log','publisher-lint.log','publisher-final.log',
        'patch-application.log','patch-check-setup-note.json','local-scratch-setup-failure.log',
        'pr-reference-reconciliation.json','superseded-reference-runs.json','active-log-transport-note.json',
        'dispatch-listing-note.json','scratch-reclamation.json','scratch-dependencies.json',
        'scratch-bytecode.json','scratch-fixtures.json','scratch-host-expansion.json',
        'expanded-duplicates.json','merged-source.json','publication-verified.json',
        'production-readonly-smoke.json','render-baseline-summary.json','render-deployed.json',
        'SCOUT_HANDOFF.md','package-final.py','package-prior.py','package-final.log','package-prior.log',
        'finalize-plan.py','verify-production.py','publish-evidence.py','product-original-decoded.log',
        'publisher-final-lint.log','publisher-archives-final.log','preparation-run.json','publication-run.json',
        'prepared-publication.json','preparation-certificate.zip']:
    shutil.copy2(b/name,root/name)
for directory in ['history-browser','replay','local-preflight','readable-console']:
    shutil.copytree(b/directory,root/directory)
for output,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
    d=root/output;d.mkdir()
    for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl',
            'canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:
        shutil.copy2(source/name,d/name)
for name in ['metadata-initial.json','metadata-resources.json','integrity-initial.json','integrity-resources.json',
        'trade-resource-2g-result.json','league-entry-2g-result.json']:
    d=root/'hosted-resource';d.mkdir(exist_ok=True);shutil.copy2(b/'hosted-originals'/name,d/name)
pub=Path('/workspace/dtos-publisher-2229/.github/release-plans')
for name in ['2229-recovery.zip','2229-prior.zip','2229.json']:
    shutil.copy2(pub/name,root/name)
for name in ['browser-collection-isolation.py','collection-isolation.log','collection-isolation/result.json','collection-isolation/memory.json']:
    p=root/'isolation-experiment'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(b.parent/name,p)
def split(source,dest,prefix):
    dest.mkdir();data=source.read_bytes();chunks=[];current=bytearray()
    for line in data.splitlines(keepends=True):
        if current and len(current)+len(line)>400000:chunks.append(bytes(current));current.clear()
        current.extend(line)
    if current:chunks.append(bytes(current))
    files=[]
    for i,part in enumerate(chunks,1):
        p=dest/f'{prefix}-{i:03d}.log';p.write_bytes(part);files.append(p)
    assert b''.join(p.read_bytes() for p in files)==data
    (dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
split(b/'host-canonical-readable/unittest-console.log',root/'readable-host-console','host-console')
split(b/'product-original-decoded.log',root/'readable-product-console','product-console')
release=published['release']['html_url']
text=f'''# Franchise history — v1.22.14 / build2229 final release

Released through [PR318](https://github.com/Richarddavis47/dtos/pull/318) and the [immutable release]({release}). Candidate `{s['candidate']}`; validated tree `{s['tree']}`; deployed merge `{merged['merge_commit']}`. [Source/patch verification](source-integrity.json), [complete patch](candidate-production.patch), [production smoke](production-readonly-smoke.json), [independent Render deploy record](render-deployed.json), [publication/attachments](publication-verified.json), [Scout checklist](SCOUT_HANDOFF.md).

The normal Trade browser fixture previously ran after accumulated unittest/ASGI state, with Chromium and Playwright sharing its2GiB container. The original390x844request correctly deferred with297076736usable bytes versus402653184required; there was no OOM or heavyweight lease conflict. [Original process/admission diagnosis](resource-diagnosis.json). The executable browser AST and all46assertions are unchanged; normal execution is scheduled before accumulated suite state. Independent pressure, cancellation, timeout and cleanup coverage remains mandatory. No application admission arithmetic, reserve or fantasy mathematics changed. The fresh isolation experiment peaked at1113944064bytes with no surviving children; it is distinct from the complete full-suite measurements below.

| Final exact-source evidence | Outcome |
|---|---|
| Focused history/source/browser controls |112passed,149.472s|
| Local mandatory regression |4107passed; all10canonical gates passed|
| Hosted mandatory canonical |4107passed; all10canonical gates passed|
| Required hosted jobs |12of12passed|
| Product executions |636passed (620+16)|
| Original canonical manifest payloads |{local['local_manifest_entries']}local / {host['entries']}hosted; every checksum verified|
| Dedicated enforced2GiB admission/resource controls |Healthy180-package search, pressure deferral,180-package recovery, actual cancellation/thread drain, lease/scratch cleanup, one-QB K/DEF and FOIS commitments passed|
| History geometry |8Day/Ark controls:320x432,375x667,390x844,1280x900; keyboard/touch emulation; nooverflow/disclosure requests|

[Local result](local-verified.json), [original full local console](original-local-canonical/unittest-console.log), [28readable local parts](readable-console), [original hosted console](original-host-canonical/unittest-console.log), [readable hosted parts](readable-host-console), [Product original decoded log](product-original-decoded.log), [readable Product parts](readable-product-console), [all hosted records](hosted-final-records.json). Local kernel peak{local['kernel_peak']}bytes, no OOM/OOM-kill, actual2147483648-byte limit/no swap/two CPUs/network none/UID1000. Full-suite pressure-test peaks are not normal Trade demand or a production worst-case profile.

History controls preserve Complete/Partial/Unknown transaction coverage, explicit completion status, deduplication, qualified ownership, exact pick original/season/round, independent observed draft selection coverage, compact retained events without invented acquired-week metadata, and FOIS RETAINED / NOT REVALIDATED. [Final retained-source replay](replay) and [phone evidence](history-browser). Rendering made no provider reads, source mutation or graph preparation. Day/Ark evidence is explicitly partialOctober12replay, supplemented by disposable complete/unknown/owner-change controls. Current private live histories and physical iPhone/Safari remain unverified. Guest production history checks prove authentication boundaries, not private timeline completeness. No user preferences, rankings, goals, lineups, valuation method or trades were written by this task.

The earlier held review remains unchanged at [a55bc686](https://github.com/Richarddavis47/dtos/tree/a55bc6865682f99b7e43c93238823d5c0eca50e0/.task-evidence/franchise-history-2229). Its original failed-host ZIP SHA256 is d8fa0d53f63f04178f11484f0b99c1f0e8b15e4e12284a8da599e5be08301508; all572original payloads were verified. Prior failures, cancellations, incomplete gates and withdrawn experiments remain separately manifested in[2229-prior.zip](2229-prior.zip). Baseline HTML/report loss, recreated baseline evidence, scratch/lint setup errors and corrected auxiliary patch baseline are explicitly documented; no recreated log is presented as an original. Cleanup samples do not prove long-term leak freedom.

[SHA256SUMS](SHA256SUMS) · [Full payload manifest](manifest.json). Original release attachments and their byte verification remain in the immutable release. No heavy live search, synchronization or FOIS rebuild was used for publication or smoke acceptance.
'''
(root/'README.md').write_text(text)
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
rows=[]
for p in sorted(root.rglob('*')):
    if not p.is_file():continue
    data=p.read_bytes()
    if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
    rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
manifest=dict(candidate=s['candidate'],tree=s['tree'],merge=merged['merge_commit'],status='RELEASED',files=rows)
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows))
print('Final sanitized payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),
      'manifestSHA256',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
