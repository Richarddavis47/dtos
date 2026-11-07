# Avoidable league-runtime retention — final validation

The scoped correction releases superseded league publications that sleeping maintenance no longer needs. It preserves current warm contexts, legitimate old readers, active writers and all persistent recovery evidence. It does not evict a runtime, share account/league catalogs, change restoration admission, reduce the full16×basis or claim Granite recovery.

Baseline: v1.22.22/build2237 `1e1234fbcf7ca18f3862e5cdeac1451780e51b49`,tree`4051883efb1f225dcd71e07f1998e45c9d96fb39`.
Candidate: v1.22.23/build2238 `49e616bc4d5c4a6d49354eea1f2d015b7a1622b4`,validated tree`7ac87bb9ff9f0da6186e50dedd0c93b9bd7bc727`.
PR: https://github.com/Richarddavis47/dtos/pull/327
Final immutable release/merge/deployment receipts accompany this report after publication. At sealing, every application gate has passed; guarded publication is still a separate required step.

## Confirmed ownership defects and correction

The resident periodic refresh kept its completed task during the next15minute sleep. `_refresh_resident_league` returns the full prepared dictionary, so its task result—or exception traceback—could keep an older graph alive after a legitimate replacement. The correction drops that completed task after terminal handling. Repeated cancellation now shields/drains the existing writer through exit before releasing runtime ownership, rather than propagating a second cancellation through gather and detaching a still-active writer.

Separately, the global evidence scheduler retained `STATE.data` although it needs only source season. That local survived ingestion and the next six-hour sleep. It now drops the full-data local immediately after extracting season. Source acquisition, cadence, locks, publication and status remain unchanged. This task is separately owned by startup maintenance and need not appear in runtime.background_tasks. Full provider/season/scoring evidence and active readers stay intact.

Source paths prove replacement is supported by normal publication; tests run the real coroutines and real canonical restoration/publication. Production stack locals and their byte contribution were not inspected. Current valid runtime ownership is intentional; no equivalent eligible production context has been established for eviction. No blind pre-entry eviction or catalog-sharing implementation is added.

## Matched measurements and practical impact

Ten resident controls on509and ten global-owner controls on0a4 use the same pinned public payloads, source, decoder, digest behavior, runtime, instrumentation and actual guards within each comparison; only the measured maintenance function changes. Final49application modules are byte-identical to0a4, and the resident function is identical to509. Original measured source/tree IDs remain unchanged; source-association receipts supply exact hashes. The accepted decoder reconciliation is reused and not repeated.

Three resident pairs recover54.65–56.28MiB settled obsolete retained memory; its failure pair recovers54.80MiB. Three global pairs recover55.08–56.34MiB, with55.21MiB in its failure pair. Raw/file/anonymous/RSS counters and stage samples are published; matched file bytes are unchanged. Native source-fact digests agree. Active-reader controls intentionally retain the old graph until that reader releases it. The resident summary's reader_release=false means the old graph is no longer held after reader release, as named explicitly in its original result.

Complete operation high-water marks are approximately422.4–423.0million bytes (about403MiB), materially unchanged. These include decode, native binding, projection restoration and both canonical publications. They are absolute full-operation peaks, not a reduced cold-restoration bound. Verification occurs after the primary peak capture. Logical ownership release is checked beforeGC; settled measurements apply identicalGC/allocator trim to both arms. They do not guarantee immediate operating-system page return.

A real obsolete owner can withhold material headroom without requiring eviction; removing it avoids that waste. The amount actually recoverable depends on the replaced graph and its remaining legitimate/shared owners. If production has no such obsolete graph, this fix recovers no corresponding bytes. The fixture has distinct replacement catalogs; a normal refresh may reuse source objects. Do not add both owners' figures when they reference the same graph, or extrapolate them to Granite's private payload. Matching serialized size is not representativeness. Current valid data, cache-restoration work and reservations can still exceed the2GiB budget.

## Final mandatory acceptance

