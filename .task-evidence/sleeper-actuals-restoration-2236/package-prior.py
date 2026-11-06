"""Keep original failed/superseded attempts distinct from final-source acceptance."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2236-actuals-restoration');m=json.loads((b/'source.json').read_text());files={}
for p in (b/'prior-attempts').rglob('*'):
 if p.is_file():files['prior-attempts/'+str(p.relative_to(b/'prior-attempts'))]=p.read_bytes()
for name in ['focused-initial.log','focused-second.log','focused-third.log','focused-fourth.log','focused-final.log','native-resource-initial.log','native-resource-corrected.log','cancellation-focused.log','cancellation-diagnostic.log','cancellation-diagnostic.json','diagnose-cancellation.py']:
 if (b/name).is_file():files['earlier-controls/'+name]=(b/name).read_bytes()
files['README.md']=('''# Original earlier attempts, not final acceptance\n\nFixture setup attempts and original failure logs are preserved unchanged. The first matched source-to-render fixture did not wait for its normal asynchronous Market preparation; its503 and secondary test errors are fixture failures, not proof of the connected binding omission. The corrected identical fixture separately establishes the omission on clean baseline and correction on the final source. Early focused runs found calendar-fixture, JSON tuple/list serialization and incomplete canonical Trade context assumptions. Positive fixtures now use the real producer after changed calendar settings; unknown completion is not invented, and all actual assertions remain. Initial resource setup incorrectly assumed a root scoring_settings field; it now uses the existing league field as appropriate. Host publisher lint lacked Ruff, so scoped lint used the already verified constrained runtime rather than elevated permissions/installing credentials. A diagnostic script initially lacked /app in its module search path; the original import failure is preserved.\n\nAny original failed local canonical run and its exact source are retained in prior-attempts, with the separate reconciliation record explaining what was changed versus rerun. Targeted diagnostic trials never replace mandatory regression or count as release acceptance. All source identities, counts and final status are established by the final records, not this descriptive index. No failed, canceled, deferred or unexecuted gate becomes a pass. Original immutable historical evidence is not replaced.\n''').encode()
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
for n,d in files.items():assert not pattern.search(d),n
rows=[dict(name=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest()) for n,d in sorted(files.items())]
files['prior-manifest.json']=json.dumps(dict(candidate=m['candidate'],tree=m['tree'],scope='prior-attempts-only',files=rows),indent=2).encode()+b'\n'
out=Path('/workspace/dtos-publisher-2236/.github/release-plans/2236-prior.zip');assert not out.exists()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,d in sorted(files.items()):z.writestr(n,d)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
(b/'package-prior-report.json').write_text(json.dumps(dict(bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),entries=len(rows),scope='prior-attempts-only'),indent=2)+'\n');print('Preserved',len(rows),'earlier original payloads')
