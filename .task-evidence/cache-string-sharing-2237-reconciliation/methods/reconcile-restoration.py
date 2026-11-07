"""Decoder-only reconciliation on one immutable source and retained fake payloads."""
import argparse,asyncio,gc,hashlib,inspect,json,logging,os,subprocess,sys,tempfile,threading,time,weakref
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/app')
p=argparse.ArgumentParser();p.add_argument('--decoder',choices=['standard','shipping'],required=True);p.add_argument('--fixture',required=True);p.add_argument('--repeat',type=int,required=True);a=p.parse_args()
b=Path('/evidence');out=b/'reconciliation';root=b/'fixture'
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:os.environ['DTOS_'+key+'_FILE']=str(root/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
import dtos_app,psutil
from services import league_preparation as prep,player_evidence
from src.core.league_runtime import LeagueRuntime
from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator
from src.platform.memory_reclamation import release_unused_allocator_pages
from src.core.valuation_intelligence import engine
logging.disable(logging.CRITICAL)
assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
expected='1e1234fbcf7ca18f3862e5cdeac1451780e51b49';head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head==expected
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
source_path=root/(a.fixture+'.json');digest_function=engine._semantic_digest;digest_source=hashlib.sha256(inspect.getsource(digest_function).encode()).hexdigest();decoder=json.load if a.decoder=='standard' else prep.load_cache_json;bind_function=player_evidence.bind_retained_actuals
stages=[];samples=[];stop=threading.Event();timings={}
def sample(label):
 stat=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines());row=dict(label=label,t=time.monotonic(),**memory_snapshot(),anon=int(stat['anon']),file=int(stat['file']),inactive_file=int(stat['inactive_file']),kernel=int(stat['kernel']),kernel_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text()));stages.append(row);return row

def watch():
 while not stop.wait(.005):samples.append(memory_snapshot()['cgroup_current_bytes'])

def decode(handle):
 sample('before_decode');t=time.monotonic();value=decoder(handle);timings['decode']=time.monotonic()-t;sample('after_decode');return value

def bind(*args,**kwargs):
 sample('before_evidence_binding');t=time.monotonic();value=bind_function(*args,**kwargs);timings['evidence_binding']=time.monotonic()-t;sample('after_evidence_binding');return value

def publish(runtime):
 sample('after_materialization');t=time.monotonic();projection=dtos_app.ProjectionService(league_id=runtime.league_id,scoring_profile_id=runtime.scoring_profile);projection.restore_into(runtime.state['data']);timings['projection_restore']=time.monotonic()-t;sample('after_projection_restore');t=time.monotonic();dtos_app._publish_runtime_context(runtime,projection);timings['canonical_publication']=time.monotonic()-t;sample('after_canonical_publication')