| Scope | Result |
|---|---|
| Clean writable focused regressions |123PASS |
| Local Python3.14.3 full regression |4261PASS;zero testfailures/errors/skips |
| Local canonical gates |10/10PASS;640verified manifest entries |
| Hosted exact-source canonical regression |4261PASS;zero testfailures/errors/skips |
| Hosted canonical gates |10/10PASS;644verified manifest entries |
| Required final-source hosted jobs |13/13PASS |
| Product job executions |620+16+121=757PASS |
| Publisher guard unit methods |50PASS;lint/compilationPASS |
| Final local/native hosted ownership protocol |Four real2GiB casesPASS in each environment |
| Existing preflight/native actual restoration and lifecycle |PASS;original source-bound archives verified |

Local full-suite aggregate kernel peak: 1970581504bytes; hosted full-suite peak:2091474944bytes. Both enforced2147483648bytes, no swap, twoCPU, offline. These full-suite peaks include intentional pressure tests, not cache-restoration demand. NoOOM/kill. Original consoles, gate traces, test events, memory/process samples, APIartifact digests, manifests and checksum lists are retained. Native publisher must independently verify all originals before merge/publication.

The four ownership cases exercise guarded restoration/publication, native source binding, invalid identity rejection, real readers, failed refresh, three repeated publications per resident case, real pending-writer cancellation/drain and global-owner release. Unsafe pressure correctly defers; FOIS's independent standing reservation remains protected. Recovery explicitly relieves fixture-owned pressure, rechecks actual capacity and performs one real restore. The global acquisition call alone is mocked identically; it is not counted as an ingestion-completion test. All cases exit with cleaned scratch and no leftover child workers. Existing lifecycle gates retain actual FOIS/Trade completion/cancellation/timeout coverage. Finite cycles do not establish long-term leak freedom.

## Prior attempts and CI reconciliation

Before correction, seven resident methods exposed five failures; four global methods exposed six failing scenarios. Source509's first hosted resource fixture correctly deferred after logical release because allocator pages did not immediately return. The fixture now explicitly relieves only its own pressure and remeasures before execution; no admission or assertion is bypassed. Source509and108cancelled suites remain incomplete, not passing.108Product genuinely completed successfully.

Source0a4local passed4261andall10. Its hosted run42327699300FAILED at4200seconds while making normal progress:4116completed/4117started,zero testerror/failure/skip/OOM. Six gates completed; regression interrupted; three later gates unexecuted. Matched substantial tests ran median1.657×local; actual host/load cause is unknown. Final49changes only CI allowance4200->4500seconds plus bounded artifact margins. Every assertion, resource limit, application timeout and test remains intact. Final49has separate complete local/hosted executions. No failed gate was waived or retried until it happened to pass.

Original failed0a4ZIP78,533,715bytes, SHA732955933c685fad1c94cbfbd4a41a76915ad46d10471866df306275127552c4 and222published/read-back original-readable payloads:
https://github.com/Richarddavis47/dtos/tree/8591cdf8b0ef7cff4b706a375c2d105d777018d8/.task-evidence/resident-refresh-ownership-2238-prior-0a4
Earlier setup failures, cancellations and prior passes remain separate in Prior-attempts.zip. The first509invocationJSON and initial49disk-prerequisite launch console were overwritten before separate preservation and are unavailable unchanged; surviving source-bound logs/results and the actual task record remain. No original is reconstructed. See PRIOR_ATTEMPTS.md for exact distinctions.

## Production evidence and live boundary

Baseline readiness/main/deployment were confirmed. Retained01:43UTCNovember7serving-process log samples show one pinned warm runtime, no runtime-owned background tasks, two observed processes, roughly1.53GBrawcgroup/0.90GBanon/0.60GBfile and zeroOOM. Source-generation count9means source keys, not nine full retained publications. These are historical samples, not a fresh preflight or stack-local inventory, and they establish neither an eviction opportunity nor another worker's current state. Inactive-file bytes are not subtracted arbitrarily. Historical cache/headroom figures are not combined with newer memory samples to invent an admission verdict.

