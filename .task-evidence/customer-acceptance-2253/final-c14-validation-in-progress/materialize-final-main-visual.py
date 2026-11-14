"""Copy byte-verified current canonical captures; no new test or visual-pass claim."""
from common import *
import shutil,datetime
S=load_source();p=BASE/'local-canonical';v=json.loads((BASE/'local-verified.json').read_text());assert v['candidate']==S['candidate'] and v['tree']==S['tree'] and v['all_local_gates_passed'];name='test_customer_experience_journeys.CustomerExperienceJourneyTests.test_authenticated_product_navigation_and_league_switching';events=[json.loads(l) for l in (p/'tests.jsonl').read_text().splitlines()];assert [e['event'] for e in events if e.get('test')==name]==['start','stop'];out=BASE/'visual-final';assert not out.exists();out.mkdir();dst=out/'customer-journeys';dst.mkdir();rows=[]
for stem in ['home','teams-1','market','players-1-QB-0','league','transactions','picks','matchups','front-offices','fois','settings','commissioner']:
 for w in [320,375,390,1280]:
  for ext in ['.png','.json']:
   q=p/'customer-experience'/f'{stem}-{w}{ext}';assert q.is_file();z=dst/q.name;shutil.copy2(q,z);assert digest(q)==digest(z);rows.append(dict(source=str(q.relative_to(BASE)),target=str(z.relative_to(BASE)),sha256=digest(z)))
shutil.copy2(p/'result.json',out/'result.json');write_json(out/'provenance.json',dict(source=S,method=name,scope='Exact verified full canonical result and original source-bound method captures, not a separately executed one-test job or automatic visual PASS.',original_manifest_sha256=digest(p/'manifest.json'),copied_originals=rows));print('48 actual current four-width main-family captures materialized; manual review remains required.')
