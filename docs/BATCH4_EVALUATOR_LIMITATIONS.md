# Batch 4 evaluator limitations — focused follow-up

## Drafting source-time trace

All 370 retained selections lack a pick occurrence timestamp. Top-level fields
include draft identity, slot, selector, player and round. Metadata contains
player identity/status/news fields, not selection time. `news_updated` and
`team_changed_at` are not draft decision timestamps. Draft records retain
millisecond start/end lifecycle bounds. Those are not individual pick times.
Canonical draft records correctly leave `occurred_at` absent, and the FOIS
adapter passes that absence through. The evaluator cannot run an exact as-of
Market lookup. This is not a timezone/epoch conversion defect or a dropped
existing pick timestamp.

Concrete correction: missing time now emits `DECISION_TIME_UNAVAILABLE` and
`MARKET_LOOKUP_UNAVAILABLE_TIME_BOUNDARY`, rather than asserting an invalid
timestamp and absent historical Market evidence. Invalid supplied times still
emit `INVALID_TIME_BOUNDARY`. No start/end/news timestamp substitutes for a pick.

Focused replay verified all five local archive semantic checksums against the
retained production manifest before invoking the candidate missing-time branch.
Insufficient counts remain: Richard 38, danreilley 34, davefedex 42,
garrettadame36 35, Mears30 48, zkobes 33, OGV 25, TheLandsharks 42,
anthonyrangel 45, Markgus13 28. No coverage was recovered and no quality changed.
No additional production export occurred. This replay does not claim to test
new interval-based assessments; none were implemented.

## Richard — Waiver limitations

From the retained production-equivalent manager/season summaries (overlapping
reasons): 101 lack contemporaneous Market; 161 lack complete comparable add/drop
Market; 142 have unavailable/not-applicable FAAB; 168 have no supported roster-fit
conclusion. There are no emitted missing-time reasons. All 168 have reconstructed
roster references, so missing roster-fit conclusions are an evaluator limitation,
not missing roster anchors. The aggregate evidence cannot separately resolve
add/drop linkage versus quote absence for all 161; do not claim it can.

Outcome is insufficient for 158 actions. The current summary does not subdivide
missing later quote, incompatible concept, and lack of baseline; it is not proof
of poor outcomes. Seven process and ten outcome partial assessments remain.
Known FAAB remains 26, including 17 explicit zeros; 142 stays unavailable.
A focused regression proves unknown FAAB alone does not invalidate a supported
contemporaneous add/drop exchange assessment.

## Richard — Trading limitations

Retained counts stay 4 evaluable / 73 partial / 5 insufficient. Overlapping
requirements report incomplete Market for 72, incomplete historical context for
58, and missing package identity for one. These aggregate reasons do not prove
individual player/pick/window subdimension counts; that distinction must not be
invented from totals. All 82 outcomes remain insufficient in the retained run.
Partial is not a quality grade and is not automatically a defect.

## Roster and calibration boundary

Richard's 181 references and complete/partial ownership precision remain
unchanged. A reference count is neither roster construction quality nor a fit
conclusion. Final quality calibration is unfinished; Results and activity cannot
fill those gaps. Draft lifecycle intervals might support narrower future
assessments, but this follow-up has not silently treated them as exact times.

Fifteen focused tests passed, including same-day before/after evidence, timezone
normalization, missing versus invalid time, missing Market, and unknown FAAB.
No comprehensive gates, storage changes or Batch 5 work.
