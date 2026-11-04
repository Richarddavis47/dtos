# Batch 4 decision coverage — unfinished diagnostic

Read-only production archive inspection, 2026-09-13. No archive download,
source deployment, database mutation, SSH key or temporary remote file.

## Day Traders activity inventory, 2021–2025

Counts are completed source records grouped by season roster owner. Trade
counts are manager participations, not distinct league trades. Selections
include startup and rookie drafts. Exact decision-time tenure and duplicate
source-event reconciliation are still required before final acceptance.

| Manager | Trade participations | Selections | Adds | Drops | Non-trade records | Bid present / absent |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| RichardDavis47 | 82 | 38 | 120 | 117 | 168 | 26 / 142 |
| anthonyrangel | 9 | 45 | 23 | 37 | 40 | 5 / 35 |
| Mears30 | 28 | 48 | 115 | 130 | 147 | 28 / 119 |
| danreilley | 63 | 34 | 221 | 210 | 252 | 28 / 224 |
| garrettadame36 | 25 | 35 | 115 | 115 | 157 | 40 / 117 |
| zkobes | 18 | 33 | 41 | 47 | 56 | 12 / 44 |
| davefedex | 116 | 42 | 211 | 230 | 266 | 56 / 210 |
| OGV | 75 | 25 | 113 | 117 | 159 | 11 / 148 |
| TheLandsharks | 16 | 42 | 78 | 97 | 118 | 20 / 98 |
| Markgus13 | 32 | 28 | 81 | 84 | 106 | 21 / 85 |

Bid presence checks `settings.waiver_bid is not None`: genuine zero counts as
present. Absence is **not** automatically missing applicable FAAB evidence;
non-trade records include free-agent adds and drops. Claim-type applicability
must be reconciled before a FAAB coverage percentage is reported.

## Bounded second-league sample

Super Flexxxin 2022–2025: Richard has 55 trade participations, 34 selections,
84 adds, 74 drops and 111 completed non-trade records (17 bids present, 94
absent). All 13 observed managers were enumerated separately by source owner.
These are not FOIS quality grades and not a completed intra-season tenure proof.

## Active evaluator coverage

The candidate history adapter now supplies `decision_coverage`, counting
discovered/attributed decisions, process/outcome evaluability and measured
Market coverage separately. Unknown player-evidence coverage remains null.
This is integrated in `load_results_history`, not a separate grading engine.

The active Drafting adapter currently sets value-over-expected unavailable;
the Waiver adapter sets value-created/FAAB efficiency unavailable. This must
not be reported as zero decision quality. Final source-backed process/outcome
counts have **not** been obtained from the completed candidate yet.

Also corrected an explicit-zero completeness fallback in FOIS Trading: a
canonical 0% no longer silently becomes the sample-based default. Nine focused
coverage/attribution/missing-evidence tests passed. No comprehensive gates run.

Remaining: exact attribution, distinct-event reconciliation, decision-time
Market/player coverage, outcome maturity, historical roster coverage, final
category/overall calibration, Pick methodology and runtime parity. Batch 4 is
not complete; Batch 5 remains unstarted.

## Evaluability classification implementation

The active history adapter now retains canonical historical process dimension
availability. Coverage distinguishes evaluable, partially evaluable and
insufficient independently for process and outcome, grouped by source owner
and season within the supplied league/franchise history. Summary counters use
the same classification. A present numeric score alone is not full coverage.

Trading requires attribution, a zoned decision timestamp, package identity,
complete contemporaneous Market coverage and available historical dimensions
for the full-process label. Draft and waiver full-process labels additionally
require their explicit decision-time evidence/identity/context fields; these
are not inferred from later results. Outcome can remain evaluable without
process, and vice versa. Explicit zero quality remains evidence, not missing.

Twelve focused tests pass, covering independent process/outcome, partial
coverage, missing boundaries and prevention of newer-season coverage leaking
into older seasons. These are implementation proofs, **not final real-manager
evaluability counts**. No final grade or comprehensive gate was produced.

## Read-only production retained Trading assessment audit

Deployed `fois_scores_v2` records with nonempty front-office evidence contain
these distinct summaries. They are retained classifications, **not a rerun of
the unreleased candidate** or proof that historical evidence is exhausted.

