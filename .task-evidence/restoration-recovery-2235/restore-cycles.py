"""Six real same-process restore/close cycles on sealed synthetic inputs.

Stage hooks call the original functions unchanged. No admission or memory
telemetry is mocked. This is not a private Granite payload profile, not a leak-
freedom proof, and includes explicit harness GC/trim after close.
"""
import asyncio,gc,hashlib,json,os,shutil,subprocess,sys,tempfile,threading,time,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/app')
root=Path('/evidence');out=root/'cycles';out.mkdir(exist_ok=True)
report={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'scope':__doc__,'cycles':[],'passed':False}
assert report['head']==os.environ['DTOS_EXPECTED_HEAD']
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
with tempfile.TemporaryDirectory(prefix='restore-cycles-') as name:
 scratch=Path(name)
 with zipfile.ZipFile('/prior/Granite-cache-restoration-memory-profile.zip') as z:
  for n in ['oneqb.json','superflex.json','projections.sqlite3']:
   (scratch/n).write_bytes(z.read('granite-scale/'+n))
 for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:
  os.environ['DTOS_'+key+'_FILE']=str(scratch/(key.lower()+'.sqlite3'))
 os.environ.update(DTOS_PROJECTION_DB_FILE=str(scratch/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',DTOS_HISTORY_STORAGE_ROOT=name,DTOS_SLEEPER_SEASON_CACHE_ROOT=str(scratch/'season'),SLEEPER_BASE_URL='http://127.0.0.1:9/v1')
 import dtos_app,psutil
 from services import league_preparation as prep
 from src.core.league_runtime import LeagueRuntime
 from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator
 from src.platform.memory_reclamation import release_unused_allocator_pages
 assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
 def sample(label):
  stat=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
  return dict(label=label,monotonic=time.monotonic(),**memory_snapshot(),**{k:int(stat[k]) for k in ['anon','file','inactive_file']})
 original=json.load
 try:
  for n in range(6):
   path=scratch/('oneqb.json' if n%2==0 else 'superflex.json')
   # Read only the known synthetic fixture to establish its identity before the
   # operation. This is preparation and excluded from observed restore peak.
   source=json.loads(path.read_bytes());league=source['data']['league'];slots=league['roster_positions'];league_id=str(league['league_id']);season=int(league['season']);del source,league
   gc.collect();release_unused_allocator_pages()
   before=sample('before_restore');stages=[];samples=[];stop=threading.Event()
   def watch():
    while not stop.wait(.005):samples.append((time.monotonic(),memory_snapshot()['cgroup_current_bytes']))
   def decode(*a,**kw):
    stages.append(sample('before_json_decode'));data=original(*a,**kw);stages.append(sample('after_json_decode'));return data
   def publish(r):
    stages.append(sample('after_materialization'))
    projections=dtos_app.ProjectionService(league_id=r.league_id,scoring_profile_id=r.scoring_profile)
    attached=projections.restore_into(r.state['data']);stages.append(sample('after_projection_restore'))
    dtos_app._publish_runtime_context(r,projections);stages.append(sample('after_canonical_publication'))
    assert attached>0
   r=LeagueRuntime(league_id);thread=threading.Thread(target=watch);thread.start();began=time.monotonic()
   try:
    with patch.object(prep,'league_cache_file',return_value=path),patch.object(prep.json,'load',side_effect=decode):assert prep.restore_cached_runtime(r,publish,expected_season=season)
   finally:stop.set();thread.join()
   assert r.state['data']['league']['roster_positions']==slots
   retained=sample('after_restore');asyncio.run(r.close());assert not r.state['data'] and not r.background_tasks and r.canonical_context is None and r.projection_context is None
   del r;gc.collect();release_unused_allocator_pages();after=sample('after_close_harness_gc_trim')
   report['cycles'].append(dict(cycle=n+1,cache_bytes=path.stat().st_size,cache_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),seconds=time.monotonic()-began,before=before,stages=stages,retained=retained,after=after,sampled_peak_increment=max([before['cgroup_current_bytes'],retained['cgroup_current_bytes'],*[s[1] for s in samples]])-before['cgroup_current_bytes']))
  assert not psutil.Process().children(recursive=True)
  assert lifecycle_coordinator.snapshot()['phase']=='idle'
  report['kernel_lifetime_peak_bytes']=int(Path('/sys/fs/cgroup/memory.peak').read_text());report['final_memory']=memory_snapshot();assert not report['final_memory']['cgroup_memory_events']['oom_kill']
  report['no_children']=True
 finally:(out/'result-incomplete.json').write_text(json.dumps(report,indent=2)+'\n')
report['scratch_removed']=not scratch.exists();assert report['scratch_removed'];report['passed']=True
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'cycles':len(report['cycles']),'increment_peaks':[r['sampled_peak_increment'] for r in report['cycles']],'post_close_usage':[r['after']['cgroup_current_bytes'] for r in report['cycles']]}))
