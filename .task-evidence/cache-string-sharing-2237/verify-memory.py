"""Read actual captured controls; no source acquisition, restoration or policy substitution."""
import hashlib,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/app')
from src.platform.cache_restoration_admission import restoration_admission
from src.platform.fois_admission import WORKING_RESERVE_BYTES,SAFETY_MARGIN_BYTES
b=Path('/evidence');source=json.loads((b/'source.json').read_text());rows=[]
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source['candidate']
for name in ['oneqb','superflex']:
 new=json.loads((b/f'profile-{name}-final.json').read_text());old=json.loads((b/f'profile-{name}-standard-control.json').read_text())
 for x in [old,new]:
  assert x['source_head']==source['candidate'] and x['source_tree']==source['tree'] and x['working_tree_clean'] and x['passed']
  assert x['enforced_limit']==2147483648 and x['swap_limit']==0 and x['lifecycle']=='idle' and x['children_after']==[]
  assert all(not s['cgroup_memory_events']['oom'] and not s['cgroup_memory_events']['oom_kill'] for s in x['stages'])
 assert old['cache_bytes']==new['cache_bytes'] and old['cache_sha256']==new['cache_sha256']==hashlib.sha256((b/'fixture'/f'{name}.json').read_bytes()).hexdigest()
 assert old['exact_actuals_and_disclosures_digest']==new['exact_actuals_and_disclosures_digest']
 assert new['sampled_peak_increment']<old['sampled_peak_increment'] and new['retained_increment']<old['retained_increment']
 rows.append(dict(fixture=name,cache_bytes=new['cache_bytes'],cache_sha256=new['cache_sha256'],standard_decoder_peak_increment=old['sampled_peak_increment'],sharing_peak_increment=new['sampled_peak_increment'],standard_retained_increment=old['retained_increment'],sharing_retained_increment=new['retained_increment'],standard_seconds=old['seconds'],sharing_seconds=new['seconds'],standard_component_graph_bytes=old['component_owned_graph_bytes'],sharing_component_graph_bytes=new['component_owned_graph_bytes'],union_graph_before=old['union_graph_bytes'],union_graph_after=new['union_graph_bytes'],exact_evidence_digest=new['exact_actuals_and_disclosures_digest'],control_scope=old['decode_control']))
warm=json.loads((b/'warm-cycles-candidate.json').read_text());assert warm['source_head']==source['candidate'] and warm['source_tree']==source['tree'] and warm['working_tree_clean'] and warm['passed'] and len(warm['cycles'])==3
native=json.loads((b/'native-resource-final/result.json').read_text());pre=json.loads((b/'local-preflight/result.json').read_text())
for x in [native,pre]:assert x['head']==source['candidate'] and x['tree']==source['tree'] and x['passed'] and x['scratch_removed']
assert native['explicit_retry_completed'] and native['fois_reserve_preserved']
assert all(x['server_ms']<500 for x in native['liveness']+pre['liveness'])
# Replay supplied historical inputs with today's unchanged pure calculation;
# this is not a fresh production sample or proof of the earlier503 branch.
historical=restoration_admission(35531769,{'cgroup_current_bytes':2147483648-670416896,'cgroup_limit_bytes':2147483648},False,fois_working_bytes=WORKING_RESERVE_BYTES,fois_safety_bytes=SAFETY_MARGIN_BYTES)
assert historical['required_bytes']==702726032 and historical['would_admit'] is False
kernel_cases=[]
for name in ['oneqb','superflex','oneqb-diverse','oneqb-unicode']:
 new=json.loads((b/f'profile-{name}-kernel-final.json').read_text());old=json.loads((b/f'profile-{name}-kernel-standard.json').read_text())
 for x in [old,new]:
  assert x['source_head']==source['candidate'] and x['source_tree']==source['tree'] and x['working_tree_clean'] and x['passed']
  assert x['owned_retained_file'] and x['owned_cache_scratch_removed'] and x['operation_established_new_peak']
  assert x['operation_kernel_peak_bytes']>x['prior_kernel_peak_bytes']
  assert x['stages'][0]['file_bytes']>=x['cache_bytes'] and x['enforced_limit']==2147483648 and x['swap_limit']==0
 assert old['cache_sha256']==new['cache_sha256'] and old['exact_actuals_and_disclosures_digest']==new['exact_actuals_and_disclosures_digest']
 assert new['operation_kernel_peak_increment']<old['operation_kernel_peak_increment'] and new['retained_increment']<old['retained_increment']
 kernel_cases.append(dict(fixture=name,bytes=new['cache_bytes'],sha256=new['cache_sha256'],old_kernel_increment=old['operation_kernel_peak_increment'],new_kernel_increment=new['operation_kernel_peak_increment'],old_retained_increment=old['retained_increment'],new_retained_increment=new['retained_increment'],old_seconds=old['seconds'],new_seconds=new['seconds'],initial_file_bytes=new['stages'][0]['file_bytes'],old_sampled_increment=old['sampled_peak_increment'],new_sampled_increment=new['sampled_peak_increment'],old_absolute_kernel_peak=old['operation_kernel_peak_bytes'],new_absolute_kernel_peak=new['operation_kernel_peak_bytes'],python=new['python'],new_peak_established_before_postmeasurement_graph_walk=True))
out=dict(kernel_cases=kernel_cases,candidate=source['candidate'],tree=source['tree'],passed=True,comparison=rows,warm_cycles=warm['cycles'],warm_sampled_peak_increment=warm['sampled_peak_increment'],native_resource_kernel_peak=native['kernel_lifetime_peak_bytes'],native_worker_cleanup=native['cleanup_processes'],liveness=native['liveness'],preflight_liveness=pre['liveness'],supplied_historical_policy_replay=historical,historical_scope='Replayed supplied Nov6 15:21Eastern inputs only; not a new production measurement.',limitations=['New modeled cohorts are not private Granite and missing reference-analysis distribution is unverified.','Standard-decoder control substitutes only the pre-change decoder inside the final source; all admission/binding/publication logic and exact payloads are identical. Original baseline source captures are retained separately.','Standalone component graphs overlap; do not add them. Five-ms sampled peaks are not hard worst-case bounds.','Finite cleanup cycles do not establish long-term leak freedom. No production cache/read/entry/parity is claimed.'])
(b/'cache-memory-verified.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'passed':True,'source':source['candidate'],'comparisons':[(r['fixture'],r['standard_decoder_peak_increment']-r['sharing_peak_increment'],r['standard_retained_increment']-r['sharing_retained_increment']) for r in rows],'unchanged_historical_verdict':historical['would_admit']}))
