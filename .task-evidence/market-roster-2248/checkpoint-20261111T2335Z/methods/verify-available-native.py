"""Verify completed-job originals only; canonical and full acceptance still pending."""
from pathlib import Path
import importlib.util,json,sys,zipfile
from common import BASE,digest,load_source,write_json
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('publisher_native','/workspace/dtos-publisher-2248/tools/release/publish.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
source=load_source();plan=dict(source,capital_tests=14,canonical_tests=4396,python_version='3.14.3')
checks={
'actuals-restoration-original.zip':guard.verify_actuals_restoration,'restoration-unused-original.zip':guard.verify_restoration_unused,
'resident-refresh-original.zip':guard.verify_resident_refresh,'trade-resource-original.zip':guard.verify_trade_resource,
'league-entry-original.zip':guard.verify_league_entry,'preflight-original.zip':guard.verify_preflight,
'current-history-original.zip':guard.verify_current_history,'current-production-coverage-original.zip':guard.verify_current_production,
'market-history-coverage-original.zip':guard.verify_market_history,'history-followthrough-original.zip':guard.verify_history_followthrough}
rows=[]
for item in json.loads((BASE/'artifact-partial-queue.json').read_text()):
 path=BASE/'hosted-originals'/item['file'];assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256'];guard.verify_zip(path)
 if item['file'] in checks:checks[item['file']](path,plan)
 if item['file']=='trade-resource-original.zip':
  for fn in [guard.verify_team_need_handoff,guard.verify_offer_comparison,guard.verify_recommended_protections,guard.verify_activation_deferral,guard.verify_front_office_workflow,guard.verify_draft_capital]:fn(path,plan)
 if item['file']=='public-welcome-security.zip':guard.verify_partner_history_links(path,plan)
 if item['file']=='history-followthrough-original.zip':guard.verify_completed_trade_browser(path,plan)
 if item['file'].startswith('lifecycle-'):
  with zipfile.ZipFile(path) as z:r=json.loads(z.read('summary.json'))
  assert r['passed'] and r['completed'] and r['exit_code']==0 and r['memory_max']==2147483648
 rows.append(dict(item,native_guards_passed=True))
write_json(BASE/'available-native-verified.json',dict(source=source,completed_archives=rows,passed=True,scope='Fourteen completed-job originals; does not replace pending complete local/hosted canonical acceptance.'))
print('All14available originals passed exact-byte and existing/new native guards; canonical pending.')
