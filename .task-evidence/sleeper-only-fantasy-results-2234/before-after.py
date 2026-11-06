"""Pinned baseline adapter + native fixture parity; not live owner evidence."""
import sys
sys.path.insert(0,"/app")
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import types

from services.player_evidence import prepare_player_production
from services.matchup_season import source_player_actual
from src.core.player_value_projection.canonical_production import prepared_production_context
from src.platform.lifecycle import memory_snapshot
from tests.test_current_production_coverage import prepared
from tests.test_sleeper_actual_results import actual_data

b=Path('/evidence');identity=json.loads((b/'source.json').read_text());baseline=identity['baseline']
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head==identity['candidate']
assert memory_snapshot()['cgroup_limit_bytes']==2147483648
old_bytes=subprocess.check_output(['git','show',baseline+':services/player_evidence.py'])
old=types.ModuleType('baseline_player_evidence');exec(compile(old_bytes,'baseline/services/player_evidence.py','exec'),old.__dict__)
# This is the exact baseline adapter with unchanged scoring dependencies. It is
# not a second deployed process or a reconstruction of a historical live result.
before=memory_snapshot();started=time.perf_counter()
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'facts.sqlite3';prepared(path)
 data=actual_data(scores=(23.4738,0,-2.125))
 prior=old.prepare_player_production(data,expected_league_id='A',as_of='2026-11-01T00:00:00Z',path=path)
 current=prepare_player_production(data,expected_league_id='A',as_of='2026-11-01T00:00:00Z',path=path)
 data['canonical_player_production']=current
 context=prepared_production_context(current,league_id='A',player_id='4984',data=data)
 source=[dict(week=int(w),points=row['players_points']['4984']) for w,week in data['season_matchups']['weeks'].items() for row in week['rows']]
 assert [r['points'] for r in context.observations]==[r['points'] for r in source]
 assert context.windows[3].observed_total==float(sum((Decimal(str(r['points'])) for r in source),Decimal(0)))
 prior_window=prior['players']['4984']['production']['windows'][3]
 assert prior_window['fantasy_points'] is None and 'st_ff' in prior_window['missing_components']
 assert context.windows[3].fantasy_points is not None
 assert prior['reference_generation']==current['reference_generation']
 assert prior['players']['4984']['reference_seasons']==current['players']['4984']['reference_seasons']
 assert prior['provider_calls']==current['provider_calls']==0

guards=['src/platform/lifecycle.py','src/platform/cache_budget.py','src/core/trade_intelligence/bilateral.py',
        'src/core/trade_intelligence/lineup.py','src/core/projection_intelligence/scoring.py',
        'src/core/projection_intelligence/sleeper_provider.py','src/core/projection_intelligence/service.py',
        'src/core/valuation/player_methodology.py','src/core/data_platform/global_production.py']
unchanged=[]
for name in guards:
 original=subprocess.check_output(['git','show',baseline+':'+name]);candidate=Path(name).read_bytes()
 assert candidate==original,name
 unchanged.append(dict(path=name,sha256=hashlib.sha256(candidate).hexdigest(),byte_identical=True))
row=dict(starters=['p'],starters_points=[0],players_points={'p':9})
assert source_player_actual(row,'p',0) is None
out=dict(candidate=head,tree=identity['tree'],baseline=baseline,scope='Disposable source-shaped fixture, exact baseline adapter and unchanged scoring dependencies; not authenticated live parity.',
         baseline_adapter_sha256=hashlib.sha256(old_bytes).hexdigest(),source_scores=source,
         old_window=prior_window,new_production=asdict(context),reference_generation_unchanged=True,
         additional_provider_calls=0,unchanged_guards=unchanged,before_memory=before,after_memory=memory_snapshot(),elapsed_seconds=time.perf_counter()-started,
         cleanup='Temporary source store removed; no production data or worker started.')
(b/'before-after.json').write_text(json.dumps(out,indent=2)+'\n')
print('Native Sleeper source parity:',source)
print('Old NFLverse fantasy average withheld; new source-backed average',context.windows[3].fantasy_points,'observed total',context.windows[3].observed_total)
print('Unchanged critical files:',len(unchanged),'reference generation preserved; additional provider calls0.')
