"""Materialize a source-bound independent acceptance prompt only from actual proof."""
from pathlib import Path
import json
B=Path(__file__).resolve().parent;s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());product=json.loads((B/'product-test-counts.json').read_text());focus=json.loads((B/'focused-ready.json').read_text())
assert all(r['candidate']==s['candidate'] and r['tree']==s['tree'] for r in [local,host,native,focus])
assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and focus['passed']
assert local['tests']==host['tests']==4435 and product['total']==932 and focus['tests']==103
body=f'''# Scout independent acceptance — franchise changes through completed trades

Application candidate: `{s['candidate']}`
Validated source tree: `{s['tree']}`
Baseline: `{s['baseline']}` / v1.22.34 build2249
PR: https://github.com/Richarddavis47/dtos/pull/{s['pr']}
Target: v{s['version']} / build{s['build']}
Release: https://github.com/Richarddavis47/dtos/releases/tag/v{s['version']}

This is source-bound pre-publication evidence. The guarded publisher's later publication/production receipt supplies the actual squash-merge commit. Require that commit's tree to equal the validated tree above; do not assume that candidate and merge SHA are identical. No owner-live acceptance is claimed by this archive.

## What changed

Existing Franchise History now has “How this franchise changed” with a retained source-season selector, observed completed-deal counts, gross player/pick acquisitions and disposals, and net transfers within those observed trades. Expand exact identities, grouped draft year/round and original own/acquired picks, supporting deals and existing pick conversion/subsequent trade links. Existing coverage, event pagination and contextual Back are retained. No new history engine, provider calls, inventory reconstruction, score, strategy inference or preference mutation.

A frozen partial Day Traders replay independently supports two source-season2026 completed deals: one player acquired and three sent; five exact picks acquired and two sent. Observed net is players−2/picks+3, **not current holdings or improvement**. The converted player13346 is later sent but is not counted as a separate trade acquisition at draft conversion. Arkham's selected sparse sample remains unknown. These are retained replay examples, not fresh/exhaustive production coverage. Granite-shaped1QB/K/DEF and Superflex contexts are disposable lifecycle controls, not new live Granite results.

## Verify evidence first

- Match source IDs to source.json and the exact patch. Reconcile original local{local['tests']} and hosted{host['tests']} executions, all ten gates in each, all13 required hosted jobs and Product{product['total']}. Check starts/stops, errors/failures/skips, actual process exit and cleanup, manifests and original API artifact digests. Local manifest has{local['local_manifest_entries']} entries; hosted has{host['entries']}.
- Focused103 exact-source methods and16 new movement methods must be independently visible in original logs/events. Browser receipts cover320×432,375×667,390×844,1280×900, keyboard/touch emulation, period selection, pagination and conversion/return. Physical iPhone/Safari is untested.
- Read PRIOR_ATTEMPTS.md. The dirty-source86-method development run is not final proof. The first publisher141-method run had3 subtest errors in an isolated collector fixture; its original failed console remains separate. The exact unformatted failed publisher working tree was not sealed and is unavailable. Later corrections never bypass real release guards. Old immutable evidence is unchanged.
- The first full-local f40 source failed one500ms FOIS responsiveness assertion at542.77ms; its remainder was deliberately interrupted and three gates did not execute. A1211-method diagnostic measured940075 unreachable objects after the replay and its first worker (origins not attributed), but did not reproduce the original stall. Final source isolates fixture GC before its unchanged workload/timer, with GC enabled,500ms limit and actual two-record completion assertions. The f40 hosted canonical was cancelled by the new head at3828starts/3827stops, not passed. A first103-method supplemental focused run exposed a missing __main__ guard in the external harness; its original1failure/5errors are separate from the corrected spawn-safe runner. Read all source-bound originals, not just final pass counts.
- Full original consoles and native archives are retained. Readable60KB UTF8-boundary parts preserve CR/LF; concatenate in lexical order and verify whole/part SHA256. Tool-decoded GitHub job logs are labelled decoded transport, not raw HTTP-wire bytes.

## Resource and fixture-review limits

Read FOIS_FIXTURE_REVIEW.md and its AST receipt. No representative workload was moved outside its original measured interval; collection occurs before construction. The940075-object count followed the replay and its first worker, with origins unattributed. It does not establish the original542.77ms failure's cause. Both final full runs reached the actual2GiB kernel cap with zeroOOM/oomkill events; do not describe them as comfortably belowcapacity. The local original observer hit its10000sample bound and stopped1261.77seconds before completion. Kernel enforcement/final cumulative counters and cleanup cover the cgroup lifetime; finite sampled/native controls do not prove continuous profiling or long-term leak freedom. Original interrupted external collectors were resumed without restarting the actual local run. Auxiliary GitHub PR merge checkouts have the exact candidate tree; see checkout identity receipts.

## Bounded live acceptance

1. Verify immutable v{s['version']} release, exact tag/merge tree, deployed build{s['build']} and readiness. Use existing authorized owner access. Keep inspection credentials inside Render. Do not retry the unchanged external401 method or request tokens in chat.
2. Use a normal prepared, authorized league context. If cold or capacity is uncertain, use the existing Render-local running-process preflight and respect normal admission. Stop on deferral. Do not force sync, backfill history, clear caches, rebuild FOIS, restart, run Trade discovery or alter saved data.
3. Open existing Franchise History for a supported franchise. Choose a retained source season. Compare completed trade count with supporting source events, not just visible pagination. Verify gross players/picks, exact year/round/original franchise and “own” origin. Do not hard-code the replay's numbers as live expectations.
4. If an asset was acquired and later sent, confirm both events remain visible and net is only the observed trade sample. Confirm a converted pick is not another trade acquisition. Waivers/drafts/drops remain distinct and prevent interpreting trade movement as total roster progress. No unsupported beginning/end inventories or current-price/hindsight judgments.
5. Expand a supporting completed deal; follow an exact pick's existing conversion/subsequent movement where source supports it; return through the original trade and contextual Back. Preserve source-season filter, events page and reload context. Existing Trade drafts, comparisons and preferences must remain untouched.
6. Inspect partial, genuinely missing and complete-empty scopes. Missing coverage must remain unknown; zero empty-period activity requires complete compatible coverage and franchise continuity. Supported values in incomplete consideration remain lower bounds; affected nets are withheld. Pending/rejected/cancelled/failed transactions, duplicates and waivers cannot inflate completed trade counts. Unknown completion times remain qualified.
7. Check another authorized league and a manager-change example when prepared evidence permits. Do not backdate current manager identity, ownership or scoring. Confirm account/league isolation and that source-linked franchise activity stays descriptive. FOIS grades remain RETAINED / NOT REVALIDATED.
8. At narrow phone widths verify readable first-level summary,44px controls, focus, touch, no horizontal overflow and accessible details. Mark physical Safari separately. Opening/filtering/expanding must not start providers, heavy analysis or an automatic search.

Report PASS/PARTIAL/HELD per evidence family. Separate source inspection, retained replay, disposable fixtures, public deployment metadata and authenticated live observations. Missing owner access or source coverage is a limitation, not proof of a failed Trade engine or reliable Granite recovery. Finite cleanup controls do not prove long-term leak freedom.
'''
(B/'SCOUT_HANDOFF.md').write_text(body)
print('Created source-bound Scout prompt from verified mandatory results; publication receipt remains separate.')
