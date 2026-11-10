"""Verify every required original byte stream with existing native guards."""
from pathlib import Path
import json
import sys
import zipfile

base = Path('/workspace/2244-trade-comparison')
sys.path.insert(0, '/workspace/dtos-publisher-2244')
from tools.release import publish as guard

plan = json.loads(Path('/workspace/dtos-publisher-2244/.github/release-plans/2244.json').read_text())
queue = json.loads((base / 'artifact-download-queue.json').read_text())
assert len(queue) == 15
checks = {'actuals-restoration-original.zip': guard.verify_actuals_restoration,
          'restoration-unused-original.zip': guard.verify_restoration_unused,
          'resident-refresh-original.zip': guard.verify_resident_refresh,
          'trade-resource-original.zip': guard.verify_trade_resource,
          'league-entry-original.zip': guard.verify_league_entry,
          'preflight-original.zip': guard.verify_preflight,
          'current-history-original.zip': guard.verify_current_history,
          'current-production-coverage-original.zip': guard.verify_current_production,
          'market-history-coverage-original.zip': guard.verify_market_history,
          'history-followthrough-original.zip': guard.verify_history_followthrough}
rows = []
for row in queue:
    path = base / 'hosted-originals' / row['file']
    assert path.stat().st_size == row['bytes'] and guard.digest(path) == row['sha256']
    guard.verify_zip(path)
    if row['file'] in checks:
        checks[row['file']](path, plan)
    if row['file'] == 'canonical-original.zip':
        proof = json.loads((base / 'host-canonical-verified.json').read_text())
        guard.verify_canonical(path, dict(plan, canonical_entries=proof['entries']))
    if row['file'] == 'trade-resource-original.zip':
        guard.verify_team_need_handoff(path, plan)
        guard.verify_offer_comparison(path, plan)
    if row['file'] == 'history-followthrough-original.zip':
        guard.verify_completed_trade_browser(path, plan)
    if row['file'] == 'public-welcome-security.zip':
        guard.verify_partner_history_links(path, plan)
    if row['file'].startswith('lifecycle-'):
        with zipfile.ZipFile(path) as archive:
            result = json.loads(archive.read('summary.json'))
        assert result['passed'] and result['completed'] and result['exit_code'] == 0 and result['memory_max'] == 2147483648
    rows.append(dict(row, original_bytes_verified=True, specialized_guards_verified=True))
(base / 'hosted-artifacts-verified.json').write_text(json.dumps(dict(candidate=plan['candidate'], tree=plan['tree'], passed=True, originals=rows), indent=2) + '\n')
print('PASS15original ZIPs: source, API digest/size, CRC, complete canonical manifest and specialized existing/new guards')
