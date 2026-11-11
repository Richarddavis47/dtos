from pathlib import Path
import json,subprocess,datetime
B=Path('/workspace/2248-market-needs-final');s=json.loads((B/'source.json').read_text())
def api(path,payload=None):
    args=['gh','api',path]
    if payload is not None:args+=['--method','POST','--input','-']
    p=subprocess.run(args,input=None if payload is None else json.dumps(payload),text=True,capture_output=True,check=True)
    return json.loads(p.stdout)
local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());recovery=json.loads((B/'recovery-verified.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and recovery['passed']
assert all(x['candidate']==s['candidate'] and x['tree']==s['tree'] for x in [local,host])
repo='repos/Richarddavis47/dtos'
main=api(repo+'/git/ref/heads/main');assert main['object']['sha']==s['baseline']
pr=api(repo+'/pulls/'+str(s['pr']));assert pr['head']['sha']==s['candidate'] and pr['state']=='open' and not pr['merged']
tag=subprocess.run(['gh','api',repo+'/git/ref/tags/v'+s['version']],text=True,capture_output=True)
assert tag.returncode and 'HTTP 404' in tag.stderr,'Version tag not confirmed unused'
releases=api(repo+'/releases?per_page=100');assert not [r for r in releases if r['tag_name']=='v'+s['version']],'Existing release must be investigated, not duplicated'
assert not (B/'release-draft-created.json').exists()
notes=subprocess.run(['git','show',s['candidate']+':RELEASE_NOTES.md'],cwd='/workspace/dtos-market-needs-2248',text=True,capture_output=True,check=True).stdout.split('\n# ',1)[0]
notes+='\n\nValidated candidate: '+s['candidate']+'\nValidated tree: '+s['tree']+'\nAll mandatory local and hosted gates passed. This draft is prepared before merge and must not be published until the guarded Actions publisher verifies the approved main tree.\n'
release=api(repo+'/releases',dict(tag_name='v'+s['version'],target_commitish=s['candidate'],name='DTOS v'+s['version']+' / build '+str(s['build']),body=notes,draft=True,prerelease=False))
(B/'release-draft-created.json').write_text(json.dumps(release,indent=2)+'\n')
assert release['draft'] and release['tag_name']=='v'+s['version'] and release['target_commitish']==s['candidate']
print(json.dumps(dict(draft_id=release['id'],tag_name=release['tag_name'],draft=release['draft'],target_commitish=release['target_commitish'])))
