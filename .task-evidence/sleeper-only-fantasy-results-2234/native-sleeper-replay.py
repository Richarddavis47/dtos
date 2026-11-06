"""Replay only the bounded native score slice; no additional source requests."""
import sys
sys.path.insert(0,'/app')
from dataclasses import asdict
import hashlib,json
from pathlib import Path
import subprocess

from services.player_evidence import attach_sleeper_actuals
from src.core.player_value_projection.canonical_production import prepared_production_context
from src.core.player_value_projection.sleeper_actuals import scoring_identity
from src.ui.canonical_production import production_panel
from src.platform.lifecycle import memory_snapshot

b=Path('/evidence');source=json.loads((b/'native-sleeper-selected-score.json').read_text());identity=json.loads((b/'source.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==identity['candidate']
rows=[]
for score in source['scores']:
 pid=score['player_id'];index=score['starter_index'];starters=['0']*index+[pid] if index is not None else []
 actuals=[None]*index+[score['starter_score']] if score['starter_score_present'] else []
 rows.append(dict(roster_id=score['roster_id'],players=[pid],starters=starters,starters_points=actuals,
                  players_points={pid:score['player_map_score']} if score['player_map_present'] else {}))
league=dict(league_id=source['league_id'],season=source['season'],scoring_settings=source['scoring_settings'],
            settings=source['calendar_settings'],sport=source['source_sport'],status=source['source_league_status'],roster_positions=source['roster_positions'])
stamp=source['requests'][-1]['retrieved_at'];fingerprint=scoring_identity(source['scoring_settings'])
week=source['week'];generation=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
data=dict(league=league,scoring_settings=source['scoring_settings'],week=source['calendar_settings']['leg'],
          season_matchups=dict(methodology='matchup-season-presentation-v1',league_id=source['league_id'],season=source['season'],
              scoring_fingerprint=fingerprint,semantic_generation=generation,observed_at=stamp,
              weeks={str(week):dict(rows=rows,availability='available',freshness='current',observed_at=stamp,retrieved_at=stamp,last_attempt_at=stamp)}))
snapshot=dict(league_id=source['league_id'],season=int(source['season']),scoring_fingerprint=fingerprint,players={})
attach_sleeper_actuals(data,snapshot)
profile=prepared_production_context(snapshot,league_id=source['league_id'],player_id=source['player_id'],data=data)
assert len(profile.observations)==len(source['scores'])==1
assert profile.observations[0]['points']==source['scores'][0]['player_map_score']==source['scores'][0]['starter_score']
assert profile.windows[3].observation_count==profile.windows[3].scored_count==1
assert profile.windows[3].fantasy_points==26.56
html=production_panel(asdict(profile));assert '26.56 fantasy points per score observation' in html
(b/'native-sleeper-component.html').write_text(html)
report=dict(candidate=identity['candidate'],tree=identity['tree'],source_capture_sha256=hashlib.sha256((b/'native-sleeper-selected-score.json').read_bytes()).hexdigest(),
            source_scores=source['scores'],interpreted=asdict(profile),direct_source_value_matches=True,rendered_component_matches=True,
            memory=memory_snapshot(),scope='Frozen slice from two public native-source reads -> exact candidate actual-results adapter and shared presentation component. Not an authenticated production route or complete league publication. Uncaptured weeks remain unacquired; no extra requests.',additional_requests=0,production_mutations=False)
(b/'native-sleeper-replay.json').write_text(json.dumps(report,indent=2)+'\n')
print('Native source26.56 == interpreted26.56 == rendered26.56; one observed completed week, no full-season or games-played inference.')
