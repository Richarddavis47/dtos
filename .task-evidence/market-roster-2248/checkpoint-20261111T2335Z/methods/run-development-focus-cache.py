from pathlib import Path
import subprocess,json,hashlib,sys,datetime,os
B=Path('/workspace/2248-market-needs-final');source=Path('/workspace/dtos-market-needs-2248');phase=sys.argv[1];assert phase.replace('-','').isalnum();output=B/phase;output.mkdir(exist_ok=False)
runner=(B/'focus-4/runner.py').read_text().replace("'tests.test_market_roster_relevance_browser'])","'tests.test_market_roster_relevance_browser','tests.test_account_league_presentation_v1131','tests.test_market_render_cache','tests.test_market_trend_current_integration'])");(output/'runner.py').write_text(runner)
paths=subprocess.run(['git','ls-files','--modified','--others','--exclude-standard'],cwd=source,capture_output=True,text=True,check=True).stdout.splitlines();files=[dict(path=p,sha256=hashlib.sha256((source/p).read_bytes()).hexdigest()) for p in paths if (source/p).is_file()]
name='dtos-market-needs-'+phase;args=['docker','-H','unix:///var/run/docker.sock','run','--name',name,'--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','-e','HOME=/tmp','-e','NODE_OPTIONS=--max-old-space-size=256','-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app','-e','DTOS_MARKET_NEED_EVIDENCE=/output/market-needs','-v',str(source)+':/app','-v','/workspace/dtos/.git:/workspace/dtos/.git:ro','-v',str(output)+':/output','-w','/app','sha256:f70a0c6402700dfb954c99d8163d4164926f74435c34d2e7e462407151663ae6','python','/output/runner.py']
(output/'invocation.json').write_text(json.dumps(dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),args=args,base_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),working_source=files,scope='Development source fingerprints, not frozen release acceptance'),indent=2)+'\n')
with (output/'original-console.log').open('x') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
x=json.loads(subprocess.run(['docker','-H','unix:///var/run/docker.sock','inspect',name],capture_output=True,text=True,check=True).stdout)[0];assert not x['State']['Running'] and x['State']['Pid']==0
(output/'container-state-original.json').write_text(json.dumps(dict(id=x['Id'],state=x['State'],image=x['Image'],limits={k:x['HostConfig'][k] for k in ['Memory','MemorySwap','NanoCpus','NetworkMode']}),indent=2)+'\n')
subprocess.run(['docker','-H','unix:///var/run/docker.sock','rm',x['Id']],check=True,capture_output=True)
assert all(hashlib.sha256((source/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in files),'Source changed during run'
print(json.dumps(dict(phase=phase,exit_code=r.returncode,source_unchanged_during_run=True,container_removed_after_retaining_state=True)))
raise SystemExit(r.returncode)
