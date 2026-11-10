"""Append final source/deployed evidence; never replace immutable prior attempts."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re,shutil,urllib.parse
b=Path('/workspace/2245-recommended-protections');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/recommended-protections-2245/released-2245';out=repo/prefix;assert not out.exists(),'Do not overwrite published evidence'
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merge=json.loads((b/'merged-source.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());prod=json.loads((b/'production-readonly-smoke.json').read_text());assets=json.loads((b/'published-attachment-verification.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['tests']==host['tests']==4346 and merge['tree']==pub['tree']==s['tree'];assert prod['production_ready']['deployment']['commit']==merge['merge_commit'];assert pub['release']['immutable'] and not pub['release']['draft'] and len(assets['attachments'])==23
out.mkdir(parents=True)
files=['REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','source.json','baseline.json','baseline-reproduction.json','baseline-reproduction-original.log','candidate.patch','preservation-review.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','hosted-artifacts-verified.json','product-test-counts.json','public-welcome-test-counts.json','focused-resource-verified.json','publisher-source.json','publisher-scoped-checks.json','publisher-scoped-sealed.json','publisher-workflow-review.json','recovery-compression-reconciliation.json','recovery-package.json','prior-package.json','recovery-offline-verified.json','draft-created.json','merged-source.json','preparation-run.json','publication-run.json','preparation-run-completed.json','publication-run-completed.json','preparation-artifacts.json','publication-artifacts.json','prepared-publication.json','published-publication.json','prepared-attachment-verification.json','published-attachment-verification.json','preparation-certificate-metadata.json','publication-certificate-metadata.json','preparation-certificate.zip','publication-certificate.zip','production-readonly-smoke.json','publisher-production-smoke.json','publication-verified.json','canonical-invocation.json','canonical-runtime-freeze.txt','local-container-enforcement.json','local-container-cleanup.json','local-budget-recovery-method.json','live-access-limitation-release.json','initial-public-readback.json','prior-public-readback.json','phone-failure-public-readback.json','prior-local-public-readback.json','canonical-job-log-receipt.json','publisher-prepare-log-receipt.json','publisher-publication-log-receipt.json','prior-package-size-reconciliation.json','environment-reconnection.json']
for name in files:
 p=b/name;assert p.is_file(),name;shutil.copyfile(p,out/name)
for p in b.glob('*original.log'):shutil.copyfile(p,out/p.name)
for folder in ['focused-final','win-now','partner-history','team-need','offer-comparison','history-browser','hosted-decoded-originals','publisher-decoded-originals','readable-originals','readable-console','readable-root-logs']:
 p=b/folder
 if p.exists():shutil.copytree(p,out/folder)
# These are directly readable original core canonical records. The complete
# manifest-bound payload, including every other capture, is in immutable release
# archives with byte/hash receipts below; no artifact is claimed absent there.
for folder in ['local-canonical','host-canonical-readable']:
 dst=out/folder;dst.mkdir()
 for name in ['unittest-console.log','canonical.log','result.json','manifest.json','SHA256SUMS','tests.jsonl','canonical-trace.jsonl','memory.jsonl']:
  p=b/folder/name;assert p.is_file(),p;shutil.copyfile(p,dst/name)
methods=out/'methods';methods.mkdir()
for p in b.glob('*.py'):shutil.copyfile(p,methods/p.name)
release_url='https://github.com/Richarddavis47/dtos/releases/tag/v1.22.30'
references=[dict(**row,url='https://github.com/Richarddavis47/dtos/releases/download/v1.22.30/'+urllib.parse.quote(row['name'],safe='')) for row in assets['attachments']]
(out/'immutable-attachments.json').write_text(json.dumps(references,indent=2)+'\n')
status=dict(status='RELEASED',version='1.22.30',build=2245,pr=334,candidate=s['candidate'],tree=s['tree'],deployed_commit=merge['merge_commit'],release_url=release_url,immutable=True,attachments=23,local_tests=4346,hosted_tests=4346,local_gates=10,hosted_gates=10,required_hosted_jobs=13,product_executions=847,welcome_security_executions=412,focused_executions=16,preserved_browser_executions=15,separate_win_now_control=1,publisher_tests=79,owner_authenticated_live=False,physical_safari_tested=False,production_searches=0,production_user_data_mutation=False,observed_at=datetime.now(timezone.utc).isoformat());(out/'FINAL_STATUS.json').write_text(json.dumps(status,indent=2)+'\n')
(out/'FINAL_STATUS.md').write_text(f'''# Released — DTOS v1.22.30 / build 2245

PR #334 merged as `{merge['merge_commit']}`. Validated candidate `{s['candidate']}` and deployed merge have identical tree `{s['tree']}`. [Immutable release]({release_url}) has all23attachments. Native publisher read back every attachment byte; the independent certificate/API reader confirmed all recorded digests. Public readiness, source-identical static files and guest auth boundaries passed. No private league hydration or production search was used.

Both local and hosted canonical runs completed4,346tests and all10gates. All13required hosted jobs passed: Product847(673+35+139), separate Welcome/security412, My Team/navigation/history,Ubuntu/Windows tooling,three Linux lifecycle modes and existing resource controls. Local manifest has{local['local_manifest_entries']}entries; hosted658. All15original ZIPs match source/API SHA/size/CRC. Focused16,preserved browser15,separate Win Now1,publisher integrity79passed. Counts are executions, not unique tests or independent Scout review.

[Full sealed review report](REPORT.md), [deployed Scout prompt](SCOUT_DEPLOYED.md), [exact source patch](candidate.patch), [all readable originals](readable-originals/INDEX.json), [full original local console](local-canonical/unittest-console.log), [full original hosted console](host-canonical-readable/unittest-console.log), [original final hosted job consoles](hosted-decoded-originals), [earlier attempts](PRIOR_ATTEMPTS.md), [23immutable attachment URLs and SHA256](immutable-attachments.json). Every public file is in manifest.json/SHA256SUMS. Original full local/hosted payloads are in their immutable archives; core logs here are not a claim of a second complete payload copy.

Temporary exact protection picker uses the existing search constraint. Own and acquired firsts stay distinct; generated/exploratory outgoing offers exclude protected IDs. Prior searches retain original effective constraints. Evaluate/draft/comparison state and saved preferences remain independent. No threshold, scoring, valuation, Sleeper projection/result or resource-policy change. Opening/editing controls starts no search/provider work. Zero-qualified is not a failed or deferred search and is not blamed on restrictions.

The initial final-source local80minute timeout is preserved as incomplete (3,998completed,3,999started;0active descendants after cleanup,noOOM). The final local run changed only the external local budget to110minutes and observer duration; official CLI/allgates/tests,app timeouts,2GiB/Trade256+128MiB/FOIS768MiB policies were unchanged. Earlier phone-layout failures remain separate and were fixed without relaxing the original pointer assertions.

Owner authenticated live acceptance and physical iPhone/Safari remain unverified. The associated Browser capability was unavailable; no401probe or workaround was attempted. Fixtures are real authenticated disposable routes/native search/admission with1-QB/K/DEF and Superflex controls, not live owner offers or production capacity evidence. Scout must stop on real admission deferral and preserve the owner's saved preferences.
''')
(out/'SCOUT_DEPLOYED.md').write_text(f'''# Independently verify deployed temporary protections

Verify v1.22.30/build2245,PR #334,commit`{merge['merge_commit']}`,tree`{s['tree']}`,[immutable release]({release_url}). Candidate`{s['candidate']}`. Native publication and bounded public smoke are complete; owner live acceptance and physical Safari remain separate. No saved settings or production search was modified by Codex.

'''+(b/'SCOUT_HANDOFF.md').read_text())
(out/'README.md').write_text('''# Temporary Recommended Trades protections

[Deployed result](FINAL_STATUS.md) · [Full report](REPORT.md) · [Scout acceptance](SCOUT_DEPLOYED.md) · [Exact patch](candidate.patch) · [Immutable attachment URLs/SHA256](immutable-attachments.json)

Read full original4346-test consoles directly: [local](local-canonical/unittest-console.log), [hosted](host-canonical-readable/unittest-console.log). [Readable original parts](readable-originals/INDEX.json) preserve every byte and original SHA256 using <=60,000byte UTF-8 parts; source/attempt labels remain distinct. [Final hosted job logs](hosted-decoded-originals) and [prior attempts](PRIOR_ATTEMPTS.md) retain original outcomes. The sealed review report precedes publication; FINAL_STATUS and publication receipts establish actual deployed identity.

[Exact picker/phone captures](focused-final), [independent Win Now control](win-now), [unchanged draft/comparison controls](offer-comparison). Complete manifest-bound validation payloads and original native hosted ZIPs remain immutable release attachments; selected directly readable core records here do not imply every manifest entry is duplicated in this directory. Public manifest.json/SHA256SUMS cover every delivered public byte. Recovery uses standard ZIP/LZMA (Python zipfile); every original validation member is unchanged. Compression only resolved Git blob transport and did not change application cache decoding or admission. No authenticated owner or physical Safari acceptance is claimed.
''')
# Only new explanatory prose is spacing-normalized; original logs remain exact.
for name in ['README.md','FINAL_STATUS.md','SCOUT_DEPLOYED.md']:
 p=out/name;text=p.read_text()
 for old,new in [('all23attachments','all 23 attachments'),('completed4,346tests','completed 4,346 tests'),('all10gates','all 10 gates'),('All13required','All 13 required'),('Product847','Product 847'),('Welcome/security412','Welcome/security 412'),('has'+str(local['local_manifest_entries'])+'entries','has '+str(local['local_manifest_entries'])+' entries'),('hosted658','hosted 658'),('All15original','All 15 original'),('Focused16','Focused 16'),('browser15','browser 15'),('Now1','Now 1'),('integrity79passed','integrity 79 passed'),('local80minute','local 80-minute'),('0active','0 active'),('cleanup,noOOM','cleanup, no OOM'),('to110minutes','to 110 minutes'),('with1-QB','with 1-QB'),('commit`','commit `'),('tree`','tree `'),('Candidate`','Candidate `'),('original4346-test','original 4346-test'),('<=60,000byte','<=60,000 byte'),('Trade256+128MiB','Trade 256+128 MiB'),('FOIS768MiB','FOIS 768 MiB')]:text=text.replace(old,new)
 p.write_text(text)
rows=[];token=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
for p in sorted(out.rglob('*')):
 if p.is_file():
  assert not p.is_symlink();raw=p.read_bytes();assert not token.search(raw),p;rows.append(dict(name=str(p.relative_to(out)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
m=dict(candidate=s['candidate'],tree=s['tree'],deployed_commit=merge['merge_commit'],files=rows);raw=(json.dumps(m,indent=2)+'\n').encode();(out/'manifest.json').write_bytes(raw);sha=hashlib.sha256(raw).hexdigest();(out/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows)+sha+'  manifest.json\n');record=dict(prefix=prefix,candidate=s['candidate'],tree=s['tree'],deployed_commit=merge['merge_commit'],files=len(rows),bytes=sum(x['bytes'] for x in rows),manifest_sha256=sha);(b/'final-handoff-prepared.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
