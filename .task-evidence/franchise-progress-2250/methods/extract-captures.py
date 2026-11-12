"""Byte-identical aliases of already verified source-bound captures."""
import hashlib,json,zipfile
from pathlib import Path,PurePosixPath
B=Path(__file__).resolve().parent;s=json.loads((B/'source.json').read_text());verified=json.loads((B/'hosted-artifacts-verified.json').read_text());assert verified['candidate']==s['candidate'] and verified['tree']==s['tree'] and verified['passed']
queue={r['file']:r for r in json.loads((B/'artifact-download-queue.json').read_text())};rows=[]
for original,prefix,destination in [('public-welcome-security.zip','trade-partner-history/','partner-history'),('trade-resource-original.zip','browser/team-need/','team-need'),('trade-resource-original.zip','browser/protections/','protections'),('trade-resource-original.zip','browser/offer-comparison/','offer-comparison'),('trade-resource-original.zip','browser/market-needs/','market-browser'),('trade-resource-original.zip','browser/roster-source-scope/','roster-browser'),('history-followthrough-original.zip','completed-trade-observations/','history-browser')]:
 path=B/'hosted-originals'/original;sha=hashlib.sha256(path.read_bytes()).hexdigest();assert sha==queue[original]['sha256'];out=B/destination;assert not out.exists();out.mkdir();members=[]
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  for name in z.namelist():
   if not name.startswith(prefix) or name.endswith('/'):continue
   relative=PurePosixPath(name[len(prefix):]);assert not relative.is_absolute() and '..' not in relative.parts
   raw=z.read(name);p=out/str(relative);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);assert p.read_bytes()==raw
   members.append(dict(name=str(relative),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 assert members,(original,prefix)
 rows.append(dict(original=original,original_sha256=sha,prefix=prefix,destination=destination,members=members))
focus=B/'focused-exact/franchise-progress';assert json.loads((focus/'browser.json').read_text())['head']==s['candidate']
rows.append(dict(original='focused-exact/franchise-progress',destination='recovery archive feature/ alias',scope='Actual clean final-source103-control run: these captures come from its88-history-control subset;15worker controls are separate; never labelled as live or substituted for native hosted acceptance',members=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(focus.glob('*')) if p.is_file()]))
(B/'capture-extraction.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],source_bound_native_originals=True,captures=rows),indent=2)+'\n');print('Verified captured bytes copied without altering original archives or canonical manifests.')
