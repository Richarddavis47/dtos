# Historical Market trend integration — v1.21.70

Baseline main/production: v1.21.69/build2169, `7da326fc36b5abf4a1730a7fafc9eb7c846eeec6`. Reconciled before changes. Supplied Scout findings, accepted repository contracts and the current request govern this correction; no separate unavailable private Blueprint or Scout artifact is claimed inspected. The preceding historical player-week/age batch is independently accepted within its tested scope.

## Reproduction and root cause

Actual canonical price selection (raw FantasyCalc 1200/1440/2400, normalized 100/120/200), sparse checkpoint producer/store and actual Market HTTP routes reproduce +20 rather than +100. The route passed a bare current number and an arbitrary provider/status clock but omitted the comparison semantics that the existing v2 evaluator correctly requires. Directory and selected detail shared this omission. `/api/market/trending` also advertised v1 while executing v2.

## Shared correction

`market_trends.current.current_comparison` reads the compact evidence already attached to the selected prepared canonical price. Price, asset identity, normalization semantics, provider membership, observation times and source generations remain bound to that handoff. It rejects missing/mismatched identity, missing/nonfinite/bool prices, native units, unsupported methods, missing/future clocks and conflicting selected-provider generations. It does not select prices, convert units, fetch providers, solve lineups, capture history or write records. Provider-price normalization and sparse-memory record normalization are separate version domains; the former remains inside the explicit comparison identity.

All Market directory/trending/selected/detail consumers pass this structured evidence into the same evaluator. Compatible 100/120/200 yields +100 overall and +80 since the latest 120-valued season-start fixture checkpoint. The existing volatility rule classifies this series as volatile; this release does not force a rising label. Compatible current zero also remains numeric. Explicit past-date HTTP requests exclude today's current endpoint.

The evaluator admits only finite, identity-matched, dated observations known by the requested boundary and no later than now. It sorts actual instants rather than lexical date labels, preserves compatible historical-only movement when the current endpoint is unsupported, and excludes contradictory source generations. Default cache keys include source facts; explicit queries follow existing immutable observation revisions. Cache capacity stays 512. An empty supplied batch does not cause redundant per-asset source reads.

Responses disclose comparison scope, units, start/end dates and current-endpoint qualification in compact and detailed views. Historical range remains the retained historical range, not a fabricated daily series. Old or unknown source clocks do not become Fresh through retrieval; an admitted retained current publication is compared at its recorded observation time and explicitly qualified. Existing confidence/materiality/volatility formulas remain unchanged. Checkpoint age now reflects elapsed time on current reads instead of freezing at the last checkpoint.

## Consumer boundaries

The selected Market view shows magnitude and dates behind its existing disclosure, with shared explanation rows. Trending metadata reports `sparse-event-market-trend-2`. The player dossier links to that canonical comparison and keeps its independently labeled FantasyCalc raw-provider 30-day change separate. Raw-provider historical APIs are not relabeled canonical Market trends. Trade's existing history-only context remains qualified by the shared evaluator; no evaluator/recommendation, fairness, strategy, lineup or projection formula changes. Buy Low/Sell High valuation gaps remain distinct from demonstrated transaction outcomes; no optimal manager timing claim is introduced.

## Verification and storage

New source/HTTP controls reproduce failure before correction and cover missing/zero/future/stale/identity/unit/method/generation boundaries, one and multiple checkpoints, source revision, warm reads and actual selected HTML. Existing producer/compatibility controls preserve raw DynastyProcess boundaries and no rewriting of historical records. Repeated warmed HTTP reads preserve every sparse-store table/row and fixture file size, with no sync or checkpoint ingestion invoked. No schema, persistence path, provider dependency, permanent archive or background collection is added. Retained FOIS grades remain RETAINED / NOT REVALIDATED.

Isolated rendered Chromium uses actual routes/theme in both league contexts at 320×432, 375×667, 390×844 and 1280×900. Comparison disclosure is initially closed, keyboard/pointer usable, with visible focus and no document overflow. Measured trend card heights: 438.02/396.02/375.02/249.02px; disclosure summary 44px. These are controlled author-run observations, not authenticated live league evidence, physical Safari or independent Scout acceptance.

Full canonical validator, focused preservation, hosted CI/product-browser and unchanged 2 GiB/500ms lifecycle gates are release prerequisites. Exact results, commit, release/deployment identity and production-safe observations belong in the final PR/Scout handoff. Physical iPhone/Safari, human comprehension and comprehensive screen-reader acceptance are not claimed.
