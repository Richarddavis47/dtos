"""Matched two-publication residency, eviction and reopening; synthetic only."""
import asyncio,gc,hashlib,json,logging,os,subprocess,sys,threading,time,weakref
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/app')
b=Path('/evidence');root=b/'fixture'
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:os.environ['DTOS_'+key+'_FILE']=str(root/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
import dtos_app,psutil
from services import league_preparation as prep
from src.core.league_runtime import LeagueRuntime
from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator
from src.platform.memory_reclamation import release_unused_allocator_pages
logging.disable(logging.CRITICAL)
mode='candidate' if hasattr(prep,'load_cache_json') else 'baseline'
result={'mode':mode,'source_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'working_tree_clean':not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),'passed':False,'stages':[],'limitations':['Synthetic producer-derived cohorts; not private Granite structure or production access.','No reserve/telemetry mocks. Actual two league runtimes/publications; no forced Market build or provider IO.','5ms samples may miss transient peaks. After-close GC/allocator trim is harness instrumentation, not a new production cleanup.','Finite cycles cannot establish long-term leak freedom. No production cache-size attribution.']}
assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
samples=[];stop=threading.Event()
def sample(label):
 x={'label':label,**memory_snapshot()};result['stages'].append(x);return x

def watch():
 while not stop.wait(.005):samples.append(memory_snapshot()['cgroup_current_bytes'])

def publish(r):
 p=dtos_app.ProjectionService(league_id=r.league_id,scoring_profile_id=r.scoring_profile);p.restore_into(r.state['data']);dtos_app._publish_runtime_context(r,p)

def restore(name):
 r=LeagueRuntime('oneqb-rich' if name=='oneqb' else 'superflex-rich')
 with patch.object(prep,'league_cache_file',return_value=root/(name+'.json')):assert prep.restore_cached_runtime(r,publish,expected_season=2026)
 d=r.state['data'];assert d['canonical_player_production']['sleeper_actuals']['source_generation']==d['season_matchups']['semantic_generation']
 assert d['valuation_intelligence']['assets']
 return r

gc.collect();release_unused_allocator_pages();initial=sample('initial');monitor=threading.Thread(target=watch);monitor.start();started=time.monotonic();refs=[];runtimes=[]
try:
 sf=restore('superflex');runtimes.append(sf);sample('warm_superflex')
 result['cycles']=[]
 for cycle in range(3):
  before=memory_snapshot();start=time.monotonic();qb=restore('oneqb');sample('two_warm_'+str(cycle));d=qb.state['data'];a=d['canonical_player_production']['sleeper_actuals'];h=hashlib.sha256()
  for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':')).iterencode({'native':d['season_matchups'],'actuals':a}):h.update(chunk.encode())
  result['cycles'].append({'index':cycle,'seconds':time.monotonic()-start,'native_digest':h.hexdigest(),'after_bytes':memory_snapshot()['cgroup_current_bytes'],'before_bytes':before['cgroup_current_bytes'],'observations':sum(map(len,a['players'].values()))})
  refs.append(weakref.ref(qb));asyncio.run(qb.close());del qb,d,a;gc.collect();release_unused_allocator_pages();sample('oneqb_closed_'+str(cycle))
 assert all(ref() is None for ref in refs)
 asyncio.run(sf.close());runtimes.clear();del sf;gc.collect();release_unused_allocator_pages();sample('all_closed')
 assert lifecycle_coordinator.snapshot()['phase']=='idle'
 assert not psutil.Process().children(recursive=True)
 assert all(x['cgroup_memory_events']['oom']==x['cgroup_memory_events']['oom_kill']==0 for x in result['stages'])
 assert len({x['native_digest'] for x in result['cycles']})==1
 result['passed']=True
finally:
 stop.set();monitor.join();result['seconds']=time.monotonic()-started;result['sampled_peak_increment']=max(samples+[x['cgroup_current_bytes'] for x in result['stages']])-initial['cgroup_current_bytes'];result['kernel_lifetime_peak_bytes']=int(Path('/sys/fs/cgroup/memory.peak').read_text());(b/('warm-cycles-'+mode+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['mode','passed','seconds','sampled_peak_increment']}))
