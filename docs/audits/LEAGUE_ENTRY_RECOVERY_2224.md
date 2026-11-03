# League-entry coordination — build 2224

## Confirmed production path

At 2026-11-03 03:15:24 UTC, an authenticated league-entry request reached secondary runtime acquisition, hydration and Sleeper synchronization. The coordinator rejected `sleeper_sync` at its FOIS exclusion check. The source service caught the scheduling exception as a generic source failure; the hydrator found no resident data and raised a generic runtime error. Middleware rendered HTTP 503 with “No supported roster is ready.” A favicon request immediately repeated the acquisition.

Correlated cgroup samples were 1,487,843,328–1,488,097,280 bytes against 2,147,483,648; approximately 940.5 MB anonymous and 522.7 MB file-backed. The FOIS worker RSS was approximately 203.2 MB. OOM and OOM-kill counters were zero. This was a scheduling rejection, not a Trade execution or demonstrated OOM. The failed runtime had no source generations, Market or projection context. Logs establish no resident usable Granite publication; they do not establish whether its disk cache existed or was compatible.

Secondary caches were already persisted per league, but only default-league startup loaded them. Normal warm runtime acquisition was already local and remains unchanged.

## Narrow correction

* Distinguish `HeavyWorkDeferred` from source failure. Preserve original exception privacy and last-valid evidence; diagnostics record deferred rather than completed synchronization.
* Try the existing bounded, retained cache before cold secondary synchronization. Require explicit matching league/season, coherent league scoring and roster rules, nonempty prepared team population, an admitted cache file and valid last-sync timestamp within the existing 30-day retention policy. This does not revalidate current projections or Market evidence.
* Decode one pinned opened generation under the existing lifecycle coordinator, with nonqueued admission. Raw container headroom must cover max(128 MiB, 16 × serialized bytes) plus 128 MiB safety. While FOIS owns a generation lease, additionally preserve its full 512 MiB outstanding working allowance and its larger 256 MiB safety margin; do not count the current worker footprint as proof that future allocations are already committed. Unknown telemetry fails closed. No file-cache credit, no changed FOIS or Trade reserve. This is a conservative measured admission allowance, not a proof for all possible source populations.
* Publish the existing source facts and cheap consumer context without starting historical, FOIS or Market preparation. Reuse the existing resident refresh cadence, not a new polling loop. Visible pages disclose saved-data freshness.
* Cold blocked hydration remains a distinct deferred runtime. Manager-owned single flight and a 60-second retry cooldown prevent repeated navigation from duplicating work. Recovery is explicit page retry after the cooldown when capacity permits; there is no automatic expensive retry or promise that an active lease will finish within a minute.
* Warm refresh deferral preserves supported existing pages and reports waiting for capacity. Source failures remain separate. No preemption or cancellation of active FOIS work is introduced.
* Cache-reader threads are drained before cancellation/shutdown releases their runtime. Restores create no scratch copy and do not write the source cache.

A further end-to-end source-cache → one-QB Trade control reproduced a real JSON boundary defect: saved pre-trade weekly keys were strings while newly computed post-trade keys were integers, causing a KeyError for week 8. Both default and secondary cache reads now restore the existing canonical integer key type, rejecting malformed/ambiguous week identities. Evidence, points and semantic generations remain unchanged. The original full run was canceled and retained; the final revised candidate requires fresh complete validation.

Final admission review identified that raw-current-only cache admission could spend outstanding FOIS capacity. The new reader now explicitly preserves the existing FOIS working and safety allowances while that lease is active. Healthy constrained-container restoration is tested with sufficient measured headroom; at higher retained pressure the same read is deferred during FOIS and succeeds after lease release without assuming memory has disappeared. Earlier raw-only diagnostic successes are retained as superseded, not final capacity clearance.

## Preserved contracts

FOIS raw 768 MiB policy and Trade 256 MiB working plus 128 MiB margin are unchanged. No scoring, projections, submitted/optimal lineup mathematics, K/DEF rules, Market/Custom values, exact pick identity, bilateral verdicts, saved preferences, goals or rankings change. Public account/Welcome and contextual history/Trade workspace contracts remain intact. No new source warehouse, provider polling or anonymous analytical work.

## Evidence and limits

Focused and resource evidence is retained outside source and attached to the immutable release only after every mandatory gate passes. An initial combined resource control incorrectly assumed a global disposable cache was empty; it restored a prior test's publication. The fixture now isolates its own cache family. That original failed attempt remains retained; no application guard was bypassed.

Diagnostic resource attempt 2 used actual Python 3.14 in a 2 GiB, two-CPU, network-disabled container. A separately prepared 17,776,613-byte source-shaped cache restored while a real process worker held the FOIS lease: current usage 1,564,864,512 before and 1,641,132,032 after; unsafe-pressure sample 1,938,137,088 deferred before decoding. After relief, current usage was 130,449,408 and a new restore completed at 206,974,976. Worker reaping was verified. Harness anonymous padding was explicitly 1,433,534,464 bytes, never subtracted to claim production headroom. These diagnostic numbers precede the final frozen candidate and must be corroborated against final source, not reused as exact-candidate acceptance.

A separate real HTTP fixture evaluates one-QB pre/post legal lineups including K/DEF and FLEX without K/DEF Market quotes. It is not a live Granite recommendation or a claim that every franchise has projections. Existing FOIS/Trade completion, cancellation, timeout, source compatibility and cleanup controls remain mandatory.

Production capacity remains bounded by the existing infrastructure. Restoring a large publication can itself be deferred. A missing/incompatible cache still requires admitted source preparation. No broad capacity clearance, physical iPhone/Safari verification or live Granite recovery is claimed from Chromium/fixture results.

## Independent Scout acceptance

1. Enter Granite normally, without forcing a source refresh or FOIS rebuild.
2. Confirm selected account/franchise, source timestamp, league-specific scoring, one-QB/FLEX/K/DEF legal lineup and prepared publication compatibility. Distinguish saved facts from refreshed evidence.
3. Inspect current Trade resource readiness separately. Do not equate page readiness with search admission.
4. Only with sufficient fresh measured capacity, run one bounded normal Trade search. Qualified offers are not required for a completed search.
5. Inspect legal pre/post lineups, exact picks, bilateral evidence and final verdict. If capacity is deferred, retain the workspace and retry explicitly later; do not force the workload.
