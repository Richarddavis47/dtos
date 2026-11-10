# Recorded Trade offer comparison — validation/release review

## Customer outcome and reproduced gap

The production baseline was observed through public readiness as v1.22.28/build2243, commit 6ed905ce18832be10f04e47cac8a703af4895719, tree 9a6fb02bd00b789f6566cfb59f70868972b3ed2d. Source inspection and an actual disposable baseline replay confirmed that the legacy comparison API reevaluated two proposals and the Trade workspace had no select-two completed-assessments journey. That API and its policy remain unchanged.

The correction adds a bounded comparison inside the existing Trade workspace. Add up to two completed Evaluate/recommendation offers, explicitly replace or remove them, inspect the changes from keeping the roster, and return to the unchanged source draft or recommendation. Opening, expanding and closing this review makes no HTTP request, invokes no evaluation/search/optimizer and changes no preference.

## Evidence and numerical boundaries

Shared lineup figures require the same authorized account/session, league/franchise, roster ownership, prepared canonical roster generation, season/week, scoring, Sleeper projection source and generation. Original Neutral Market and personal Custom values remain separate; saved personal revision/method/publication changes withhold shared comparison. Known source changes, aged publication qualification, missing identity and unsupported/provisional full lineups are explicit. A supported individual effect can remain visible when the second lineup is incomplete under the same admitted identity. Missing evidence is not zero. Retained results say NOT REVALIDATED and remain assessment-time facts, not a fresh recommendation.

Selection snapshots the completed context independently. Subsequent draft mode edits cannot mutate selected Custom evidence. Real canonical-source invalidation still marks the selected copies stale. Exact original asset order is retained separately from the evaluator's existing order-insensitive identity. Future picks keep their verified year, round and original franchise. Original verdicts, counterparty conditions, reserve limits and configured roster-space consequences stay attached to their own offer; this view does not pick a winner or invent an acceptance probability.

## Source-compatible controls

- One-QB/FLEX/K/DEF fixture: two independent actual canonical assessments have +4 and +8 supported lineup deltas, with 250 and 500 Neutral Market sent respectively. The higher-cost offer preserves the original ordered 2028 first (original franchise 3, currently owned by the sending franchise) plus player package. These are intentionally disposable prices and native Sleeper fixture projections, not claims about current production player values.
- Superflex plus a genuinely uncovered reserve: original unknown depth stays qualified. Three actual evaluations exercise explicit replacement and removal without another comparison request.
- A complete retained pair remains inspectable after reload; an incomplete native Custom pair stays incomplete. Mode changes leave selected original contexts unchanged. Actual changed projection generations and eight-hour source aging withhold the shared comparison.
- A native missing post-trade starting lineup preserves the supported effect from the other offer without fabricating a second total. Neutral and Custom values remain the exact separately returned evidence.
- The retained source-compatible Rebuild fixture executed one explicit search with four eligible source offers. Selection compared existing results without adopting them. Switching leagues discarded the comparison scope. This is not a live qualified owner offer or Granite acceptance.
- Four widths 320×432, 375×667, 390×844 and 1280×900 cover keyboard, Chromium touch, overflow, target size and exact draft/strategy/mode return. Physical iPhone/Safari was not tested.

## Preservation and resources

Protected evaluator, optimizer, fantasy source/scoring, valuation, FOIS and admission source objects match the production baseline byte-for-byte; see preservation-review.json. The existing workspace already reads the compatible prepared lineup profile; its canonical semantic generation is now exposed alongside the same metadata, without new calculation. No provider call, source storage, preference schema, submitted lineup, qualification threshold, roster rule or memory reserve changed. The actual cap is 2 GiB, Trade 256+128 MiB and FOIS 768 MiB.

Focused source-pinned acceptance passed 31 tests; eight additional source-pinned existing feature browser controls and all three native enforced 2 GiB resource/recovery controls passed. The separate publisher has 76 focused fail-closed integrity/authorization tests. Complete local/hosted gates are not inferred from these counts; the sealed final section below must record their actual outcomes.

## Live scope and original attempts

The existing browser connector returned Browser not connected. No owner tabs, private league payload, authenticated feature acceptance, Trade search, sync, FOIS rebuild or user-setting mutation was performed. Public deployed readiness/static/authentication smoke observations are separate from all disposable fixture and retained replay results.

