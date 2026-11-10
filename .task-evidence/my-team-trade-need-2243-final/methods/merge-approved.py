"""Normal expected-head PR merge only after native preparation and exact checks."""
from pathlib import Path
import json, subprocess
import sys
sys.path.insert(0,'/workspace/dtos-publisher-2243')
from tools.release import publish
b=Path('/workspace/2243-my-team-trade-need')
plan=json.loads(Path('/workspace/dtos-publisher-2243/.github/release-plans/2243.json').read_text())
source=json.loads((b/'source.json').read_text())
publisher=json.loads((b/'publisher-source.json').read_text())['publisher']
prepared=json.loads((b/'prepared-publication.json').read_text())
verified=json.loads((b/'prepared-attachment-verification.json').read_text())
assert prepared['candidate']==verified['candidate']==source['candidate'] and prepared['tree']==verified['tree']==source['tree']
assert prepared['publisher']==verified['publisher']==publisher and prepared['draft'] and not prepared['immutable']
assert verified['native_all_attachment_bytes_read_back'] and verified['cloud_api_digests_match_certificate']
assert len(verified['attachments'])==23
repo='repos/'+plan['repository']
def api(path):return json.loads(subprocess.check_output(['gh','api',repo+'/'+path],text=True))
run=api('actions/runs/'+str(json.loads((b/'preparation-run.json').read_text())['id']))
assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==publisher
assert api('git/ref/heads/main')['object']['sha']==source['baseline']
tag_lookup=subprocess.run(['gh','api',repo+'/git/ref/tags/v1.22.28'],capture_output=True,text=True)
assert tag_lookup.returncode!=0 and 'HTTP 404' in tag_lookup.stderr, 'Target immutable version is no longer unused; hold before any merge/publication.'
pr=api('pulls/332');assert not pr['merged'] and pr['state']=='open' and pr['head']['sha']==source['candidate'] and pr['base']['sha']==source['baseline']
assert api('git/commits/'+source['candidate'])['tree']['sha']==source['tree']
records,_=publish.verify_runs(plan);assert len(records)==13
if pr['draft']:
 query='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{number isDraft}}}'
 result=json.loads(subprocess.check_output(['gh','api','graphql','-f','query='+query,'-f','id='+pr['node_id']],text=True))
 assert not result.get('errors') and result['data']['markPullRequestReadyForReview']['pullRequest']=={'number':332,'isDraft':False}
body={'sha':source['candidate'],'merge_method':'squash',
 'commit_title':'feat: carry prepared My Team needs into Trade (#332)',
 'commit_message':'Carry a current prepared starter or depth need into an editable Recommended Trades position filter. Preserve explicit Generate, scoped drafts, prior contexts and saved preferences. No evaluation, scoring, valuation, source or memory-policy change.\n\nValidated source tree: '+source['tree']+'\n\n4,330 tests and all ten gates passed locally and hosted; all thirteen required hosted jobs and 831 Product executions passed. Native Actions preparation verified all 23 attachments before normal expected-head merge. Disposable authenticated round trips are distinct from unverified owner live acceptance. Prior failed/preliminary attempts remain preserved.'}

(b/'merge-input.json').write_text(json.dumps(body,indent=2)+'\n')
result=json.loads(subprocess.check_output(['gh','api',repo+'/pulls/332/merge','--method','PUT','--input',str(b/'merge-input.json')],text=True))
assert result['merged'] is True
sha=result['sha'];assert api('git/ref/heads/main')['object']['sha']==sha
assert api('git/commits/'+sha)['tree']['sha']==source['tree']
report=dict(merge_commit=sha,candidate=source['candidate'],tree=source['tree'],publisher=publisher,pr=332,normal_expected_head_squash=True,validated_tree_unchanged=True)
(b/'merged-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
