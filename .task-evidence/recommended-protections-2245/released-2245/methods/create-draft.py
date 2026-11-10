"""Create only the validated, unused-version draft; never merge or create a tag."""
from pathlib import Path
import json,subprocess,sys
sys.path.insert(0,'/workspace/dtos-publisher-2245')
from tools.release import publish as publisher
b=Path('/workspace/2245-recommended-protections');source=json.loads((b/'source.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2245/.github/release-plans/2245.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());proof=json.loads((b/'focused-resource-verified.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and proof['all_native_guards_passed'];assert local['tests']==host['tests']==4346;assert local['candidate']==host['candidate']==proof['candidate']==source['candidate'] and local['tree']==host['tree']==proof['tree']==source['tree'];publisher.verify_runs(plan)
repo='repos/'+plan['repository']
def api(path):return json.loads(subprocess.check_output(['gh','api',repo+'/'+path],text=True))
assert api('git/ref/heads/main')['object']['sha']==source['baseline'];pr=api('pulls/334');assert pr['state']=='open' and not pr['merged'] and pr['head']['sha']==source['candidate'] and pr['base']['ref']=='main'
lookup=subprocess.run(['gh','api',repo+'/git/ref/tags/v1.22.30'],capture_output=True,text=True);assert lookup.returncode and 'HTTP 404' in lookup.stderr,'Immutable target already used; hold'
existing=[r for r in api('releases?per_page=100') if r['tag_name']=='v1.22.30']
if existing:
 assert len(existing)==1 and existing[0]['draft'] and not existing[0]['immutable'] and existing[0]['target_commitish']==source['candidate'];draft=existing[0]
else:
 notes=subprocess.check_output(['git','show',source['candidate']+':RELEASE_NOTES.md'],cwd='/workspace/dtos',text=True).split('\n# ',1)[0]
 payload=dict(tag_name='v1.22.30',target_commitish=source['candidate'],name='DTOS v1.22.30 / build 2245',body=notes,draft=True,prerelease=False);path=b/'draft-create-input.json';path.write_text(json.dumps(payload,indent=2)+'\n');draft=json.loads(subprocess.check_output(['gh','api',repo+'/releases','--method','POST','--input',str(path)],text=True))
assert draft['draft'] and draft['tag_name']=='v1.22.30' and draft['target_commitish']==source['candidate'];(b/'draft-created.json').write_text(json.dumps(draft,indent=2)+'\n');print('Created/reused exact validated draft',draft['id'],'without tag/merge/publication')