| Manager | Activity | Process evaluable / partial / insufficient | Outcome evaluable / partial / insufficient |
| --- | ---: | --- | --- |
| RichardDavis47 | 82 | 0 / 0 / 82 | 0 / 0 / 82 |
| Markgus13 | 32 | 0 / 0 / 32 | 0 / 0 / 32 |
| danreilley | 63 | 0 / 0 / 63 | 0 / 0 / 63 |
| davefedex | 116 | 0 / 0 / 116 | 0 / 0 / 116 |
| garrettadame36 | 25 | 0 / 0 / 25 | 0 / 0 / 25 |
| Mears30 | 28 | 0 / 0 / 28 | 0 / 0 / 28 |
| zkobes | 18 | 0 / 0 / 18 | 0 / 0 / 18 |
| OGV | 75 | 0 / 0 / 75 | 0 / 0 / 75 |
| TheLandsharks | 16 | 0 / 0 / 16 | 0 / 0 / 16 |
| anthonyrangel | 9 | 0 / 0 / 9 | 0 / 0 / 9 |

All ten explicitly record zero evaluated transactions and zero completeness;
both distributions contain only `insufficient_evidence`. No quality grade
follows from these 564 participations. Richard's 38 draft selections remain
activity evidence; final candidate draft evaluability is pending. Aggregate
payloads do not supply season-level decisions.

### Historical quote-identity defect

Read-only global checkpoint inspection found 578 historical backfill
observations: 422 player mappings (`fantasypros_to_sleeper`) and 156 pick
observations (`generic_pick_round_average`). The latter averaged Early/Mid/Late
quotes into a fabricated generic quote. They cannot support canonical generic
pick Market grading. No production records were changed.

The candidate admits only explicit generic source labels for generic picks.
It excludes retained synthetic averages from canonical checkpoint projection
and historical resolution, preserving stored records for audit. The checkpoint
read-contract version changes accordingly. Twenty-eight focused historical
Market tests pass, including retained-record preservation, direct/flight
exclusion and explicit generic selection. The initial pytest invocation could
not run (pytest is not installed); unittest executed the tests successfully.

Historical checkpoints can reference global observations despite a null local
Market column; that null alone was not classified as missing evidence.
Timestamp/provenance inspection and real candidate decision application remain
open. No production write, comprehensive gate, release or Batch 5 work.

## Candidate applied to real cached Day Traders decisions

The active `load_results_history` and `decision_coverage` path was executed
against the local retained 2021–2025 Sleeper cache, without provider requests.
This is a candidate adapter proof, not production checkpoint parity. Local
checkpoint coverage differs from production. Drafting and Waiver quality
evaluators are not yet connected: their insufficient state must not be claimed
as proof that the original source could never support evaluation.

| Manager | Trades | Selections | Completed waiver/free-agent actions |
| --- | ---: | ---: | ---: |
| RichardDavis47 | 82 | 38 | 168 |
| danreilley | 63 | 34 | 252 |
| davefedex | 116 | 42 | 264 |
| garrettadame36 | 25 | 35 | 157 |
| Mears30 | 28 | 48 | 146 |
| zkobes | 18 | 33 | 56 |
| OGV | 75 | 25 | 159 |
| TheLandsharks | 16 | 42 | 118 |
| anthonyrangel | 9 | 45 | 40 |
| Markgus13 | 32 | 28 | 106 |

For **each category/cell**, the observed process counts are `0 evaluable,
0 partial, N insufficient`; outcome counts independently have the same shape.
All counted rows have retained seasonal attribution. Exact intra-season tenure
boundaries and historical quality are not inferred from that attribution.

The active adapter now excludes unsuccessful claims and commissioner actions
from Waivers, retains per-roster add/drop identities, and preserves missing vs
zero FAAB. The canonical transaction stream contains 1,219 completed free-agent
records, 247 completed waivers, 172 failed waivers and three completed
commissioner actions. Two commissioner records belong to roster 3 in 2022 and
one to roster 5 in 2021, explaining the earlier activity-inventory differences
of 266 vs 264 and 147 vs 146. These are scope differences, not deleted evidence.
Draft selection identity is now retained for evaluability checks.

