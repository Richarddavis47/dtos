"""Wait for the current real container, then complete only required sequential scopes."""
from pathlib import Path
import subprocess,json,os,hashlib,sys
b=Path('/workspace/2234-release');m=json.loads((b/'source.json').read_text())
with (b/'local-container-exit.log').open('w') as f:subprocess.run(['docker','wait','dtos-sleeper-results-clean'],stdout=f,stderr=subprocess.STDOUT,check=True)
r=json.loads((b/'canonical/result.json').read_text());assert r['passed'] and r['head']==m['candidate'] and r['tree']==m['tree'],'Canonical not passing: no follow-on scopes started'
commands=[]
def run(name,args,env=None):
 with (b/name).open('w') as f:result=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env)
 commands.append({'log':name,'command':args,'exit_code':result.returncode})
 (b/'sequential-final-scopes.json').write_text(json.dumps(commands,indent=2)+'\n')
 assert result.returncode==0,name
 print(name,'passed',flush=True)
run('local-canonical-integrity.log',['python',str(b/'verify-local-canonical.py')])
(b/'browser-final').mkdir(exist_ok=True);(b/'browser-final').chmod(0o777)
env=dict(os.environ,DTOS_EXPECTED_HEAD=m['candidate'],DTOS_PRODUCTION_COVERAGE_EVIDENCE='/evidence/browser-final')
modules=['test_sleeper_actual_results','test_current_production_coverage','test_current_production_browser','test_historical_retained_admission','test_historical_retained_admission_browser','test_historical_snapshot_integrity','test_trade_decision_experience','test_sleeper_projection_transport','test_prepared_player_evidence','test_reference_production_methodology','test_historical_player_evidence','test_batch6_asset_explanations','test_batch6_asset_explanation_browser','test_data_completeness','test_lineup_review','test_trade_lineup_provenance_browser']
run('focused-exact.log',['python',str(b/'run-constrained.py'),'-m','unittest','-v',*['tests.'+n for n in modules]],env)
(b/'local-preflight').mkdir(exist_ok=True);(b/'local-preflight').chmod(0o777)
run('local-preflight-console.log',['python',str(b/'run-constrained.py'),'-m','tools.validation.restoration_preflight_gate','--output','/evidence/local-preflight'],env)
raw=(b/'local-preflight-console.log').read_bytes();(b/'local-preflight/raw.log').write_bytes(raw)
pre=json.loads((b/'local-preflight/result.json').read_text());assert pre['passed'] and pre['complete'] and pre['head']==m['candidate'] and pre['tree']==m['tree']
(b/'local-preflight/SHA256SUMS').write_text(''.join(hashlib.sha256((b/'local-preflight'/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ['result.json','raw.log']))
run('before-after.log',['python',str(b/'run-constrained.py'),'/evidence/before-after.py'],env)
run('native-sleeper-replay.log',['python',str(b/'run-constrained.py'),'/evidence/native-sleeper-replay.py'],env)
run('ruff-final.log',['python',str(b/'run-constrained.py'),'-m','ruff','check','--no-cache','.'],env)
print('All final local scopes passed; no production work performed.',flush=True)
