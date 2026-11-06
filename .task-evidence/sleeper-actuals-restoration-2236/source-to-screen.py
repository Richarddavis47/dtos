"""Matched source-to-render evidence; no live source or owner account is used."""
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/app')
b=Path('/evidence');spec=importlib.util.spec_from_file_location('restoration_fixture',b/'restoration_fixture.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip();assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
records=[]
for default in (True,False):
 case=module.ActualRestorationTests('test_matched_default_and_connected_restoration_reach_rendered_consumers')
 try:
  f,data=case.fixture();native=data['season_matchups']['weeks']['1']['rows'][0]['players_points']['1'];restored=case.restore(data,default=default);dossier,market,api=case.render(f,restored);actual=api.json()['valuation']['canonical_production'];profile=case.profile(restored)
  records.append(dict(path='default' if default else 'connected',league=data['league']['league_id'],season=data['league']['season'],week=1,native_score=native,source_generation=data['season_matchups']['semantic_generation'],admitted_generation=actual.get('source_generation'),admitted_score=(actual.get('observations') or [{}])[0].get('points'),season_average=next((w['fantasy_points'] for w in actual['windows'] if w['label']=='Season Average'),None),statuses=[r.status_code for r in [dossier,market,api]],dossier_supported='18.00 fantasy points per score observation' in dossier.text,market_supported='18.00 fantasy points per score observation' in market.text,unprepared_message='Compatible Sleeper actual results are not prepared' in dossier.text,observed_at=profile.updated_at))
 finally:case.doCleanups()
expected=[18,None] if os.environ['DTOS_EXPECTED_HEAD']=='4e63bfbf605c7a1cdd5ce1dc039424e862ab7efd' else [18,18]
assert [r['admitted_score'] for r in records]==expected
assert all(r['statuses']==[200]*3 for r in records)
out=dict(head=head,tree=tree,scope=__doc__,fixture_sha256=hashlib.sha256((b/'restoration_fixture.py').read_bytes()).hexdigest(),records=records,source_requests=0,expected_behavior_verified=True)
(b/('before-rendered.json' if expected[1] is None else 'after-rendered.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
