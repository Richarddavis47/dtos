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