with tempfile.TemporaryDirectory(prefix='decoder-isolation-') as directory:
 import shutil
 path=Path(directory)/'cache.json'
 with source_path.open('rb') as r,path.open('wb') as w:shutil.copyfileobj(r,w,1024*1024);w.flush();os.fsync(w.fileno())
 runtime=LeagueRuntime('superflex-rich' if a.fixture=='superflex' else 'oneqb-rich');ref=weakref.ref(runtime)
 gc.collect();release_unused_allocator_pages();initial=sample('before_restore');prior_peak=initial['kernel_peak'];monitor=threading.Thread(target=watch);monitor.start();started=time.monotonic()
 try:
  with patch.object(prep,'league_cache_file',return_value=path),patch.object(prep,'load_cache_json',side_effect=decode),patch.object(player_evidence,'bind_retained_actuals',side_effect=bind):
   assert prep.restore_cached_runtime(runtime,publish,expected_season=2026)
 finally:stop.set();monitor.join()
 elapsed=time.monotonic()-started;retained=sample('retained_after_publication');operation_peak=retained['kernel_peak'];assert operation_peak>prior_peak
 assert engine._semantic_digest is digest_function
 # Verification and graph accounting are strictly after full operation peak.
 data=runtime.state['data'];h=hashlib.sha256()
 for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).iterencode(data):h.update(chunk.encode())
 def size(value,seen):
  identity=id(value)
  if identity in seen:return 0
  seen.add(identity);n=sys.getsizeof(value)
  if isinstance(value,dict):n+=sum(size(k,seen)+size(v,seen) for k,v in value.items())
  elif isinstance(value,(list,tuple)):n+=sum(size(v,seen) for v in value)
  return n
 components={key:size(data.get(key),set()) for key in ['players','normalized_players','season_matchups','canonical_player_production','projection_intelligence','valuation_intelligence','teams','team_strength']}
 components['derived_actuals']=size(data['canonical_player_production']['sleeper_actuals'],set());components['consumer_disclosures']=size({key:asset['canonical_production'] for key,asset in data['valuation_intelligence']['assets'].items()},set());union=size(data,set())
 # Ordered exclusive attribution is explicitly order dependent, unlike standalone graphs.
 seen=set();exclusive={}
 for key in ['players','normalized_players','season_matchups','canonical_player_production','valuation_intelligence','projection_intelligence','team_strength','teams']:
  exclusive[key]=size(data.get(key),seen)
 actuals=data['canonical_player_production']['sleeper_actuals'];observation_count=sum(map(len,actuals['players'].values()));del actuals,data
 del seen
 asyncio.run(runtime.close());del runtime;gc.collect();release_unused_allocator_pages();cleanup=sample('after_close_gc_trim');assert ref() is None and not psutil.Process().children(recursive=True)
 assert lifecycle_coordinator.snapshot()['phase']=='idle'
 report=dict(decoder=a.decoder,fixture=a.fixture,repeat=a.repeat,head=head,tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),python=sys.version,payload_bytes=source_path.stat().st_size,payload_sha256=hashlib.file_digest(source_path.open('rb'),'sha256').hexdigest(),digest_helper_sha256=digest_source,digest_helper_unmodified=engine._semantic_digest is digest_function,digest_scope='Both sides use the shipping _semantic_digest; no digest/asdict/admission changes.',instrumentation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),enforced_limit=2147483648,swap_limit=0,seconds=elapsed,timings=timings,initial=initial,retained=retained,stages=stages,prior_kernel_peak=prior_peak,operation_kernel_peak=operation_peak,peak_increment=operation_peak-initial['cgroup_current_bytes'],retained_increment=retained['cgroup_current_bytes']-initial['cgroup_current_bytes'],sampled_peak_increment=max(samples+[x['cgroup_current_bytes'] for x in stages if x['label']!='after_close_gc_trim'])-initial['cgroup_current_bytes'],full_publication_digest=h.hexdigest(),component_standalone_graph_bytes=components,ordered_exclusive_graph_bytes=exclusive,union_graph_bytes=union,observation_count=observation_count,cleanup=cleanup,runtime_released=ref() is None,children_after=[],lease_phase='idle',scratch_removed=False,limits=['Disposable synthetic structures,not privateGranite or live parity.','Five-ms Python sampling can miss GIL-bound C-decoder transients; operation kernel peak is primary and established above prior peak.','Graph walks/digest happen after captured operation peak and do not measure RSS; standalone groups overlap; exclusive attribution is order dependent.','Owned file pages are charged before baseline; no cache deductions or clearing.','After-close GC/allocator trim is disclosed harness cleanup; finite runs do not prove long-term leak freedom.'])
 assert all(x['cgroup_memory_events']['oom']==x['cgroup_memory_events']['oom_kill']==0 for x in stages)
report['after_scratch_cleanup']=sample('after_scratch_unlink');report['scratch_removed']=not Path(directory).exists();assert report['scratch_removed'];out.mkdir(exist_ok=True);(out/f'{a.fixture}-{a.decoder}-{a.repeat}.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['decoder','fixture','repeat','seconds','peak_increment','retained_increment','full_publication_digest']}))
