"""Add actual publication/deployment receipts without editing sealed release originals."""
from pathlib import Path
import json,hashlib,shutil,re
B=Path('/workspace/2248-market-needs-final');T=Path('/workspace/cache-sharing-handoff/.task-evidence/market-roster-2248');s=json.loads((B/'source.json').read_text());r=json.loads((B/'release-verified.json').read_text());p=json.loads((B/'production-verified.json').read_text());merge=json.loads((B/'merge-verified.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());products=json.loads((B/'product-test-counts.json').read_text())
assert r['immutable'] and r['published'] and r['commit']==p['commit']==merge['merge_commit'] and p['passed'] and r['tree']==s['tree']==p['tree'];assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['tests']==host['tests']==4399 and products['total']==896
for name in ['source-cleanup-verified.json','APPLICATION_VALIDATION.md','REPORT.md','recovery-verified.json','publisher-controller.json','publisher-final-integrity.json','publisher-final-exact-controls.log','publisher-final-exact-ruff.log','prepare-certificate-original.zip','prepare-artifact-metadata.json','prepare-certificate-verified.json','premerge-guard.json','merge-original.json','merge-verified.json','publisher-prepare-final.json','publisher-publish-final.json','publish-certificate-original.zip','publish-artifact-metadata.json','release-verified.json','release-record-original.json','production-verified.json','production-smoke-original.json','render-deployment-final.json','final-release-plan.json']:
 src=B/name;assert src.is_file() and not src.is_symlink(),src;dest=T/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
for folder in ['prepare-certificate-native','publish-certificate-native']:
 for src in (B/folder).rglob('*'):
  if src.is_file():dest=T/folder/src.relative_to(B/folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
original=(B/'SCOUT_HANDOFF.md').read_text();(T/'SCOUT_HANDOFF_PREPUBLICATION.md').write_text(original);deployed=f"# Released acceptance handoff\n\nReleased **v{s['version']}/build{s['build']}**, deployed `{p['commit']}`, validated tree `{s['tree']}`. [Immutable release]({r['url']}). The sealed release attachment below was written before publication; actual release/deployment receipts are provided alongside this final handoff. Owner-authenticated live and physical Safari acceptance remain unverified.\n\n"+original;(B/'SCOUT_HANDOFF_DEPLOYED.md').write_text(deployed);(T/'SCOUT_HANDOFF.md').write_text(deployed);(T/'SCOUT_HANDOFF_DEPLOYED.md').write_text(deployed)
base=f"https://github.com/Richarddavis47/dtos/releases/download/v{s['version']}/"
(T/'README.md').write_text(f'''# Market movement and your roster — build{s['build']}

Released **v{s['version']}/build{s['build']}**: [immutable release]({r['url']}). Market connects compatible canonical observations to a current prepared starter/depth need, with source, dates, age, neutral cost and limits. Exact-player Trade For handoffs wait for an explicit search and preserve prior work. This is investigative context, not an evaluated recommendation.

- PR [#337](https://github.com/Richarddavis47/dtos/pull/337), merged. Deployment `{p['commit']}`.
- Validated candidate `{s['candidate']}`, source tree `{s['tree']}`, baseline `{s['baseline']}`.
- **4,399 regression executions/all ten gates locally and hosted; all 13 required hosted jobs; 896 Product executions.** New21 controls are included. Exact54focused controls and code-equivalent56rendered/related controls overlap; one additional unchanged-source anchor probe passed. Publisher guards passed129controls.
- Fixtures cover1QB/K/DEF and Superflex,320x432/375x667/390x844/desktop, keyboard and touch emulation. Owner live and physical iPhone/Safari are **not verified**.

## Read original evidence

[Outcome and limitations](REPORT.md) · [validation](APPLICATION_VALIDATION.md) · [complete patch](candidate.patch) · [source identity](source.json) · [method](FEATURE_METHOD.md) · [Scout acceptance](SCOUT_HANDOFF.md).

[Local original console parts](local-console/) · [hosted canonical original and parts](hosted-canonical/) · [all required job console parts](job-consoles/) · [exact focused console](focused-console/) · [Market source/browser captures](market-browser/) · [anchor probe](anchor-probe/) · [prior failures/incomplete/canceled attempts](prior-attempts/) · [dated partial recovery checkpoint](checkpoint-20261111T2210Z/README.md).

Console parts concatenate exactly in filename order; each folder records whole-file and per-part SHA256. The dated checkpoint remains historical partial evidence; it is not a claim of incomplete final validation. Original pre-publication acceptance text remains separately preserved.

## Immutable downloads

[Full original canonical artifact]({base}canonical-original.zip) · [complete local/source handoff]({base}Market-Roster-Handoff.zip) · [original Product/resource evidence]({base}trade-resource-original.zip) · [earlier attempts]({base}Prior-attempts.zip) · [release checksums]({base}SHA256SUMS) · [release manifest]({base}evidence-manifest.json).

[Handoff SHA256](SHA256SUMS) and [manifest](handoff-manifest.json) cover these readable files. Every required native original was verified against its GitHub API digest and internal integrity records. Actions performed attachment byte readback; deployment receipts distinguish public read-only observations from disposable fixture results. No source acquisition, owner preferences, submitted lineups or real transactions were changed during live checks.
''')
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})');files=[]
for path in sorted(T.rglob('*')):
 if not path.is_file():continue
 assert not path.is_symlink();name=str(path.relative_to(T))
 if name in {'handoff-manifest.json','SHA256SUMS'}:continue
 raw=path.read_bytes();assert len(raw)<100*1024**2
 if path.suffix.lower() in {'.log','.json','.jsonl','.txt','.md','.patch','.py','.js'}:assert not pattern.search(raw),name
 files.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
manifest=dict(schema=1,candidate=s['candidate'],tree=s['tree'],merge=p['commit'],release=r['url'],files=files);(T/'handoff-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');raw=(T/'handoff-manifest.json').read_bytes();files.append(dict(name='handoff-manifest.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()));(T/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in files));print(json.dumps(dict(files=len(files)+1,manifest_sha256=hashlib.sha256(raw).hexdigest(),sanitized=True)))
