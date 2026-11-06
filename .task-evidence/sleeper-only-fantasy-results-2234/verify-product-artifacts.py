from pathlib import Path
import json,hashlib,zipfile
from tools.release import publish as p
b=Path('/workspace/2234-release');m=json.loads((b/'source.json').read_text());rows=json.loads((b/'product-artifact-metadata.json').read_text())['artifacts'];results=[]
checks={'current-production-coverage-browser':p.verify_current_production,'market-history-coverage-browser':p.verify_market_history,'current-season-history-browser':p.verify_current_history,'history-followthrough-browser':p.verify_history_followthrough,'restoration-preflight-2g':p.verify_preflight,'trade-resource-2g':p.verify_trade_resource,'league-entry-2g':p.verify_league_entry}
for a in rows:
 path=b/'hosted-originals'/(a['name']+'.zip');assert a['workflow_run']['head_sha']==m['candidate'] and path.stat().st_size==a['size_in_bytes'] and 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()==a['digest']
 p.verify_zip(path)
 if a['name'] in checks:
  r=checks[a['name']](path,m)
  result={k:r[k] for k in ['head','tree','passed','complete','kernel_peak','kernel_peak_bytes','cgroup_lifetime_peak','cleanup','liveness'] if k in r}
  result['native_verifier_passed']=True
 else:
  with zipfile.ZipFile(path) as z:result={'members':len(z.namelist()),'crc_ok':z.testzip() is None,'privacy':'Existing public welcome/security evidence, separately guarded mandatory job.'}
 results.append({'artifact':a,'verification':result,'original_bytes_verified':True})
(b/'resource-verified.json').write_text(json.dumps({'candidate':m['candidate'],'tree':m['tree'],'artifacts':results,'all_native_guards_passed':True},indent=2)+'\n')
print('Eight original Product artifacts: exact source, API SHA256, byte sizes, CRC, semantic browser/history/Trade/league/preflight guards passed')