This session exposes authorized Render management reads but no authenticated Shell/SSH executor or associated Browser app execution tool. An earlier separate browser-connector check returned disconnected; no substitute session was used. MainChat's earlier Render-local inspection-tokenHTTP200is supplied evidence, not reproduced. The unchanged external401was not retried or repaired. Fresh Granite preflight, one conditional normal entry and independent completed-week nativeSleeper-to-dossier/Market parity remainHELD. The handoff uses the existing configured token entirely inside Render, grants no reservation and requires normal entry to recheck. Stop on unknown/deferral. No fixture is live parity and no successful entry alone proves cleanup caused recovery.

No production private-cache decoding, forced sync, FOIS rebuild, Trade search, cache clearing, manual restart, active-context eviction, infrastructure/credential change or saved-user-data mutation was performed. A normal authorized release deployment is separate from diagnostic restart or stress.

## Preserved contracts and remaining capacity

The2GiBcap, full16×restorationbasis, FOIS768MiB and Trade256+128MiB policies, actual telemetry, fail-closed unknowns, leases and admission rechecks are unchanged. String-sharing decoder, bounded recovery, atomic publication, legacy caches, source/account/league/generation/scoring identity, restored Sleeper actuals, exact zero/negative/sourceprecision, missing/conflict qualifications, neutral/Custom separation, exact picks, submitted lineups, saved settings and FOIS provenance remain intact. No provider work or heavy search is added to ordinary navigation.

The remaining genuine constraint is capacity for current valid evidence plus safe restoration demand. This correction avoids proven unnecessary roots; it does not establish a smaller safe reserve, privateGranite peak, universal availability or that a RAM upgrade is technically required. Any future immutable catalog sharing needs its own provenance, generation and mutation-isolation proof; it is not bundled here. A larger plan is an alternative capacity choice, not a demonstrated necessity. Independent bounded live acceptance is the next customer-outcome check.


## Completed publication and deployment

PR #327 was merged through the normal expected-head squash operation as `9e9cca569e8c9fb80b1843db4ae8fb248cfcb971`. Its tree is exactly the validated `7ac87bb9ff9f0da6186e50dedd0c93b9bd7bc727`; no unvalidated application changes were introduced. The separate tooling-only publisher revision is `06cfc8c3f93db75a420daca467836681aadde009`; it was never merged into main.

Native Actions preparation run42339581021 and publication run42339860195 both passed on that same frozen tooling revision. All23attachments were uploaded and their complete bytes read back before merge and again after immutable publication. Separate original-certificate checksum/source verification and every GitHub API asset digest agree. Published immutable release:
https://github.com/Richarddavis47/dtos/releases/tag/v1.22.23

Render deploy `dep-dbnapr8ae00c738ihlmg` is live at the approved merge, triggered by normal new-commit automation. It finished at2026-11-07T04:46:55.178687Z. Independent public readiness reports v1.22.23/build2238 and that exact commit. Seven bounded independent guest smoke checks pass, including public entry/authentication boundaries and the exact validated navigation asset. No private league hydration or user-data mutation was part of those checks.

Final local canonical elapsed2783.779seconds and hosted elapsed3650.290seconds. The latter is below both the previous and enlarged CI budgets. Different-run throughput varies; this result does not establish an application speedup or prove that the extra allowance caused this run to pass. The original progressing timeout remains a failed result, separately preserved.

One normal read-only Render metrics query reports three new-instance memory_usage samples at04:47–04:49UTC:268742660,427266050and766681100bytes. These are coarse management metrics with unestablished raw-cgroup/working-set semantics; rounded limit series include old/new instances during rollout. They are not fresh restoration admission inputs, an operation peak, a leak test, cleanup causation or Granite recovery. Exact2GiBenforcement and admission protection are independently demonstrated by the constrained tests.

Fresh authenticated Granite preflight, conditional normal entry and independent completed-week Sleeper actual-score parity remainHELD for the specific missing session capabilities in live-access-limitation.json. Shipping this correction does not establish Granite recovery or the cause of the earlier503. The exact existing Render-local procedure and stop conditions are in SCOUT_HANDOFF.md; the completed credential check need not be repeated.
