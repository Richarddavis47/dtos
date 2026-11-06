"""Two bounded read-only native-source requests; no DTOS league entry or sync."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
from urllib.request import Request,urlopen

root='https://api.sleeper.app/v1';league_id='1314695233040052224';player_id='4984'
def read(path):
 start=datetime.now(timezone.utc).isoformat()
 with urlopen(Request(root+path,headers={'Accept':'application/json'}),timeout=20) as response:
  body=response.read(1024*1024+1)
  if len(body)>1024*1024:raise ValueError('Bounded source response exceeded1MiB')
  return json.loads(body),dict(url=root+path,started_at=start,retrieved_at=datetime.now(timezone.utc).isoformat(),
      response_sha256=hashlib.sha256(body).hexdigest(),response_bytes=len(body),http_status=response.status,
      provider_publication_time='not_established',http_date=response.headers.get('Date'))
league,first=read('/league/'+league_id)
assert str(league.get('league_id'))==league_id and str(league.get('season')).isdigit()
week=(league.get('settings') or {}).get('last_scored_leg')
assert type(week) is int and 1<=week<=18,'No authoritative completed-week boundary; no matchup read performed'
rows,second=read('/league/'+league_id+'/matchups/'+str(week))
assert isinstance(rows,list) and len(rows)<=64
scores=[]
for row in rows:
 starters=list(map(str,row.get('starters') or []));score_map=row.get('players_points') or {}
 if player_id not in score_map and player_id not in starters:continue
 index=starters.index(player_id) if player_id in starters else None
 values=row.get('starters_points') or []
 scores.append(dict(roster_id=row.get('roster_id'),player_id=player_id,
   player_map_present=player_id in score_map,player_map_score=score_map.get(player_id),
   starter_index=index,starter_score_present=index is not None and index<len(values),
   starter_score=values[index] if index is not None and index<len(values) else None))
scoring=league.get('scoring_settings') or {}
report=dict(scope='Fresh public native Sleeper metadata and one selected-player/week score slice; no owner-authenticated DTOS view or production recovery verified.',
 league_id=league_id,season=str(league['season']),week=week,player_id=player_id,
 selected_week_basis='Sleeper league settings.last_scored_leg',scoring_settings=scoring,
 roster_positions=league.get('roster_positions'),calendar_settings={k:(league.get('settings') or {}).get(k) for k in ('leg','last_scored_leg','start_week','playoff_week_start','playoff_teams','playoff_round_type','playoff_type')},
 source_league_status=league.get('status'),source_sport=league.get('sport'),scores=scores,requests=[first,second],
 source_payloads_exported=False,other_players_or_account_identifiers_exported=False,production_requests=0,
 limitations=['A completed league week is not independent proof of individual game participation.','The retained score slice is not the complete native response; hashes identify the original bounded responses.','No assertion is made about current DTOS cache preparation, source generation or authenticated presentation.'])
Path('/workspace/2234-release/native-sleeper-selected-score.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['scope','league_id','season','week','player_id','scores','production_requests']},indent=2))
