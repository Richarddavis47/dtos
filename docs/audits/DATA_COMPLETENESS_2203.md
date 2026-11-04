# Phase 2 source to screen findings

The 24-surface inventory continues build 2202; rows are coverage categories, not assumed defects. This is a cohesive correction of one shared Market publication defect and one narrow matchup layout defect, not full-site production completeness acceptance.

## Proven Market continuity loss

The released normalizer pins a scalar reference from the full provider population before relevance filtering. Reading the retained reference preserves its value, but preparing an unchanged cached subset again discarded it and recalculated the curve from that subset. A 100-row fixture's player quote remained 440 after filtering, then became 417 after cached re-preparation. No source price had changed.

Cached subset preparation now preserves player and supported pick references only if every priced retained item has a matching raw value, provider, supported method/version, bounded numerical value and the same full-population generation/size. Missing, damaged, changed or mixed partial references fail atomically. Heavy work does not enter the publication lock; preparation still uses a detached snapshot and commits only against the unchanged source identity. A fresh full provider response without references uses the existing formula and establishes a new generation normally. No percentile formula, source scale, price-selection policy, Custom slot model or historical record changes.

Retained provider row counts also identify known partial tables when all references are absent or were previously recomputed from the subset. Those cases fail closed. During the existing synchronization cycle, the adapter retries that provider with a complete response instead of reusing a known incomplete cache. Compatible retained references do not trigger a source call. A failed recovery preserves the last successful source count and cached facts, so subsequent normalization cannot promote the subset as a complete population. No new poller or request-time fetch is introduced. Legacy caches lacking both retained full-population references and reliable source counts cannot reveal their discarded original population; this batch does not reconstruct that missing metadata. This correction prevents future repeated drift; it does not reconstruct missing past metadata or force live synchronization.

## CSV observation continuity

DynastyProcess CSV values are strings. The normalizer correctly prices them, but the observation producer compared the raw string to its numeric reference and discarded otherwise supported provenance. A source CSV/crosswalk fixture produced a canonical price of 500 from native "5000" while observation evidence was absent. The observation boundary now compares validated finite numerical meanings, keeps existing numeric types, rejects malformed/bool/nonfinite quotes and retains the reported day precision without inventing an update hour. The quote, neutral price and exact identity are unchanged. Existing checkpoint capture can retain the supported source observation; no old history is backfilled or regraded. Day-only source timestamps still do not become exact-time comparisons.

## Four reported saved identities

Read-only public reads on 2026-10-27 verified 13602 Jack Strand QB (rookie), 13075 Myles Price WR, 3155 Laquon Treadwell WR and 11593 Brevyn Spann-Ford TE. All four were active in that Sleeper response. FantasyCalc's configured 12-team 2QB PPR response included native quotes for 13075 and 11593; neither other ID was present. The supported exact DynastyProcess crosswalk/value join produced no current quote for those four. Provider-native amounts are not canonical prices or personal values.

The configured inspection credential received private/no-store 401 from both existing operational identity and semantic inspection entry points. Therefore the production publication, league format, saved identifiers/revision and exact exclusion reasons remain unverified. No authorization bypass, live preference read or write was attempted. Names were resolved by exact IDs, never substituted by name.

Full Custom numerical use remains guarded if a saved cohort member is unpriced. With two known prices 800 and 300, an unknown third price of 200 versus 900 changes the ordered curve from [800,300,200] to [900,800,300]; no fixed slot in that example is determined. Dropping the unknown changes unaffected personal values and is not a safe partial-use policy. Saved editing, tiers, flags, exact picks and individual confirmed recovery remain supported; no fallback price or automatic reset is introduced.

## Matchup readability

Actual fixture HTTP/browser reproduction found 129px player cells at 320x432 with no document overflow. At widths up to 360px, sides now stack and display the source franchise label; wider comparisons stay paired. Points, projections and source qualifications are unchanged. Required viewports, keyboard focus, native disclosure and touch controls are tested.

## Ranked remaining source gaps

1. Restore authorized read-only inspection access to the pinned production Market publication and diagnose the four saved IDs there. Public presence alone is insufficient compatibility proof.
2. Trace normal sync's reuse of a filtered player catalog for newly rostered IDs. Source inspection identifies a possible identity gap before the daily full-player refresh; no production failure or safe bounded acquisition change was established in this batch.
3. Trace cached filtered provider membership versus newly relevant assets; never import a new quote or change the full-population curve from a partial table.
4. Measure projection publication coverage for the exact league/week/scoring. Prepared absence is not proof that Sleeper has never published the field.
5. Preserve historical completed/attempted status, manager-tenure and contemporaneous-quote qualifications. No extra historical scan or FOIS generation is used to fill a display.

No new provider calls, factories, persistence or background work are added by these changes. Existing cache limits, runtime eviction, source locks, 2 GiB memory protection, request isolation and RETAINED / NOT REVALIDATED grades remain intact. Full validation and release remain conditional on passing required checks. Evidence distinguishes public-source observations, denied production access and disposable fixture controls.
