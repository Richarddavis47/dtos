"""New producer-derived cohort over existing sealed synthetic identities, not private Granite."""
import asyncio,copy,json,hashlib,os,sys,tempfile,zipfile
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
sys.path.insert(0,'/app')
b=Path('/evidence');root=b/'fixture';root.mkdir(exist_ok=True)
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:
 os.environ['DTOS_'+key+'_FILE']=str(root/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
archive=Path('/prior/Granite-cache-restoration-memory-profile.zip');assert hashlib.sha256(archive.read_bytes()).hexdigest()=='df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439'
from src.core.data_platform.normalization import PlayerIdentityResolver
from services.matchup_season import prepare_season_matchups
from services.player_evidence import prepare_player_production,bind_retained_actuals
from tools.validation.generate_sanitized_market_fixture import fixture_valuation_intelligence
metadata=[]
with zipfile.ZipFile(archive) as z:
 (root/'projections.sqlite3').write_bytes(z.read('granite-scale/projections.sqlite3'))
 for name in ['oneqb','superflex']:
  payload=json.loads(z.read('granite-scale/'+name+'.json'));data=payload['data'];league=data['league'];league.update(sport='nfl',status='in_season');league['settings'].update(leg=9,last_scored_leg=8,start_week=1,playoff_week_start=15,playoff_teams=6,playoff_round_type=0,playoff_type=0);data['week']=9
  resolver=PlayerIdentityResolver(data['players']);data['normalized_players']={pid:asdict(p) for pid in data['players'] if(p:=resolver.resolve(pid))}
  ids=list(dict.fromkeys([str(p['id']) for t in data['teams'] for p in t['players']]+list(data['players'])))[:991]
  data['relevant_player_universe']={'member_ids':ids}
  rows=[]
  for team in data['teams']:
   pids=[str(p['id']) for p in team['players']];scores={pid:(0 if i==0 else -2.125 if i==1 else 23.4738) for i,pid in enumerate(pids)};rows.append(dict(roster_id=team['roster_id'],players=pids,starters=pids[:1],players_points=scores,starters_points=[scores[pids[0]]]))
  async def fetch(_):return rows
  data['season_matchups']=asyncio.run(prepare_season_matchups(league,9,rows,fetch,observed_at='2026-11-06T20:00:00Z'))
  data['canonical_player_production']=prepare_player_production(data,expected_league_id=str(league['league_id']),as_of='2026-11-06T20:00:00Z',path=root/'absent-global.sqlite3')
  report=fixture_valuation_intelligence();base=next(iter(report['assets'].values()));report['assets']={f'player:{pid}':{**copy.deepcopy(base),'asset_id':f'player:{pid}','display_name':data['normalized_players'][pid]['name']} for pid in ids};report['asset_count']=len(ids);data['valuation_intelligence']=report;bind_retained_actuals(data,expected_league_id=str(league['league_id']))
  payload['last_sync']=datetime.now(timezone.utc).isoformat();path=root/(name+'.json');path.write_text(json.dumps(payload,separators=(',',':'),ensure_ascii=False));component={k:len(json.dumps(v,separators=(',',':'),ensure_ascii=False).encode()) for k,v in data.items()}
  metadata.append(dict(name=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),catalog=len(data['players']),normalized=len(data['normalized_players']),prepared_players=len(data['canonical_player_production']['players']),consumer_assets=len(report['assets']),native_observations=sum(map(len,data['canonical_player_production']['sleeper_actuals']['players'].values())),component_bytes=component,native_bytes=len(json.dumps(data['season_matchups'],separators=(',',':')).encode()),actuals_bytes=len(json.dumps(data['canonical_player_production']['sleeper_actuals'],separators=(',',':')).encode()),disclosures_bytes=sum(len(json.dumps(a['canonical_production'],separators=(',',':')).encode()) for a in report['assets'].values()),scope='Native values fictional; actual identity normalization/preparation/binding functions. Cohort991 is a modeled declared population, not measured private production count. Existing synthetic raw identities retained, no byte-size padding added.'))
(b/'fixture-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps(metadata))
