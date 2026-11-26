"""Join matched instrumented tests and the original exact-case full run samples."""
from collections import Counter
import json,sys
from common import BASE,digest,load_source,write_json
root=BASE/(sys.argv[1] if len(sys.argv)==2 else 'focused-memory-attribution')
admission_comparison=json.loads((BASE/'current-exact-rebuild-resource-comparison.json').read_text())
def families(sample):
    by=Counter()
    for p in sample['processes']:
        if p['pss'] is not None:
            by[p['name']]+=p['pss']
    return dict(by)
summary={}
for label in ('baseline','candidate'):
    out=root/label
    result=json.loads((out/'result.json').read_text())
    trace=[json.loads(line) for line in (out/'memory-original.jsonl').open()]
    a=next(i for i,row in enumerate(trace) if row['phase']=='start' and 'test_full_rosters_unseeded' in row['test'])
    z=next(i for i in range(a+1,len(trace)) if trace[i]['phase']=='stop')
    rows=[row for row in trace[a:z] if row['phase']=='admission']
    smallest=min(rows,key=lambda r:r['diagnostic']['observation']['admission_headroom_bytes'])
    snapshots={k:dict(cgroup=row['cgroup'],stats=row['stats'],pss=families(row),
                      driver_pids=[proc['pid'] for proc in row['processes'] if proc['name']=='MainThread'])
               for k,row in [('first_test_start',trace[0]),('rebuild_start',trace[a]),
                    ('rebuild_tightest_admission',smallest),('rebuild_stop',trace[z]),('last_test_stop',trace[-1])]}
    summary[label]=dict(result=result,rebuild_admissions=len(rows),
        narrowest_rebuild_headroom_bytes=smallest['diagnostic']['observation']['admission_headroom_bytes'],
        snapshots=snapshots,
        originals={f.name:digest(f) for f in out.iterdir() if f.is_file()})
expected=load_source()
assert summary['baseline']['result']['commit']==expected['baseline']
assert summary['candidate']['result']['commit']==expected['candidate']
assert all(row['result']['passed'] and row['rebuild_admissions']==17 for row in summary.values())
from zipfile import ZipFile
hosted_archive=ZipFile(BASE/'hosted-large-current/canonical-failed-original.zip')
def pre_test_sample(opener, label):
    with opener('memory.jsonl') as stream:
        cutoff=admission_comparison[label]['test_events'][0]['time']
        before=max((row for line in stream if -2 < (row:=json.loads(line))['time']-cutoff <= 0),
                   key=lambda row:row['time'])
    return dict(time_before_start=before['time']-cutoff, memory=before['memory'],
                processes_by_pss=families(before), driver_processes=[p for p in before['processes']
                    if p['name'] not in ('python','python3')])
before={'hosted':pre_test_sample(hosted_archive.open,'hosted'),
        'local':pre_test_sample(lambda name:(BASE/'canonical-original'/name).open('rb'),'local')}
write_json(root/'comparison.json',dict(source=expected,matched=summary,before_full_rebuild=before,full={
    k:dict(observation=admission_comparison[k]['tightest_observation']['diagnostic']['observation'],
           samples=admission_comparison[k]['nearest_memory_samples'])
    for k in ('hosted','local')},
    limits='Focused journey ran after the same nine tests on each tree. It does not reproduce the full canonical process or establish the cause of hosted process variation. PSS accounting is from the observed process tree.'))
for label,row in summary.items():
    s=row['snapshots']
    print(label,row['result']['tests'],row['narrowest_rebuild_headroom_bytes'],row['result']['peak'],
        'rebuild start',s['rebuild_start'],'tightest',s['rebuild_tightest_admission'],
        'rebuild stop',s['rebuild_stop'])
