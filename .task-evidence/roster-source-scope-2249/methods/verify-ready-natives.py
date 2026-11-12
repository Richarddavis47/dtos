from pathlib import Path
import json,importlib.util,zipfile
B=Path('/workspace/2249-sleeper-relevance');s=json.loads((B/'source.json').read_text());spec=importlib.util.spec_from_file_location('ready_native_guards','/workspace/dtos-publisher-2249/tools/release/publish.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);plan=dict(s,canonical_tests=4419,market_roster_tests=21,capital_tests=14,roster_source_scope_tests=20)
checks={'actuals-restoration-original.zip':g.verify_actuals_restoration,'restoration-unused-original.zip':g.verify_restoration_unused,'resident-refresh-original.zip':g.verify_resident_refresh,'trade-resource-original.zip':g.verify_trade_resource,'league-entry-original.zip':g.verify_league_entry,'preflight-original.zip':g.verify_preflight,'current-history-original.zip':g.verify_current_history,'current-production-coverage-original.zip':g.verify_current_production,'market-history-coverage-original.zip':g.verify_market_history,'history-followthrough-original.zip':g.verify_history_followthrough}
rows=[]
queue={row["file"]:row for row in json.loads((B/"available-complete-noncanonical-artifacts.json").read_text())}
for path in sorted((B/'hosted-originals').glob('*.zip')):
 receipt=queue[path.name];assert path.stat().st_size==receipt["bytes"] and g.digest(path)==receipt["sha256"];g.verify_zip(path)
 if path.name in checks:checks[path.name](path,plan)
 if path.name=='trade-resource-original.zip':
  for f in [g.verify_team_need_handoff,g.verify_offer_comparison,g.verify_recommended_protections,g.verify_activation_deferral,g.verify_front_office_workflow,g.verify_draft_capital,g.verify_market_roster,g.verify_roster_source_scope]:f(path,plan)
 if path.name=='history-followthrough-original.zip':g.verify_completed_trade_browser(path,plan)
 if path.name=='public-welcome-security.zip':g.verify_partner_history_links(path,plan)
 if path.name.startswith('lifecycle-'):
  with zipfile.ZipFile(path) as z:r=json.loads(z.read('summary.json'))
  assert r['passed'] and r['completed'] and r['exit_code']==0 and r['memory_max']==2147483648
 rows.append(dict(file=path.name,verified=True))
assert len(rows)==14
(B/'ready-native-integrity.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],verified=rows,scope='Fourteen of fifteen native archives verified; canonical and complete local gates still required'),indent=2)+'\n');print(dict(verified=14,required=15,new_market_roundtrip_verified=True,all_mandatory_checks_complete=False))
