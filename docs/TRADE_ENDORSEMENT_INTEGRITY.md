# Trade recommendation integrity — v1.21.64 / build 2164

Baseline: v1.21.63, `ede8310018ae3c6b1e5002a0bdf1446dbdc82864`.
Main and production matched before implementation. This release addresses only
recommendation promotion, not the separate historical reconstruction audit.

## Reproduction and root cause

Actual canonical Market inputs, Sleeper-shaped projection publication, legal
lineups and the evaluator reproduce 995 sent, 75 received, +0.01 active-team
weekly lineup points with explicit REBUILD. The shared evaluator returns WORTH
PURSUING and generated eligibility; actual Trade For HTTP discovery publishes
the construction. This is controlled evidence, not a claim about a live roster.

The player-only positive-horizon branch admitted any positive delta when complete
coverage and unchanged reserve capacity were present. It ran before the later
material-production branch and omitted the severe-Market-loss check already used
by capital assessment and counterparty plausibility. Discovery correctly reused
that shared judgment, carrying the defect into suggestions.

## Narrow shared correction

- Reuse the existing severe-loss ratio (return below 0.50) for complete,
  player-only evaluations as well as capital and counterparty checks. It remains
  separate from legality; a legal but severely unfavorable offer is REJECT.
- Require the existing production materiality flag for positive-horizon
  endorsement: unique weekly gains average at least max(1 point, 3% of pre-trade
  optimal lineup points). No new projection, price, weighting or threshold.
- A supported Market overpay without material production or the existing
  qualifying depth benefit is NOT WORTH IT. Unknown required evidence remains
  unavailable, rather than a supported zero or invented upside.
- Keep supported positive overpays, including the existing 200-to-100/5-point
  positive control at the accepted severe-loss boundary. Capital-specific
  WIN NOW/RETOOL/REBUILD rules remain unchanged. CONTEND is exercised through
  the existing canonical Contender window resolving to WIN NOW, not a new alias.
- Give the new rejection reasons readable explanations; materiality also governs
  the existing best-for competitive-window description. No UI redesign.
- Include the shared evaluation policy version in assessment/Home reuse identity.
  Existing old assessments become retained through the established compatibility
  contract; an unchanged price/projection publication cannot validate an old
  favorable endorsement under the corrected policy. No saved payload is rewritten.

Trade For, Shop Asset, Recommended, Builder and Adjust all consume the same
`evaluate_trade_request -> evaluate_bilateral -> reconcile_result` conclusion.
Search classification, counterparty plausibility and recommendation eligibility
remain distinct. Calculator Market balancing is not a favorable endorsement.

## Evidence and acceptance

`tests/test_trade_endorsement_integrity.py` covers the exact negative control,
explicit strategies and canonical Contender inference, materiality boundaries,
trivial/zero/negative/unavailable gains, player-plus-exact-pick consideration,
missing Market versus zero, the complementary 400-to-400/+4/+8 trade, material
win-now overpay, source preservation, discovery/Adjust consistency and actual
authenticated HTTP/released-client phone views. Existing strategy assertions
and accepted overpay controls are preserved. Product-browser CI includes it.

No store, schema, cache, source record, recommendation history or paid
infrastructure is introduced. Prices, raw Sleeper projections, source clocks,
legal lineup rules, account authority, exact ownership/protections and retained
FOIS grades are unchanged. No production user-state mutation or regeneration is
part of acceptance. Resource limits remain 2 GiB and 500 ms liveness.

Scout must independently repeat the source/HTTP negative case, verify no
favorable discovery publication, and review positive overpay and complementary
trades. Author-run fixtures and responsive Chromium are not independent Scout,
physical iPhone/Safari, human screen-reader or unfamiliar-user acceptance.
