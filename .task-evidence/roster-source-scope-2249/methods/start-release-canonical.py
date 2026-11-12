"""Start one final official canonical run only after focused/resource proof and measured scratch."""
from pathlib import Path
import json,subprocess,datetime,shutil
from common import BASE, SOURCE_CHECKOUT, load_source, assert_checkout, IMAGE_ID, write_json, git_common_dir
import time
while not (BASE/'completed-archive-deduplication-verified.json').exists(): time.sleep(2)
assert json.loads((BASE/'completed-archive-deduplication-verified.json').read_text())['all_original_member_bytes_verified']
s=load_source();assert_checkout(s);focus=json.loads((BASE/'focused-ready.json').read_text());native=json.loads((BASE/'resource-preservation-verified.json').read_text());assert focus['candidate']==s['candidate'] and focus['tree']==s['tree'] and focus['passed'] and focus['tests']==123 and native['all_native_guards_passed'] and native['source']['candidate']==s['candidate']
assert not (BASE/'canonical-invocation.json').exists();free_before=shutil.disk_usage(BASE).free
assert free_before>8*1024**3+2400000000,'Do not create until space covers measured VFS copy plus unchanged8GiB scratch'
assert not (BASE/'fixture').exists();(BASE/'fixture').mkdir();common=git_common_dir(SOURCE_CHECKOUT)
args=['create','--name','dtos-roster-scope-canonical-2249','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','-v',str(SOURCE_CHECKOUT)+':/app','-v',str(common)+':'+str(common)+':ro','-v',str(BASE/'local-canonical')+':/output','-v',str(BASE/'fixture')+':/fixture','-e','HOME=/tmp','-e','NODE_OPTIONS=--max-old-space-size=256','-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app','-e','DTOS_EXPECTED_HEAD='+s['candidate'],'-e','DTOS_EXPECTED_TREE='+s['tree'],'-e','DTOS_EXPECTED_TEST_COUNT=4419','-w','/app',IMAGE_ID,'python','/output/runner.py']
container=subprocess.check_output(['docker',*args],text=True).strip();free=shutil.disk_usage(BASE).free;record=dict(source=s,args=args,container=container,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),image=IMAGE_ID,status='CREATED_NOT_STARTED',fixture_free_before_create=free_before,fixture_free_after_create=free)
write_json(BASE/'canonical-invocation.json',record);assert free>8*1024**3,'Actual scratch guard remains; do not start underinsufficientspace';subprocess.run(['docker','start',container],check=True);record.update(status='RUNNING_NOT_SUCCESS',started_at=datetime.datetime.now(datetime.timezone.utc).isoformat());write_json(BASE/'canonical-invocation.json',record);print(json.dumps(dict(container=container,free_after_create=free,candidate=s['candidate'],tree=s['tree'],focused123_and_native_guards_passed=True)))
