from pathlib import Path
import json,subprocess,datetime,os
B=Path('/workspace/2248-market-needs-final');source=json.loads((B/'source.json').read_text());checkout=Path('/workspace/dtos-market-local-2248-r3');env=dict(os.environ);env.pop('DOCKER_HOST',None);env.pop('DOCKER_CONTEXT',None)
def docker(*args):return subprocess.check_output(['docker','-H','unix:///var/run/docker.sock',*args],env=env,text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()==source['candidate']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout,text=True).strip()
assert not (B/'canonical-invocation.json').exists()
common=['--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','-v',str(checkout)+':/app','-v','/workspace/dtos/.git:/workspace/dtos/.git:ro','-e','HOME=/tmp','-e','NODE_OPTIONS=--max-old-space-size=256','-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app','-w','/app'];image='sha256:f70a0c6402700dfb954c99d8163d4164926f74435c34d2e7e462407151663ae6'
focus=B/'focused-exact';focus.mkdir(exist_ok=False)
s=(B/'focus-7/runner.py').read_text().replace("'tests.test_market_roster_relevance_browser'", "'tests.test_account_league_presentation_v1131','tests.test_market_render_cache','tests.test_market_trend_current_integration'").replace("scope='Development source; original failures retained, not exact-source release acceptance'", "scope='Frozen final candidate; new unit, original multi-account, cache and canonical comparison controls'")
(focus/'runner.py').write_text(s)
args=['create','--name','dtos-market-focused-2248-r3',*common,'-v',str(focus)+':/output','-e','DTOS_MARKET_NEED_EVIDENCE=/output/market-needs',image,'python','/output/runner.py'];container=docker(*args)
(B/'focused-invocation.json').write_text(json.dumps(dict(source=source,args=args,container=container,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
with (B/'focused-exact-console.log').open('x') as log:r=subprocess.run(['docker','-H','unix:///var/run/docker.sock','start','-a',container],env=env,stdout=log,stderr=subprocess.STDOUT)
x=json.loads(docker('inspect',container))[0];assert not x['State']['Running'] and x['State']['Pid']==0
(B/'focused-exact-container.json').write_text(json.dumps(dict(state=x['State'],image=x['Image'],limits={k:x['HostConfig'][k] for k in ['Memory','MemorySwap','NanoCpus','NetworkMode']}),indent=2)+'\n')
docker('rm',container)
assert r.returncode==0 and x['State']['ExitCode']==0 and not x['State']['OOMKilled'],'Focused failure retained; canonical not launched'
assert json.loads((focus/'result.json').read_text())['passed']
print('Exact-source focused controls passed; starting unchanged official canonical CLI.',flush=True)
(B/'fixture').mkdir(exist_ok=False)
args=['run','--detach','--name','dtos-market-canonical-2248-r3',*common,'-v',str(B/'local-canonical')+':/output','-v',str(B/'fixture')+':/fixture','-e','DTOS_EXPECTED_HEAD='+source['candidate'],'-e','DTOS_EXPECTED_TREE='+source['tree'],'-e','DTOS_EXPECTED_TEST_COUNT='+str(source['expected_test_count']),image,'python','/output/runner.py'];container=docker(*args)
(B/'canonical-invocation.json').write_text(json.dumps(dict(source=source,args=args,container=container,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='RUNNING; not success',image=image),indent=2)+'\n');print(container,flush=True)
