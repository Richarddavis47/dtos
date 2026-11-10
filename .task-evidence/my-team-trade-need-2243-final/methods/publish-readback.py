from pathlib import Path
import json,hashlib,subprocess,shutil
b=Path('/workspace/2243-my-team-trade-need');repo=Path('/workspace/cache-sharing-handoff');r=json.loads((b/'final-evidence-public-readback.json').read_text());assert r['published_bytes_readback'] and r['verified_files']==r['files']
prefix='.task-evidence/my-team-trade-need-2243-readback';out=repo/prefix;assert not out.exists() and not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip();out.mkdir(parents=True);(out/'.gitattributes').write_text('* -text\n')
for n in ['final-evidence-public-readback.json','final-evidence-publication.json','final-workspace-check.json','final-evidence-publication-original.log','final-public-readback-original.log']:shutil.copy2(b/n,out/n)
for filename,label in [('final-evidence-publication-original.log','publication-console'),('final-public-readback-original.log','readback-console')]:
 raw=(b/filename).read_bytes();parts=[];start=0
 while start<len(raw):
  end=min(start+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  part=raw[start:end];parts.append(part);(out/(label+'-'+str(len(parts)).zfill(3)+'.log')).write_bytes(part);start=end
 assert b''.join(parts)==raw
(out/'README.md').write_text('''# My Team handoff evidence transport and source checks

The completed task evidence was fetched from its published commit URLs. Every payload matched its recorded size and SHA-256; the manifest and checksum list matched too. See final-evidence-public-readback.json for exact population and source identity. This is byte/integrity verification, not independent Scout acceptance.

The publication and public-readback command outputs were deliberately excluded from the first evidence snapshot to avoid circular or incomplete self-logs. Their completed originals and <=60k-byte readable parts are supplied here. Mandatory validation and failed/preliminary test originals remain in the unchanged first snapshot.

The exact task source and owned-container cleanup are recorded in final-workspace-check.json. Publication/deployment status is supplied by the main evidence snapshot, not inferred from byte transport. Original source/evidence refs and failed attempts remain preserved. No production user-data mutation occurred. Authenticated live My Team/Trade handoff acceptance and physical Safari remain separately unverified; follow the main Scout handoff and stop on capacity deferral.
''')
rows=[]
for p in sorted(out.iterdir()):
 if p.is_file():raw=p.read_bytes();rows.append(dict(name=p.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
(out/'manifest.json').write_text(json.dumps(dict(evidence_commit=r['evidence_commit'],candidate=r['candidate'],tree=r['tree'],deployed_commit=r['deployed_commit'],files=rows),indent=2)+'\n');sha=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in rows)+sha+'  manifest.json\n');subprocess.run(['git','add','--sparse','-f',prefix],cwd=repo,check=True);subprocess.run(['git','commit','-m','Record final My Team handoff evidence readback and cleanup receipt'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True);head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();result=dict(commit=head,prefix=prefix,manifest_sha256=sha,url='https://github.com/Richarddavis47/dtos/tree/'+head+'/'+prefix);(b/'readback-publication.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