All original development failures and incomplete invocation attempts remain separately indexed in PRIOR_ATTEMPTS.md and the original logs. The first hosted Product and resident-refresh jobs failed during unchanged Ubuntu package-mirror acquisition before application tests. Their original logs and later attempt identities remain separate. A standard failed-jobs-only GitHub retry was requested once after the workflow completed; GitHub emitted fresh attempt 2 job records for all seven Product-workflow jobs, so final verification must use those actual records rather than claiming the earlier sibling executions are final-attempt proof. No threshold or assertion was relaxed.

All original local/hosted consoles are supplied intact and as byte-reassembling UTF8-safe readable parts. Immutable release ZIPs retain their own API digests, CRC and manifests. Final publication and deployment identity are recorded separately from validation, only after guarded Actions preparation, exact expected-head squash tree verification and immutable publication.

## Execution transport qualification

The environment reconnected while the original enforced validation container continued. Its complete original in-container regression console, all ten gate logs, event ledger, final result and 654-entry manifest survive and verify. The outer CLI stdout contains only its original startup header and the outer wrapper after-check receipt was absent; the exact transport cause is unproven. Neither was reconstructed. Fresh read-only checks separately confirm both source checkouts and all shared immutable bytes unchanged, and the original container absent after completion. See canonical-outer-transport-limitation.json. No successful regression was repeated solely for the reconnection.

## Sealed exact-source validation

Observed 2026-11-10T06:42:04.347119+00:00. These are completed validation results before publication. Deployment is established only by the separate exact production/release receipts.

| Scope | Verified outcome |
| --- | --- |
| Clean writable local Python 3.14.3, UID 1000, enforced 2 GiB, two CPUs, no network | 4,342 completed tests; all 10 gates; 654 SHA-verified manifest entries; 2953.139s |
| Hosted exact-source canonical | 4,342 completed tests; all 10 gates; 658 SHA-verified manifest entries; 4049.150s |
| Required hosted jobs | 13/13 pass: canonical, Product, My Team, beginner navigation, Welcome/security, historical timeline, projection cross-version, resident refresh, Ubuntu/Windows tooling, three Linux lifecycle modes |
| Product and separate Welcome/security | 843 executions (669+35+139) / 412 executions, complete original consoles retained |
| Focused feature and preservation | 31 exact-source controls +8 existing feature browser controls; three native resource controls; 76 separate publisher integrity controls, lint/compile and workflow permission/source review |
| Phone | 320×432,375×667,390×844,1280×900; keyboard, Chromium touch, exact asset order and unchanged draft. Physical Safari and authenticated owner acceptance unverified |
| Artifact integrity | All15original ZIPs match API size/digest, ZIP CRC, canonical manifest and existing/new specialized guards |

Local full-suite lifetime cgroup peak was 2132180992 bytes; hosted was 2100588544 bytes. Both OOM/OOM-kill counters were zero. Peaks include intentional resource-pressure controls and the complete validation workload, not the incremental cost of opening comparison or evidence of production spare capacity. Native worker cleanup/recovery and liveness qualifications remain in the original resource records.

Original canonical full console: canonical/unittest-console.log locally and the same named file in canonical-original.zip for hosted evidence. Complete readable <=60k-byte parts and checksum indexes are supplied separately. The outer transport limitation is disclosed above; no missing outer log was reconstructed. Both exact original manifests are independently hashed; environment-specific output differences are listed in local-hosted-manifest-reconciliation.json.

Completed workflows:

- [Canonical release recovery](https://github.com/Richarddavis47/dtos/actions/runs/42761857873)
- [Product browser journeys](https://github.com/Richarddavis47/dtos/actions/runs/42761857745)
- [Validation tooling](https://github.com/Richarddavis47/dtos/actions/runs/42761857641)
- [Linux Asset Market lifecycle](https://github.com/Richarddavis47/dtos/actions/runs/42761857870)

Prior original failures remain separate in PRIOR_ATTEMPTS.md, Prior-attempts.zip and the readable original logs. Counts refer to executions, not that many unique tests or independent Scout review. No real production trade or owner preference was changed.
