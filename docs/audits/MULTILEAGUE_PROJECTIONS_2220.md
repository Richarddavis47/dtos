# League-configured K/DEF projection continuity — candidate 2220

## Confirmed shared defects

Baseline 118269a2b3c6a6e812422d79818c55d088aff191 limits the existing bulk Sleeper request to QB/RB/WR/TE/FLEX. The parser also discards defensive statistics such as sack, int and points-allowed buckets; a source DEF record with those fields consequently has no canonical projection. Independently, roster diagnostics rejects any starting K/DEF slot before the legal-lineup solver. Horizon Trade impact reuses this same admission gate.

The existing assignment solver already supports exact-position K/DEF eligibility. The candidate adds those positions to the existing single bulk request, admits them to the shared bounded diagnostic gate, and retains explicit defensive statistics under league-specific coefficients. It never derives scoring buckets from projected means or substitutes default points totals. Parser and scoring method versions advance. Required positions remain mandatory; a missing K or DEF is never zero. No Market price is required to score an untraded roster asset.

## Evidence boundary

The connected Opera browser returned reauthentication required. The configured inspection header returned HTTP 401. No authenticated Granite roster/publication was retrieved. Granite settings, generation, exact current week, actual affected rosters and live recovery remain unverified. Do not call this a proven live Granite root cause or claim more qualified live recommendations.

The previously captured Arkham league ID permits an authorized read-only source settings check. It has no dedicated TE slot, multiple FLEX types and Superflex. Do not substitute it for Granite. A bounded public Sleeper 2026 Week 8 K/DEF request returned 185 records and actual K and DEF scoring records. This establishes provider availability for sampled positions, not complete player coverage or admitted DTOS production evidence. Source samples remain separate from disposable fixtures.

## Disposable controls

A 12-team one-QB fixture requires QB, two RB, two WR, TE, two FLEX, K and DEF. Supported source records yield a 115-point legal lineup, including both K and DEF; the stronger bench QB is selected despite the empty submitted slot. Removing K or DEF withholds full lineup points. Explicit zero DEF remains supported and produces 111. A player-only hypothetical exchange reaches independently constructed post-trade horizon and package diagnostics without K/DEF Market quotes. Missing weeks, foreign league/season, scoring mismatch and player-generation conflicts fail closed.

No production ranking, preference, valuation method, goal, lineup or trade was changed. No recommendation thresholds or Market/Custom formulas changed. Decision-card redesign is deferred; the main correction is projection compatibility.

## Validation status

See /workspace/2220-evidence for attempt-specific logs. Initial test harness errors (import name, manual total, incomplete proposal/impact fixture) are retained. The first canonical attempt was cancelled after identifying obsolete fixture inputs; it is not a passing gate run. Release requires a complete canonical rerun, hosted checks and resource/browser evidence on the exact final candidate.


## Build 2222 reconciliation

Preserve candidate225337446e5fb81b05299afc0869db6b3f07fa5e and its earlier evidence. Merge production9b33fa45123eafcdac71ee756898dabfe30a8053 into the same PR310 branch; no rebase or force push. Only metadata/release-note conflicts require resolution. Target v1.22.7/build2222; the three K/DEF implementation boundaries remain unchanged from the original candidate.

All build2221 FOIS safety files must remain byte-identical to production. Focused and full acceptance must use the combined source; older K/DEF hosted passes do not certify this integration. The earlier local3963-test run with3failures/45admission errors remains failed evidence, separately from later passing hosted results.


### Combined-source focused acceptance (2026-11-02)

The original three production files are byte-identical to candidate2253374. Ten FOIS/lifecycle files are byte-identical to production9b33fa4; the reserve remains512MiB plus256MiB. Focused2GiB containers passed the11 K/DEF source, scoring, legal-lineup, provenance, IR/taxi and pre/post-Trade controls;71 earlier projection controls and39 memory/worker controls also passed. The new browser control covers complete, missing-K and missing-DEF fixtures at four viewports with keyboard/touch and no overflow. These are not full release-gate results.

A single authorized, bounded fresh source capture freezes2026 Week8 projections and the two leagues' current roster/settings. Scoring and starting slots match the earlier replay. The new publication differs numerically: Granite supports11/12 legal lineups and Arkham10/10, with owner-reference155.8992 including K/DEF and Josh Allen23.3952 versus49.6052. The prior157.2858/23.4738/49.6638 values remain historical observations, not equality targets after refresh. Granite's previously unsupported DEF roster remains unsupported. No missing value was filled.

Against exactly the same frozen expanded input, production2221's parser omits defensive contributions (owner147.0792) and its diagnostic gate rejects required K/DEF. Combined source admits Granite diagnostics and matches all11 supported lineups exactly; Arkham's10 supported lineups also match exactly. This baseline comparison supplies the expanded feed to both parsers, isolating normalization and admission; source-query inclusion is independently tested. An initial replay mislabeled canonical Taxi slots as TAXI and produced cross-consumer differences. Correcting the replay to the actual Sleeper normalizer's Taxi representation removes every difference; initial results are retained. No application eligibility rule changed to obtain agreement.

These source replays use current source rosters with historical Week8 projections; they are not a contemporaneous Week8 roster reconstruction or a live DTOS publication assertion. Raw authorized roster/settings snapshots are temporary private validation inputs and excluded from public evidence. Only aggregate results and source fingerprints may be published. Configured live inspection returned401 and the separate browser connector required reauthentication; authenticated production recovery remains unverified. No user state changed.
