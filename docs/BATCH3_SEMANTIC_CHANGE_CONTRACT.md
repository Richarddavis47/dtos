# Batch 3 semantic change contract

This extends the existing bounded valuation timeline. No new database, provider
fetch, report/narrative engine or Batch 4/6 functionality is introduced.

`valuation_intelligence/changes.py` defines the methodology manifest covering
normalization, rank scope, intrinsic profile, production, provider compatibility,
grading, missingness and source-clock semantics. Its deterministic identity participates in the Brain
semantic digest and new DTOS checkpoint model identities. Old external Market
facts are not rewritten. Old DTOS history without this identity establishes one
methodology transition rather than price/quality movement.

Reason codes distinguish raw provider prices from normalized-index movement,
production quality/sample, usage and usage boundary, weekly projection and its
boundary, status, role/team context, confidence, source tiers, format boundaries
and ranks. `RANK_CHANGED_PEER_MOVEMENT` requires unchanged subject evidence and
unchanged rank scope/universe with a changed ordinal. Otherwise rank movement or
a universe boundary is reported without claiming a cause.

Explicit missing-to-present or present-to-missing events are availability changes,
not numeric gains/losses. Same-method unchanged snapshots produce no event.
Snapshots use JSON-native types so serialized/reloaded tuples cannot create false
changes. All records are league/asset scoped; a different context cannot be
compared as ordinary movement.

Storage: existing 50-event-per-asset cap is preserved. Only the latest event keeps
the compact comparison snapshot; older events retain codes, methodology and the
existing summary fields. Unchanged replay adds no rows. No per-league global NFL
warehouse is introduced. This local proof is not a production disk measurement.

Focused evidence: active valuation/Brain/API module 25 passed; memory-runtime,
Matchups evidence and final-panel tests 27 passed; change/consumer suite 11 passed
before the final JSON-native refinement; the targeted six-test refinement rerun passed.

## Source clocks and validation follow-up

Cached Market rows use explicit `source_updated_at` for provider freshness.
`retrieved_at` (legacy `updated_at`) remains the observation/knowledge clock;
`published_at` is retained separately. No timestamp is synthesized on a cache
read. Source time cannot backdate projection knowledge in checkpoint evidence.
Market history keeps observation ordering and rejects a late older source state
as forward price movement. External historical observations are not rewritten.
The provider-price observation methodology is v2, making the transition explicit.

The pre-correction canonical run completed 1,678 tests in 2,260.277 seconds with
36 failures and 9 errors. It stopped before route/HTTP gates. Compilation, lint,
dependencies and whitespace passed on that pre-correction boundary. This is not
validation of the subsequently corrected source.

The first corrected focused group passed 110 tests (Market clocks, normalization,
providers, trends, valuation, Data Platform and UI contract checks). The source
panel already used unknown FantasyCalc publication freshness, so its player
calibration is not invalidated. No fresh provider fetch or full calibration rerun
was performed. Further affected regression work remains required.

Follow-up focused groups passed: 130 historical/projection/memory tests and 82
Market/Brain/consumer boundary tests. Legacy quote-cache hits and fallbacks also
preserve retrieval time and do not relabel unknown/stale source evidence fresh.
Brain confidence schema is 1.1 for nullable agreement. The corrected candidate is
now proceeding to canonical validation; no release or production pass is claimed.

The subsequent full run completed 1,684 tests with six failures and three errors.
Focused classification found obsolete scalar/label/fixture-version expectations,
a same-position swap incorrectly claiming net-new depth, and restart diagnostic
tree expansion exceeding its representation budget. All 92 tests covering these
remaining failures passed after correction. Net position-count growth is now
required for the depth reason; no new Trade Intelligence model was introduced.

Restart evidence v4 fingerprints complete valuation layers at layer granularity,
while provider fields remain expanded. Every nested credential key is still
rejected, any layer field change changes its fingerprint, and prior schemas cannot
be silently compared. Input-byte, output-byte and node limits are unchanged.
This is restart evidence only, not restoration of retired capture/publication.

A concrete Brain decision adapter failure (`float(None)` on unavailable agreement)
was also corrected: agreement remains unavailable, and confidence weights are
renormalized over supported dimensions. No synthetic agreement or provider-count
penalty is introduced. This correction needs the same final authoritative gates.

Release/production acceptance is not yet complete. Preserve stable canonical
inputs for the required restart test; a legitimate source transition is not an
artifact-reuse defect. Current Visual, DINS and Mirror remain retired.

Final regression passed (432.267 seconds), as did route/OpenAPI validation
(252 registrations, zero duplicates, 234 paths). HTTP validation then exposed
an obsolete caption assertion requiring filtered results to be called dynasty
rankings. The validator now requires the scoped filtered-results label and
rejects the retired label. All 25 affected contract tests passed, followed by
tracked HTTP startup/smoke/graceful cleanup/process-cleanup PASS. No product
source or threshold changed for this validator correction. Final canonical
completion and Linux/browser release gates remain required.

Final canonical validator: 10/10 PASS in 542.633 seconds on the corrected
candidate. Regression: 428.620 seconds; routes: 252 registrations, zero
duplicates, 234 OpenAPI paths; tracked HTTP: 94.699 seconds; process cleanup:
PASS. Linux and lightweight browser checks plus production acceptance remain
pending. These results do not claim a release or production pass.

PR #180 initially passed all three Linux scenarios on 90aae7e. The browser
job exposed 390px Player Dossier overflow on Linux across account/league cases.
Focused diagnostics separated contained table scrolling from text overflow.
Wrapping the large value label (including Unavailable) within its card fixed
the document width without clipping content, changing font size or semantics.
Fifteen focused local tests passed; isolated Linux browser run 34436380418
passed. Final PR checks must pass on the corrected commit before merge.
