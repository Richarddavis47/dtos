"""Fail closed on confounded or incomplete decoder comparisons."""
from pathlib import Path
from statistics import median
import json,re
BASELINE='1e1234fbcf7ca18f3862e5cdeac1451780e51b49'
TREE='4051883efb1f225dcd71e07f1998e45c9d96fb39'
def verify_pair(a,b):
 assert a['decoder']=='standard' and b['decoder']=='shipping'
 for key in ['head','tree','fixture','repeat','payload_bytes','payload_sha256','digest_helper_sha256','instrumentation_sha256','python','full_publication_digest','observation_count','enforced_limit','swap_limit']:
  assert a[key]==b[key],key
 assert a['head']==BASELINE and a['tree']==TREE and a['enforced_limit']==2147483648 and a['swap_limit']==0
 for x in [a,b]:
  assert x['digest_helper_unmodified'] is True
  assert x['operation_kernel_peak']>x['prior_kernel_peak']
  assert x['peak_increment']==x['operation_kernel_peak']-x['initial']['cgroup_current_bytes']
  assert x['retained_increment']==x['retained']['cgroup_current_bytes']-x['initial']['cgroup_current_bytes']
  assert x['runtime_released'] and not x['children_after'] and x['scratch_removed'] and x['lease_phase']=='idle'
  assert all(row['cgroup_memory_events']['oom']==row['cgroup_memory_events']['oom_kill']==0 for row in x['stages'])
 return {'fixture':a['fixture'],'repeat':a['repeat'],'standard_peak':a['peak_increment'],'shipping_peak':b['peak_increment'],'peak_saved':a['peak_increment']-b['peak_increment'],'standard_retained':a['retained_increment'],'shipping_retained':b['retained_increment'],'retained_saved':a['retained_increment']-b['retained_increment'],'standard_seconds':a['seconds'],'shipping_seconds':b['seconds']}

def analyze(root):
 rows=[];groups=[]
 for fixture in ['oneqb','superflex','oneqb-diverse','oneqb-unicode']:
  pairs=[]
  for repeat in [2,3,4]:
   a=json.loads((root/f'{fixture}-standard-{repeat}.json').read_text());b=json.loads((root/f'{fixture}-shipping-{repeat}.json').read_text());pairs.append(verify_pair(a,b))
  rows+=pairs
  groups.append({'fixture':fixture,**{key:median(r[key] for r in pairs) for key in ['standard_peak','shipping_peak','peak_saved','standard_retained','shipping_retained','retained_saved','standard_seconds','shipping_seconds']}})
 assert len(rows)==12
 focus=(root/'focused-baseline-original.log').read_text();assert re.search(r'Ran 63 tests in [0-9.]+s\s+OK\s*$',focus)
 pressure=json.loads((root/'clean-shipping-pressure.json').read_text());assert pressure['passed'] and pressure['cases']['deferred_before_release'] and pressure['cases']['completed_after_release'] and pressure['scratch_removed'] and not pressure['children_after']
 shipping=json.loads((root/'clean-shipping-matched.json').read_text());prototype=json.loads((root/'clean-shipping-detached-prototype.json').read_text());assert shipping['instrumentation_sha256']==prototype['instrumentation_sha256'] and shipping['head']==prototype['head']==BASELINE
 for x in [shipping,prototype]:assert x['passed'] and not x['children_after'] and x['scratch_removed'] and len(x['cases']['cycles'])==3
 return {'baseline':BASELINE,'tree':TREE,'decoder_pairs':12,'new_controlled_restorations':24,'fixtures':4,'repeats_per_fixture':3,'rows':rows,'medians':groups,'focused_tests':63,'peak_saving_bytes_range':[min(r['peak_saved'] for r in rows),max(r['peak_saved'] for r in rows)],'retained_saving_bytes_range':[min(r['retained_saved'] for r in rows),max(r['retained_saved'] for r in rows)],'prior_comparison':'Combined decoder and streaming-digest substitution,not decoder-only; original files and immutable release unchanged.','clean_lifecycle':'No graph or full-payload digest before cleanup; GC/trim and file unlink are separately identified. Remaining anonymous memory is not automatically a leak.','pressure_case':pressure['cases'],'production_changes':False,'live_preflight':'HELD:no Render Shell/SSH executor; existing Opera connector UNAVAILABLE/not connected; unchanged external401binding not retried.','granite_entry':'Not attempted; cannot grant admission from fixture results.','live_actual_score_parity':'Not obtained.'}

if __name__=='__main__':
 root=Path('/evidence/reconciliation') if Path('/evidence/reconciliation').exists() else Path(__file__).parent/'reconciliation'
 result=analyze(root);(root/'verified-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
