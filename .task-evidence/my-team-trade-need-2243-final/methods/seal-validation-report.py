"""Seal only independently checked, complete exact-source validation facts."""
from pathlib import Path
from datetime import datetime, timezone
import json

b = Path('/workspace/2243-my-team-trade-need')
s = json.loads((b / 'source.json').read_text())
local = json.loads((b / 'local-verified.json').read_text())
host = json.loads((b / 'host-canonical-verified.json').read_text())
art = json.loads((b / 'hosted-artifacts-verified.json').read_text())
product = json.loads((b / 'product-test-counts.json').read_text())
welcome = json.loads((b / 'public-welcome-test-counts.json').read_text())
assert local['all_local_gates_passed'] and host['all_gates_passed'] and art['passed']
assert local['tests'] == host['tests'] == 4330 and product['total'] == 831 and welcome['total'] == 412
for r in (local, host, art, product, welcome):
    assert r['candidate'] == s['candidate'] and r['tree'] == s['tree']
assert len(art['originals']) == 15
records = json.loads((b / 'hosted-final-records.json').read_text())
plan = json.loads(Path('/workspace/dtos-publisher-2243/.github/release-plans/2243.json').read_text())
for expected in plan['runs']:
    row = next(x for x in records if x['run']['id'] == expected['id'])
    assert row['run']['head_sha'] == s['candidate'] and row['run']['conclusion'] == 'success'
    for name in expected['jobs']:
        job = next(x for x in row['jobs'] if x['name'] == name)
        assert job['status'] == 'completed' and job['conclusion'] == 'success'
report = (b / 'REPORT_DRAFT.md').read_text()
report += '\n## Sealed exact-source final validation\n\n'
report += 'Observed ' + datetime.now(timezone.utc).isoformat() + '. This section records completed validation before guarded publication. The separate final deployment receipt is authoritative for release status.\n\n'
report += '| Scope | Result |\n| --- | --- |\n'
report += f"| Clean writable local Python 3.14.3, enforced 2 GiB / two CPU / network none / UID 1000 | 4,330 completed tests, 10/10 gates; {local['local_manifest_entries']} SHA-verified original manifest entries; {local['elapsed_seconds']:.3f}s |\n"
report += f"| Hosted exact-source canonical | 4,330 completed tests, 10/10 gates; {host['entries']} SHA-verified original manifest entries; {host['elapsed_seconds']:.3f}s |\n"
report += '| Hosted required jobs | 13/13 passed: canonical, Product, My Team, beginner navigation, Welcome/security, historical timeline, projection cross-version, resident refresh, Ubuntu/Windows tooling and all three Linux lifecycle modes |\n'
report += '| Product / separate Welcome-security executions | 831 (657 + 35 + 139) / 412 passed, original complete consoles retained |\n'
report += '| Focused / publisher | 24 final-source focused tests / 68 scoped publisher controls, lint, compile and permission/source review passed |\n'
report += '| Phone / touch | Four sizes and three CDP touch sizes passed; physical iPhone/Safari not tested |\n'
report += '| Artifact integrity | 15 original GitHub ZIPs match API size/digest, ZIP CRC and all specialized source-bound guards |\n\n'
report += f"Local kernel lifetime peak: {local['kernel_peak']} bytes; hosted: {host['kernel_peak']} bytes. OOM and OOM-kill counters were zero. These include disposable validation workloads/pressure; they are not proof of spare production capacity. Original per-stage samples, process records, cleanup and qualifications remain in the archive. Test repetitions are execution counts, not a claim of that many unique cases.\n\n"
report += 'Local and hosted artifact populations differ by output capture: local has 18 additional partner-history reports/screenshots enabled by its documented capture variable; hosted has four environment/build/bytecode files absent locally. Both original manifests are independently verified. The hosted Welcome artifact separately contains the source-bound partner-history captures. See local-hosted-manifest-reconciliation.json; neither inventory count substitutes for completed tests.\n\n'
report += 'Original workflow results:\n\n' + ''.join(f"- [{x['name']}](https://github.com/Richarddavis47/dtos/actions/runs/{x['id']})\n" for x in plan['runs'])
report += '\nEarlier original failures, cancellations and incomplete attempts remain separately qualified in PRIOR_ATTEMPTS.md, Prior-attempts.zip and the byte-verified [prior-originals snapshot](https://github.com/Richarddavis47/dtos/tree/480da5e97a793d167c2ca68be3a01b9796f6b7f2/.task-evidence/my-team-trade-need-2243-prior-originals). No original failed inner manifest was rewritten.\n'
(b / 'REPORT.md').write_text(report)
scout = (b / 'SCOUT_HANDOFF_DRAFT.md').read_text()
scout += '\nFinal exact-source validation is complete: 4,330 local and hosted executions, all ten gates in each, all 13 required hosted jobs, 831 Product and 412 separate Welcome/security executions. Read the separate final publication/production receipts before asserting deployment. No heavy production search or live owner feature acceptance is part of this validation.\n'
(b / 'SCOUT_HANDOFF.md').write_text(scout)
print('Sealed complete exact-source validation report and independent acceptance handoff; publication is separately guarded.')
