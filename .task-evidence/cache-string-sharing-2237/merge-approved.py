"""Normal expected-head PR merge only after native preparation and exact checks."""
from pathlib import Path
import json, subprocess
from tools.release import publish
b=Path('/workspace/2237-cache-duplication')
plan=json.loads(Path('/workspace/dtos-publisher-2237/.github/release-plans/2237.json').read_text())
source=json.loads((b/'source.json').read_text())
publisher=json.loads((b/'publisher-source.json').read_text())['publisher']
prepared=json.loads((b/'prepared-publication.json').read_text())
verified=json.loads((b/'prepared-attachment-verification.json').read_text())
assert prepared['candidate']==verified['candidate']==source['candidate'] and prepared['tree']==verified['tree']==source['tree']
assert prepared['publisher']==verified['publisher']==publisher and prepared['draft'] and not prepared['immutable']
assert verified['native_all_attachment_bytes_read_back'] and verified['cloud_api_digests_match_certificate']
assert len(verified['attachments'])==22
repo='repos/'+plan['repository']
def api(path):return json.loads(subprocess.check_output(['gh','api',repo+'/'+path],text=True))
run=api('actions/runs/'+str(json.loads((b/'preparation-run.json').read_text())['id']))
assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==publisher
assert api('git/ref/heads/main')['object']['sha']==source['baseline']
pr=api('pulls/326');assert not pr['merged'] and pr['state']=='open' and pr['head']['sha']==source['candidate'] and pr['base']['sha']==source['baseline']
assert api('git/commits/'+source['candidate'])['tree']['sha']==source['tree']
records,_=publish.verify_runs(plan);assert len(records)==12
if pr['draft']:
 query='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{number isDraft}}}'
 result=json.loads(subprocess.check_output(['gh','api','graphql','-f','query='+query,'-f','id='+pr['node_id']],text=True))
 assert not result.get('errors') and result['data']['markPullRequestReadyForReview']['pullRequest']=={'number':326,'isDraft':False}
body={'sha':source['candidate'],'merge_method':'squash','commit_title':'fix: reduce league restoration memory with bounded string sharing (#326)',
 'commit_message':'Share repeated immutable strings within each cache decode while preserving all values, mutable ownership, full serialized admission basis, source binding and existing memory policies.\n\nValidated application tree: '+source['tree']+'\n4,250 regression tests and all ten canonical gates passed locally and hosted; all twelve required hosted jobs and 757 Product executions passed. Native Actions preparation verified 22 evidence attachments before this merge. Authenticated Granite entry and independent live Sleeper actual-score parity remain separately unverified.'}
(b/'merge-input.json').write_text(json.dumps(body,indent=2)+'\n')
result=json.loads(subprocess.check_output(['gh','api',repo+'/pulls/326/merge','--method','PUT','--input',str(b/'merge-input.json')],text=True))
assert result['merged'] is True
sha=result['sha'];assert api('git/ref/heads/main')['object']['sha']==sha
assert api('git/commits/'+sha)['tree']['sha']==source['tree']
report=dict(merge_commit=sha,candidate=source['candidate'],tree=source['tree'],publisher=publisher,pr=326,normal_expected_head_squash=True,validated_tree_unchanged=True)
(b/'merged-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
