"""Add verified release/deployment receipts; preserve sealed pre-publication evidence."""
from pathlib import Path
import json,hashlib,shutil,re
B=Path(__file__).resolve().parent;T=Path('/workspace/cache-sharing-handoff/.task-evidence/roster-source-scope-2249')
def load(name):return json.loads((B/name).read_text())
s=load('source.json');r=load('release-verified.json');p=load('production-verified.json');m=load('merge-verified.json');local=load('local-verified.json');host=load('host-canonical-verified.json');products=load('product-test-counts.json')
assert r['immutable'] and r['published'] and r['commit']==p['commit']==m['merge_commit'] and p['passed'] and r['tree']==s['tree']==p['tree']
assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['tests']==host['tests']==4419 and products['total']==916
names=['source-cleanup-verified.json','APPLICATION_VALIDATION.md','REPORT.md','recovery-verified.json','publisher-controller.json','publisher-final-integrity.json','publisher-final-exact-controls.log','publisher-final-exact-ruff.log','publisher-final-exact-compile.log','publisher-final-diff-check.log','prepare-certificate-original.zip','prepare-artifact-metadata.json','prepare-certificate-verified.json','premerge-guard.json','merge-original.json','merge-verified.json','publisher-prepare-final.json','publisher-publish-final.json','publish-certificate-original.zip','publish-artifact-metadata.json','publish-certificate-verified.json','release-verified.json','release-record-original.json','production-verified.json','production-smoke-original.json','render-deployment-final.json','final-release-plan.json','prepare-certificate-verification-original.log','publish-certificate-verification-original.log','prepare-dispatch-input.json','prepare-dispatch-receipt.json','publish-dispatch-input.json','publish-dispatch-receipt.json','publisher-prepare-jobs-original.json','publisher-publish-jobs-original.json','publisher-push-original.log']
for name in names:
 src=B/name;assert src.is_file() and not src.is_symlink(),src
 dst=T/name;dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():assert dst.read_bytes()==src.read_bytes(),name
 else:shutil.copyfile(src,dst)
for folder in ['prepare-certificate-native','publish-certificate-native']:
 for src in (B/folder).rglob('*'):
  if src.is_file():
   dst=T/folder/src.relative_to(B/folder);dst.parent.mkdir(parents=True,exist_ok=True)
   if dst.exists():assert dst.read_bytes()==src.read_bytes()
   else:shutil.copyfile(src,dst)
original=(B/'SCOUT_HANDOFF.md').read_bytes();(T/'SCOUT_HANDOFF_PREPUBLICATION.md').write_bytes(original)
deployed=f"# Released acceptance handoff\n\nReleased **v{s['version']} / build {s['build']}**, deployed `{p['commit']}`, validated tree `{s['tree']}`. [Immutable release]({r['url']}). The original pre-publication plan is preserved separately. Owner-authenticated Granite and physical Safari acceptance remain unverified.\n\n"+original.decode()
(B/'SCOUT_HANDOFF_DEPLOYED.md').write_text(deployed);(T/'SCOUT_HANDOFF.md').write_text(deployed);(T/'SCOUT_HANDOFF_DEPLOYED.md').write_text(deployed)
base=f"https://github.com/Richarddavis47/dtos/releases/download/v{s['version']}/"
(T/'README.md').write_text(f'''# Scoped roster freshness — build {s['build']}

Released **v{s['version']} / build {s['build']}**: [immutable release]({r['url']}). An unrelated missing/stale catalog projection no longer qualifies an unchanged supported roster comparison. Genuine missing roster evidence remains qualified. This does not establish live Granite recovery.

- [PR #338](https://github.com/Richarddavis47/dtos/pull/338), merged; deployment `{p['commit']}`.
- Validated candidate `{s['candidate']}`, source tree `{s['tree']}`, baseline `{s['baseline']}`.
- **4,419 regression executions and all ten gates locally and hosted; all 13 required hosted jobs; 916 Product executions.** The 123 focused controls overlap. New 20 methods are included. Publisher: 138 scoped controls.
- Native one-QB/K/DEF and Superflex fixtures; 320x432, 375x667, 390x844 and desktop; keyboard/touch emulation. Owner live and physical iPhone/Safari are **not verified**.

## Read original evidence

[Outcome and limitations](REPORT.md) · [validation](APPLICATION_VALIDATION.md) · [complete patch](candidate.patch) · [source identity](source.json) · [method](FEATURE_METHOD.md) · [Scout acceptance](SCOUT_HANDOFF.md).

[Local original console parts](local-canonical-unittest-console-log/) · [local original canonical records](local-canonical/) · [hosted original console parts](hosted-canonical-unittest-console-log/) · [hosted canonical records](hosted-canonical/) · [required job console parts](job-consoles/) · [focused console parts](focused-console/) · [new source/browser captures](roster-browser/) · [native resource controls](resource-originals/) · [separate local capital captures](local-capital-capture/) · [packaging correction](recovery-packaging-failure.json) · [prior failures and cancellations](prior-attempts/) · [dated partial checkpoint](checkpoints/2026-11-12T0414Z/).

Console/event/memory parts concatenate exactly in filename order. Each folder records whole-file and part SHA256. Original decoded GitHub logs preserve returned Unicode and CR/LF; no HTTP wire-byte claim is made. The dated checkpoint and pre-publication texts remain historical, separately qualified evidence.

## Immutable downloads

[Original hosted canonical archive]({base}canonical-original.zip) · [complete local/source handoff]({base}Market-Roster-Handoff.zip) · [Product/resource evidence]({base}trade-resource-original.zip) · [earlier attempts]({base}Prior-attempts.zip) · [release checksums]({base}SHA256SUMS) · [release manifest]({base}evidence-manifest.json).

[Readable handoff checksums](SHA256SUMS) and [manifest](handoff-manifest.json) cover these files. Native original API digests and specialized guards are verified; Actions performed attachment byte readback. Deployment receipts distinguish bounded public reads from fixture and supplied owner observations. No owner preferences, source publication or submitted lineup was changed.
''')
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})');files=[]
for path in sorted(T.rglob('*')):
 if not path.is_file():continue
 assert not path.is_symlink();name=str(path.relative_to(T))
 if name in {'handoff-manifest.json','SHA256SUMS'}:continue
 raw=path.read_bytes();assert len(raw)<100*1024**2
 if path.suffix.lower() in {'.log','.json','.jsonl','.txt','.md','.patch','.py','.js'}:assert not pattern.search(raw),name
 files.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
manifest=dict(schema=1,candidate=s['candidate'],tree=s['tree'],merge=p['commit'],release=r['url'],files=files)
(T/'handoff-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');raw=(T/'handoff-manifest.json').read_bytes();files.append(dict(name='handoff-manifest.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()));(T/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in files));print(json.dumps(dict(files=len(files)+1,manifest_sha256=hashlib.sha256(raw).hexdigest(),sanitized=True)))
