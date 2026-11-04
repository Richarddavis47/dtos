# Post-Batch-3 Market coverage prerequisite

Baseline: v1.17.1 / 1701 / 22efbcc5e415f11b52ecf37c2830c0b4cb5ec0ff.

## Proven root cause

The shared canonical consensus rejected the entire quote set whenever multiple
providers lacked proven compatibility. This correctly prevented averaging, but
incorrectly removed an otherwise valid single-provider FantasyCalc price.
The active Trade workspace and valuation universe both consume this boundary;
the selector accurately displayed the broken canonical result, not an independent
UI fallback defect.

Production retained cohort: 809 QB/RB/WR/TE identities, 78 priced; 311 rostered,
5 priced; 110 current starters, none priced; 201 bench/taxi, 5 priced. Of 731
unavailable relevant players, 356 had both FantasyCalc and DynastyProcess rows;
375 had neither retained quote. Separate rookie/free-agent counts must not be
interpreted as arbitrary coverage targets. Future picks use a separate pipeline.

## Narrow contract correction

The existing FantasyCalc feed explicitly requests dynasty, 12 teams, numQbs=2,
PPR=1. TE premium remains undocumented, not inferred. DynastyProcess remains
INCOMPATIBLE/UNKNOWN for combined consensus. When compatible consensus cannot
be formed, select the valid primary FantasyCalc reference rather than erase it.
No numerical format conversion, player-specific override or provider-count penalty.
If no primary is available, a sole valid provider remains separately identified;
multiple unproven secondary formats still fail closed.

Explicit historical/expired/invalid/ambiguous/wrong-format rows cannot populate
current price. Ordinary stale evidence retains the established freshness weighting;
this release does not invent a new age cutoff. Retrieval does not become source
update time. Unsupported feeds remain separate, and no missing scalar is filled.

The consumer chain is provider → exact ID ingestion → normalization → canonical
selection → cached_market_consensus → build_trade_workspace/build_asset_pool → UI.
ValuationUniverse shares that selection. Market Intelligence aggregation calls the
same canonical selector. The methodology identity is advanced for this repair;
external historic facts are unchanged. Global evidence is not duplicated per league.

## Source coverage audit

One read-only current FantasyCalc source request returned 422 rows / 422 unique
exact Sleeper IDs, no duplicate or missing IDs. Retained provider data had 376
FantasyCalc rows. 378 current IDs were in the retained player universe; nine were
new relative to the earlier retained refresh (11569, 11623, 12670, 13322, 5857,
7562, 7670, 8122, 9481). The snapshots differ in time; do not label this a mapping
failure or revive removed quotes. Normal scheduled ingestion remains unchanged.

Production quote samples included Allen, Daniels, Bijan, Chase and Kittle with
both exact-ID provider records; canonical price was unavailable despite FantasyCalc
evidence. Mixon had only a DynastyProcess quote and already had a price, demonstrating
the inverse coverage defect. FantasyCalc retrieval was 2026-09-12T18:41:44Z with
unknown source update; DynastyProcess source date was 2026-09-11, separately retained.

## Validation and acceptance

Focused tests cover primary/secondary compatibility, missing/invalid/historical/
ambiguous/expired evidence, source freshness, generation and league independence,
input immutability and the active Trade/valuation path. Canonical release gates and
production acceptance are required before completion. No calibration rerun or
historical backfill is required. Batch 4 NOT STARTED.
