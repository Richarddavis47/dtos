# Resident-refresh ownership — release review

Status: VALIDATING. No merge, immutable release or deployment claimed here.

Baseline v1.22.22/build2237: `1e1234fbcf7ca18f3862e5cdeac1451780e51b49` / `4051883efb1f225dcd71e07f1998e45c9d96fb39`.
Candidate v1.22.23/build2238: `108624a0a3be61501376de243a54f23dd2e1e34a` / `a09397ad108c2bf221a70ff55fe7e06ab1cbc07c`. PR#327.

## Confirmed cause and chosen correction

The resident maintenance coroutine retained a completed worker for the next interval. Its task result or failed traceback could pin a superseded full source publication after a separate legitimate replacement. This is unnecessary task ownership, distinct from current warm contexts, request pins, persistent recovery data and allocator retention. The worker's local reference is now dropped after terminal processing. Repeated cancellation drains the existing writer through shield before close/release. No eviction or immutable-catalog sharing is implemented. Existing periodic schedule, persistence, failure qualification and source publication remain unchanged.

## Measured impact and limits

Three matched full restore/publication pairs in real2GiB/no-swap/twoCPU/offline Python3.14.3 containers show obsolete settled retained-memory reductions of54.652,56.281and56.176MiB. A failed-worker pair recovers54.801MiB. Exact native facts/disclosures digests agree. During an active-reader control the old source intentionally remains, then releases only after its reader. Peaks are approximately403MiB and materially unchanged. No smaller restoration allowance is supported or proposed. Measurement includes actual cache decoding, native binding, projection restoration and canonical publication; verification clocks and GC/allocator trim are disclosed in methods and counters.

The matched pairs used commit509; its complete production refresh function is identical in final108. The fixture payloads are source-compatible public disposable data, not a privateGranite profile. In the first hosted Python3.12 run, logical release returned only~10.7MiB immediately and recovery correctly deferred. The fixture had incorrectly assumed sufficient immediate allocator return. Final recovery explicitly relieves its own remaining pressure and checks actual admission before one real restore. It does not attribute recovery to the code change alone. Original failure and canceled superseded suites remain separate.

## Safeguards

No current/active source eviction, catalog/account overlay sharing, cache format change, source loss, provider acquisition or retry loop. Full16× physical cache basis,2GiB cap, FOIS768MiB and Trade256+128MiB reserves are unchanged. Native Sleeper results, exact zeros/negatives/precision, scoring, pick identity, submitted lineups, neutral/Custom mathematics, saved preferences and FOIS provenance remain unchanged. Genuine incompatibility and unsafe capacity still defer/reject.

## Production boundary

Authorized Render management evidence confirms the baseline and retained logs/metrics, but cannot provide the current serving process's full ownership snapshot. This session has no authenticated Render Shell/SSH executor; the existing browser connector reports disconnected. The unchanged external401 binding is not retried. MainChat's previous local token200 is supplied evidence, not reproduced. No private cache decoded, no Granite entry or Trade/sync/FOIS workload initiated. Fresh preflight, conditional entry and independent completed-week actual-score parity remain HELD until existing authorized live access is available. No synthetic result proves Granite recovery, production causation or long-term leak freedom.

Final gate counts and immutable/deployed identity will be added only after verified completion.
