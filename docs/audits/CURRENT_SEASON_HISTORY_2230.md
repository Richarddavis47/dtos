# Current-season franchise history — source-to-screen correction

Baseline: v1.22.14/build2229, commit769bf99ee719f5e353822cdbd75b9259c8fd5fe1, tree752cfe006296bcaf879472183d100fa9df940fbb. Target v1.22.15/build2230. No related unfinished implementation was found.

## Confirmed lifecycle gap

Fresh Sleeper synchronization calls CanonicalHistoryStore.update_current, but restored-cache hydration and cached default startup publish through _publish_runtime_context without that registration. A matched disposable cache contains eight weekly buckets and a completed trade; the original production source tree returns no current franchise observations. The same actual restore and route control passes after shared context publication registers the owned data reference. Current records are not a completed-season backfill; that pipeline still skips the ongoing season appropriately.

Registration uses the existing canonical method, source object and lock. CanonicalLeagueContext.close releases the current reference by identity on owned-runtime eviction. A late close cannot remove a newer publication. No historical reconstruction, provider call, solver, new lease or permanent provider store is added. Existing restoration admission, JSON bounds and the 2GiB cap remain unchanged. Cached context history readiness is partial, not a claim of complete history.

## Acquisition and coverage

Existing full synchronization requests current and preceding buckets0..selectedWeek; request count is unchanged and capped by the existing supported0..18period contract. The existing cache publication now carries at most19scoped per-period observations: observed, observed-empty, unavailable, malformed or failed; retrieval/attempt time; and whether an unsuccessful refresh retained a last-valid bucket. Context is admitted only for the same league and season. New retrieval timestamps are captured after responses; legacy dates remain unknown. Transaction-only success publishes its small acquisition metadata under the existing source-publication lock. Failed transaction-only refresh preserves the source and the existing safe warning; recorded timestamps are not represented as the latest attempted refresh.

The canonical coverage fingerprint includes acquisition metadata so dates and qualifications cannot remain cached behind unchanged transaction IDs. Supported source bucket rows remain useful; malformed unsupported periods are qualified. Rendering shows retrieved and observed-empty weeks, source gaps, selected source week, recorded times and last-valid status. Ongoing source seasons remain partial; empty retrieved buckets do not establish empty missing weeks. Completed seasons still require all supported periods, compatible source identity, closed-source status and no unresolved qualification before a no-activity conclusion.

## Evidence scope and acceptance

Controls use disposable authoritative-shaped league publications, not production caches. They cover real sync/save, cached restoration, eviction/reopening, stale owner close, identity mismatch, multiple isolated league contexts, legacy flat transactions, partial failures and unknown dates. Three independent source configurations represent Granite one-QB with K/DEF, Day Traders and Arkham Superflex; their names are fixture labels, not live recovery claims. Twelve phone/desktop controls verify320x432,375x667,390x844,1280x900, keyboard/touch, no overflow, stable facts and no provider work on disclosures. Existing account authorization, completed-season history, transaction/pick/ownership and pagination controls remain mandatory.

An intermediate focused failure caught a timestamp callable incorrectly applied to matchup metadata; it was corrected and the original failed log retained. An early browser fixture attempted asyncio.run while Playwright owned a running loop; setup now completes real restorations before browser startup. No application admission, memory threshold, timeout or assertion was relaxed to pass either case. Original matched baseline failures, lint/setup failures and final passing logs remain separate in task evidence.

No current private Granite cache or authenticated owner history was inspected. Supplied live observations establish that2026was shown unknown, not whether its weekly buckets were acquired. This correction therefore proves a reusable source-path defect and fixture recovery, not that it retrospectively establishes the exact cause of that live state.

Trade qualification, Neutral/Custom valuation, grading/scoring, optimal/submitted lineups, pick identity, saved preferences, FOIS RETAINED / NOT REVALIDATED and independent768MiBFOIS/384MiBTrade policies are preserved. Mandatory final-source canonical/hosted results and guarded publication records establish release status separately from this design/source record.
