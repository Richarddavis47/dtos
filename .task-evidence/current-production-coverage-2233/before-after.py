"""One frozen public-stat fixture, original versus corrected canonical boundaries."""
from pathlib import Path
import json,subprocess,sys,types
sys.path.insert(0,"/app")
from tests.test_current_production_coverage import raw
from src.core.data_platform.global_production import GlobalProduction
from src.core.historical_memory.providers import normalize_nflverse_row
b=Path('/evidence');m=json.loads((b/'source.json').read_text())
def previous(path,name):
 module=types.ModuleType(name);module.__package__="src.core.data_platform" if "/data_platform/" in path else "src.core.historical_memory";sys.modules[name]=module
 code=subprocess.check_output(['git','show',m['baseline']+':'+path],text=True)
 exec(compile(code,m['baseline']+':'+path,'exec'),module.__dict__)
 return module
provider=previous('src/core/historical_memory/providers.py','prior_production_provider')
production=previous('src/core/data_platform/global_production.py','prior_canonical_production')
record=raw();old_row=provider.normalize_nflverse_row(record);new_row=normalize_nflverse_row(record);old=old_row['raw_stats']|{'position':old_row['position']};new=new_row['raw_stats']|{'position':new_row['position']}
configs=json.loads(Path('tests/fixtures/current_production_leagues.json').read_text())['leagues']
controls=configs+[dict(name='Disposable standard offensive scoring plus required team defense',league_id='fixture-control',scoring_settings={'pass_yd':.04,'pass_td':4,'pass_int':-2,'rush_yd':.1,'sack':1,'pts_allow_0':10,'unused':0})]
rows=[]
for league in controls:
 before=production.GlobalProduction.score_game(old,league['scoring_settings']);after=GlobalProduction.score_game(new,league['scoring_settings'])
 rows.append(dict(name=league['name'],league_id=league['league_id'],before=before,after=after,scope='Identical disposable QB stat record under frozen public league coefficients, not live player or team results.'))
assert rows[-1]['before']['fantasy_points'] is None and rows[-1]['after']['fantasy_points']==18
assert rows[0]['after']['fantasy_points'] is None and set(rows[0]['after']['missing_components'])=={'st_ff','st_fum_rec'}
result=dict(candidate=m['candidate'],tree=m['tree'],baseline=m['baseline'],normalized_fields_added=sorted(set(new)-set(old)),cases=rows,scope='Source inspection and deterministic numerical fixture only; no private roster observation substitution or new acquisition.')
(b/'before-after.json').write_text(json.dumps(result,indent=2)+'\n')
for r in rows:print(r['name'],dict(before_missing=r['before'].get('missing_components'),after_missing=r['after'].get('missing_components'),before_points=r['before'].get('fantasy_points'),after_points=r['after'].get('fantasy_points')))
