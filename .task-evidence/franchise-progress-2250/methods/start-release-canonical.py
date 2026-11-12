"""One exact official full local canonical run, unchanged resource/scratch guards."""
import datetime,json,shutil,subprocess
from common import BASE,SOURCE_CHECKOUT,load_source,assert_checkout,IMAGE_ID,write_json,git_common_dir
s=load_source();assert_checkout(s)
f=json.loads((BASE/'focused-ready.json').read_text());r=json.loads((BASE/'resource-preservation-verified.json').read_text())
assert f['candidate']==s['candidate'] and f['tree']==s['tree'] and f['passed'] and f['tests']==103
assert r['all_native_guards_passed'] and r['source']['candidate']==s['candidate'] and r['source']['tree']==s['tree']
assert not (BASE/'canonical-invocation.json').exists()
free_before=shutil.disk_usage(BASE).free
assert free_before>8*1024**3+2400000000,('Insufficient scratch before unchanged VFS creation',free_before)
(BASE/'fixture').mkdir();common=git_common_dir(SOURCE_CHECKOUT)
args=['create','--name','dtos-franchise-progress-canonical-2250','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','-v',str(SOURCE_CHECKOUT)+':/app','-v',str(common)+':'+str(common)+':ro','-v',str(BASE/'local-canonical')+':/output','-v',str(BASE/'fixture')+':/fixture','-e','HOME=/tmp','-e','NODE_OPTIONS=--max-old-space-size=256','-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app','-e','DTOS_EXPECTED_HEAD='+s['candidate'],'-e','DTOS_EXPECTED_TREE='+s['tree'],'-e','DTOS_EXPECTED_TEST_COUNT='+str(s['expected_test_count']),'-w','/app',IMAGE_ID,'python','/output/runner.py']
c=subprocess.check_output(['docker',*args],text=True).strip();free=shutil.disk_usage(BASE).free
record=dict(source=s,args=args,container=c,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),image=IMAGE_ID,status='CREATED_NOT_STARTED',fixture_free_before_create=free_before,fixture_free_after_create=free)
write_json(BASE/'canonical-invocation.json',record)
assert free>8*1024**3,('Actual remaining scratch does not meet unchanged8GiB guard',free)
subprocess.run(['docker','start',c],check=True);record.update(status='RUNNING_NOT_SUCCESS',started_at=datetime.datetime.now(datetime.timezone.utc).isoformat());write_json(BASE/'canonical-invocation.json',record)
print(json.dumps(dict(container=c,free_after_create=free,candidate=s['candidate'],tree=s['tree'],focused103_and_native_guards_passed=True)))
