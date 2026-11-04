# Batch 3 sparse trend correction — v1.17.1

Production exposed a missed active sparse Step 7 path: the reader discarded
comparison identity and the service compared arbitrary dated numbers. The raw
5237 provider price and legacy 752/757 blended prices are not comparable. Only
this concrete ledger entry is reopened, not the accepted model or player panel.

| Source semantic | Unit | Scope | Generation | Availability | Consumer meaning |
| --- | --- | --- | --- | --- | --- |
| Explicit sparse comparison metadata | Explicit scale | Same providers/format/context/asset | Method + normalization + Market generation | Unknown/incompatible means not comparable | Observed movement within proven boundaries |
| Legacy sparse observations | Unproven raw/blended scale | Global retained fact | Original version retained | Individual facts only | Never current fallback or fabricated movement |

The reader retains method, normalization, context and creation/knowledge time.
Comparison semantics require explicit agreeing producer metadata; an opaque
context hash and normalization `1.0` are not scale/format proof. No rows change.
Existing producers lacking metadata yield unavailable sparse comparisons, not
guessed trends. Separate provider-history trends already enforce their own
concept/scale/format/method boundary and remain separate.

The service excludes future knowledge from as-of reads and week labels from
observed instants, rejects conflicting same-time prices, and refuses unproven
current endpoints. Compatible evidence still produces legitimate trends.
Ranges/milestones/volatility cannot bridge boundaries. Private league liquidity
remains separate. Not-comparable results cannot enter movers. No new durable
storage, provider calls, or intelligence model is introduced.

Focused tests cover semantics, current endpoints, actual store/service reads,
unchanged historical rows, knowledge time, cache identity and Market notices.
Prior v1.17.0 model/panel evidence is reused. Canonical and required PR gates,
followed by production acceptance, remain necessary for this changed source.

Local release evidence: canonical validator passed 10/10 in 643.814 seconds,
including full regression (531.095 seconds), 252 routes with no duplicates,
234 OpenAPI paths, HTTP smoke and process cleanup. Focused runs passed 54 tests
and 24 tests respectively (overlapping sets). PR Linux/browser and production
acceptance remain pending; these are not claimed by local validation.

## Settled projection roadmap contract — not implemented here

For Batches 5–7, every Sleeper-labeled projection is the same canonical player/week
source value across surfaces. Totals/windows/lineup deltas may be derived, never
fabricated or extrapolated and labeled Sleeper. Missing is unavailable; verified
source zero remains zero. No multi-week feature is added in this correction.

Batch 3 acceptance remains pending. Batch 4 is not started.