Seven focused adapter/coverage tests pass. No decision payload copies were
persisted by this diagnostic. Full quality panels, historical roster coverage,
production-equivalent checkpoint evaluation and second-league application remain
open; these counts do not justify final category or overall grades.

## Historical player lookup correction

A focused regression reproduced a production-shaped identity mismatch:
historical roster reconstruction requests bare numeric Sleeper player IDs,
while retained global observations use `player:<id>`. The checkpoint projection
now resolves that exact alias; pick namespaces remain separate. The flight read
contract changes so old cached projections cannot survive this correction.
Thirty-six checkpoint/Market tests pass after the regression first failed.

Drafting and Waiver adapters now attach decision-time canonical Market
checkpoint references, without copying provider payloads or using current
prices. Missing/invalid timestamps produce no references. Future checkpoints
are excluded. Seven adapter/coverage tests pass. Reference presence alone does
not confer process quality: alternatives, format and other required evidence
remain independently necessary. Final production-equivalent counts and quality
panels are still pending; prior local zero-coverage results are pre-correction
evidence and must not be represented as validating this changed candidate.

### Fact-model handoff regression

The active service constructs DraftFact/WaiverFact directly from adapter rows.
New selection, add/drop, FAAB and checkpoint-reference fields were previously
not accepted by those models, which would raise before evaluation. Explicit
fields now preserve those semantics through the handoff. Three focused
adapter/attribution tests pass, including constructing facts from actual adapter
output. This fixes connectivity, not Drafting/Waiver quality methodology; those
evaluators and the production-equivalent application remain incomplete.

### Scoped Drafting/Waiver evaluation integration

Active preparation now invokes `decision_evaluators` and retains derived
process/outcome results on typed facts. Draft Market-relative assessment requires
verified available-alternative evidence; later selections are not substituted.
Waiver add/drop comparison requires complete comparable pre-decision prices.
Historical roster alignment can independently support a limited assessment.
No composite quality scalar is invented. Outcome has independent time/reference
and scope requirements and never changes Process. Coverage counts use these
scoped results rather than requiring a scalar score to recognize partial work.

Ten focused evaluator/adapter/coverage tests pass. Production adapters currently
provide checkpoint comparisons, but do not yet connect reconstructed draft
alternatives, historical roster alignment or later outcomes to these evaluator
inputs. Those are outstanding integration work, not historical source absence.
Production-equivalent manager counts and full category calibration remain open.

### Independent later Market outcome connection

Drafting/Waiver preparation now resolves the first supported later observation
for acquired players independently from decision-time prices. It requires the
same Market context and normalization version, records actual elapsed days and
checkpoint references, and exposes only partial Market-development evidence.
It does not score NFL success, infer holding-period benefit, or penalize a recent
decision without an outcome. Ten focused tests pass, including a 334-day
observation whose positive Market change leaves Process insufficient unchanged.

Historical roster alignment, reconstructed available alternatives and realized
production/holding outcomes remain unconnected. The real production-equivalent
manager panel is still pending; this is not final FOIS calibration.

### Historical context connection

Drafting/Waiver preparation now requests the canonical reconstruction strictly
before the decision boundary, or before draft start when only that anchor is
known. It retains state identity, generation, counts and ownership precision,
not roster payloads. A partial anchor is not labeled exact; its existence does
not manufacture a positional-need or roster-fit quality conclusion.

The alternatives connector requires a referenced contemporaneous eligible pool
and removes earlier selections. Later successful players/selections alone cannot
define that pool. No retained real eligible-pool source has yet been connected;
the real alternative comparison remains unavailable until that evidence exists.
Six focused context/adapter/evaluator tests pass. Production-equivalent panel
execution remains outstanding. No final manager grades or release gates.

### Scoped coverage reporting and retained draft-pool check

Coverage availability now follows the active scoped process/outcome result,
not the presence of a legacy numeric score. Manager/season summaries retain
the evaluator's actual limitation reasons and independent confidence labels.
Thirteen focused context, adapter, evaluator and coverage tests pass.

A read-only production archive check found six draft metadata records across
2021–2025 (two in 2021, one in each subsequent season), with zero explicit
`eligible_pool`, `available_players` or `player_pool` fields. This proves only
absence of those explicit pools in the checked draft metadata, not absence of
every possible reconstruction source. No retrospective successful-player pool
has been substituted. Production data was not changed.
