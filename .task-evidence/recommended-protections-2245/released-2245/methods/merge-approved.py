"""Established expected-head squash only after guarded native preparation."""
from pathlib import Path
import json,subprocess,sys
sys.path.insert(0,'/workspace/dtos-publisher-2245')
from tools.release import publish
b=Path('/workspace/2245-recommended-protections');plan=json.loads(Path('/workspace/dtos-publisher-2245/.github/release-plans/2245.json').read_text());source=json.loads((b/'source.json').read_text());publisher=json.loads((b/'publisher-source.json').read_text())['publisher'];prepared=json.loads((b/'prepared-publication.json').read_text());verified=json.loads((b/'prepared-attachment-verification.json').read_text())
publish.verify_plan(plan)
assert prepared['candidate']==verified['candidate']==source['candidate'] and prepared['tree']==verified['tree']==source['tree']
assert prepared['publisher']==verified['publisher']==publisher and prepared['draft'] and not prepared['immutable']
assert verified['native_all_attachment_bytes_read_back'] and verified['cloud_api_digests_match_certificate'] and len(verified['attachments'])==23
repo='repos/'+plan['repository']
def api(path):return json.loads(subprocess.check_output(['gh','api',repo+'/'+path],text=True))
run=api('actions/runs/'+str(json.loads((b/'preparation-run.json').read_text())['id']));assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==publisher
assert api('git/ref/heads/main')['object']['sha']==source['baseline']
tag=subprocess.run(['gh','api',repo+'/git/ref/tags/v'+plan['version']],capture_output=True,text=True);assert tag.returncode and 'HTTP 404' in tag.stderr,'Immutable target already used; hold'
pr=api('pulls/'+str(plan['pr']));assert not pr['merged'] and pr['state']=='open' and pr['head']['sha']==source['candidate'] and pr['base']['sha']==source['baseline']
assert api('git/commits/'+source['candidate'])['tree']['sha']==source['tree']
records,_=publish.verify_runs(plan);assert len(records)==13
if pr['draft']:
 query='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{number isDraft}}}'
 result=json.loads(subprocess.check_output(['gh','api','graphql','-f','query='+query,'-f','id='+pr['node_id']],text=True));assert not result.get('errors') and result['data']['markPullRequestReadyForReview']['pullRequest']=={'number':plan['pr'],'isDraft':False}
body=dict(sha=source['candidate'],merge_method='squash',commit_title='feat: temporary exact protections for Recommended Trades (#334)',commit_message='Expose exact owned-player/pick exclusions through the existing recommendation constraint, without saving preferences or applying them to Evaluate. Keep original search restrictions, draft and selected comparisons. Reuse the existing search-options disclosure to preserve phone Generate reachability. No scoring, valuation, qualification, source acquisition or resource policy changes.\n\nValidated source tree: '+source['tree']+'\n\n'+f"{plan['canonical_tests']:,} regression tests and all ten gates passed locally and hosted; all thirteen hosted jobs and {plan['product_tests']} Product executions passed. Native Actions preparation verified all 23 attachments. Fixture acceptance is separate from unverified owner live/Safari acceptance. Prior failed/canceled attempts are retained.")
(b/'merge-input.json').write_text(json.dumps(body,indent=2)+'\n');result=json.loads(subprocess.check_output(['gh','api',repo+'/pulls/'+str(plan['pr'])+'/merge','--method','PUT','--input',str(b/'merge-input.json')],text=True));assert result['merged'] is True
sha=result['sha'];assert api('git/ref/heads/main')['object']['sha']==sha and api('git/commits/'+sha)['tree']['sha']==source['tree']
report=dict(merge_commit=sha,candidate=source['candidate'],tree=source['tree'],publisher=publisher,pr=plan['pr'],normal_expected_head_squash=True,validated_tree_unchanged=True);(b/'merged-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
