from pathlib import Path
import json,hashlib,sys,zipfile
sys.path.insert(0,'/workspace/dtos-publisher-2244')
from tools.release import publish as p
b=Path('/workspace/2244-trade-comparison');plan=json.loads(Path('/workspace/dtos-publisher-2244/.github/release-plans/2244.json').read_text());queue=json.loads((b/'precanonical-download-queue.json').read_text());assert len(queue)==14
checks={'actuals-restoration-original.zip':p.verify_actuals_restoration,'restoration-unused-original.zip':p.verify_restoration_unused,'resident-refresh-original.zip':p.verify_resident_refresh,'trade-resource-original.zip':p.verify_trade_resource,'league-entry-original.zip':p.verify_league_entry,'preflight-original.zip':p.verify_preflight,'current-history-original.zip':p.verify_current_history,'current-production-coverage-original.zip':p.verify_current_production,'market-history-coverage-original.zip':p.verify_market_history,'history-followthrough-original.zip':p.verify_history_followthrough}
rows=[]
for r in queue:
 f=b/'hosted-originals'/r['file'];assert f.stat().st_size==r['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'];p.verify_zip(f)
 if r['file'] in checks:
  result=checks[r['file']](f,plan)
  if isinstance(result,dict) and 'passed' in result:assert result['passed'] is True
 if r['file']=='trade-resource-original.zip':
  assert p.verify_team_need_handoff(f,plan)['passed'];assert p.verify_offer_comparison(f,plan)['passed']
 if r['file']=='history-followthrough-original.zip':assert p.verify_completed_trade_browser(f,plan)['passed']
 if r['file']=='public-welcome-security.zip':assert p.verify_partner_history_links(f,plan)['passed']
 if r['file'].startswith('lifecycle-'):
  with zipfile.ZipFile(f) as z:x=json.loads(z.read('summary.json'))
  assert x['passed'] and x['completed'] and x['exit_code']==0 and x['memory_max']==2147483648
 rows.append(dict(r,original_api_digest_size_and_crc_verified=True,specialized_native_guards_passed=True))
(b/'noncanonical-artifacts-verified.json').write_text(json.dumps(dict(candidate=plan['candidate'],tree=plan['tree'],originals=rows,passed=True,canonical_still_required=True),indent=2)+'\n');print('PASS14original ZIPs and native guards, including hosted actual comparison, lifecycle, recovery and security; canonical remains separate')
