# Historical FAAB and score integrity — v1.21.38 / build 2138

Baseline: v1.21.37 / 2137 / 480632d4ae651ec39fff8da5dcf7a98940093d4e. This correction reuses canonical Sleeper facts, the existing Historical Asset Graph and bounded timeline/read-model caches. No new permanent storage, schema migration, provider backfill, scoring/projection model, historical repair or FOIS regeneration.

## Original trade consideration

The original transaction already retained `waiver_budget`; the summary projected only player/pick asset events. The timeline now separately projects source-directed FAAB movements (sender, receiver, exact amount), resolves season-observed franchise identities, and renders each once beside original players/picks. Zero is valid; absent amounts are withheld with an evidence limitation. FAAB is not priced as a Market asset and player/pick totals do not establish whole-trade fairness when FAAB is present. At most 40 FAAB movements are presented; the original transaction remains the source.

The captured actual transaction 965057520920260608 (May 18, 2023, source league 916477632584318976) transfers 100 FAAB from Nasty Navel Lasers, roster 3, to zkobes, roster 6. Its three players and five exact picks remain intact. The small test fixture records source URLs, capture times and response hashes; current player names are independently sourced and do not assert historical ownership or status.

## Scores and source generations

The canonical page previously collapsed `record_key` duplicates using the last row before reconciliation. It now admits all player-week observations from the published evidence before key collapse. Conflicting numeric scores and cross-franchise observations fail closed. Reasons survive subsequent reconciliation and appear in historical player-season HTTP output. Missing and genuine zero remain distinct; identical observations do not double-count. A newly published semantic dataset replaces the old generation's temporary index and can admit a supported correction. Raw Sleeper values are unchanged.

The reducer chooses a deterministic representative for provenance, not a competitive owner or score. A conflicted representative never supplies production or last-scored ownership. The player-week index retains its existing 100,000-row bound; graph/timeline bounds remain unchanged. Read-model version 1.3 identifies the corrected contract without changing persistent schema.

## Related read corrections

- Last-scored franchise comes from the latest supported numeric observation, never a later unscored membership row or final roster.
- Franchise API separates available observed season roster snapshots from weekly roster observations. The franchise page describes snapshot scope explicitly. Missing optional Team Intelligence cannot block supported franchise/roster evidence; no weekly holdings are reconstructed from a season snapshot.
- Legacy Market reads preserve original attachment time separately from effective provider observation time in a read-only field. Stored rows remain unchanged. The real v2136 publisher/current reader test verifies both clocks, future rejection, dated estimates, compatible units and unchanged files.
- Exercised picks describe verified draft conversion and do not offer active-pick Trade actions. Original identity and last observed holder remain evidence, not a claim of current pick ownership.

## Validation and independent acceptance

Focused tests cover both [10,20] and [20,10], repeat reconciliation, identical duplicates, zero, missing scores, cross-franchise conflicts, later corrected publication, canonical historical HTTP output, last-scored owner and separate roster evidence. Actual source replay covers the named three-party trade, two-party/multiple directed FAAB controls and initialized repeat-read file hashes. Rendered Trade, pick and franchise/history routes use 320,375,390px, short/tall portrait and desktop Chromium with overflow, pointer and keyboard/focus assertions. Existing Day 40-conversion, Arkham 260-auction, Love/Boston, chronology, quote, legacy, ownership and current-product regressions remain required.

Before release: full canonical validator (all ten gates), all affected focused tests, HTTP/browser checks, ordinary/archive/combined-read lifecycle and recovery/quiescence under unchanged 2 GiB limits. Do not claim deployment until immutable release and intended production version/build/commit are verified.

Scout should independently check the authenticated live named trade: 100 FAAB roster 3 → 6 once, three original players/five picks intact, source disclosures and subsequent links, readable 320/375/390px/desktop. Replay conflicts in both orders and confirm identical reasons, zero/missing/new-generation controls, no double-counting and repeat-read no-growth. Recheck Love/Boston, prices/context, current Trade/Calculator/My Team/Matchups/standings, exact locks and RETAINED / NOT REVALIDATED FOIS. Distinguish authenticated live evidence, raw source replay, controlled fixtures and responsive Chromium. Physical iPhone/Safari and complete historical coverage are not established by these tests.
