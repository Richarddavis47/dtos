# Capital / strategy local checkpoint

## Current-state map before implementation

Compared audit `23870d1` with fetched `origin/main` `7e6bd6e` on 2026-10-05.
The two later commits concern portable validation and private operations inspection;
they do not fix capital reconciliation. Work is isolated on
`fix/capital-strategy-reconciliation`; no release metadata, storage or deployment work.

Active path: Trade routes -> `services.trade_intelligence.evaluate_trade_request`
-> ownership validation and exact `TradeProposal` -> canonical `market_balance`
and `evaluate_horizon_impact` (generation-pinned optimal legal lineups for both
teams) -> `bilateral.evaluate_bilateral` prepared-evidence branch ->
`strategy_dimensions.reconcile_result` -> recommendation -> evidence confidence
and independent counterparty plausibility -> workflow eligibility -> filtering.

The unconditional `elif capital_changed` precedes every positive branch and
sets `FUTURE_CAPITAL_TRADEOFF_UNRESOLVED`, although pick identity, price and lineup
evidence may all exist. Capital records describe movement only; no strategy
policy consumes them. Explicit manager strategy is not forwarded. Counterparty
plausibility accepts any positive horizon without checking material loss elsewhere.

Create Trade displays an unavailable recommendation. Shop Asset / Draft Capital,
Trade For, Recommended Trades, adjustments and alternatives all reuse this
evaluator, so qualifying constructions are filtered out. Targeted search,
Recommended and adjustment paths may also include FAIR / OPTIONAL through
`_trade_for_eligible`. Recommended discovery requires two player slot opportunities,
so it can miss pure player/pick theses before evaluation. The audit's 36 live
rejections are historical observations, not a new live count.

Already correct: neutral canonical prices, no pick weekly projection, generation
compatibility, legal lineup optimization, capacity disclosures, soft FOIS context,
and exact pick records. Preserve these contracts.

## Policy to implement

Separate Market, legal production, draft capital, manager strategy and counterparty
evidence. Explicit strategy overrides a generation-matched competitive-window
default. Missing strategy/window remains unresolved for a strategic sacrifice.
Thresholds are bounded decision rules, not price adjustments or outcome forecasts.
Count each supported projected week once; never sum overlapping horizons.

Hard ownership/identity failures reject. Missing required evidence or unresolved
capacity blocks eligibility. Current production loss and capital expenditure
remain legal strategic costs. Require meaningful compensation and independently
assess the other manager; no acceptance probability and no FOIS veto.

Implementation results and validation are recorded below after checks finish.

## Implemented model

`capital_assessment` consumes canonical acquisition prices without modifying them.
It separately reports exact received/sent picks, received/sent/net capital value,
unique-week legal production, strategy source, bounded decision thresholds and
the recommendation rationale. No pick weekly projection, future utility scalar,
weighted strategy score or acceptance probability is introduced.

Explicit request `strategy` (WIN NOW / RETOOL / REBUILD, including underscore
aliases) takes precedence over synchronized team intent and a generation-matched
competitive window. Search, repair and alternatives carry request-local intent;
Shop ordering preferences and Recommended filters still do not alter evaluation.
The existing workspace has one strategy selector. No persistent preference or
website redesign is included.

Material production means a unique-week mean improvement of at least one point
or 3% of the pre-trade optimal lineup, whichever is greater. Each weekly delta
is counted once; overlapping current / Next-N / ROS / playoff totals are never
added together. Individual horizons still expose losses and prevent a win-now
upgrade claim when a supported horizon declines.

Meaningful net capital means at least 100 canonical price units or 10% of the
outgoing package, whichever is greater. REBUILD can intentionally sacrifice
production for that gain with at least 80% Market return. WIN NOW can spend
capital for material legal production with at least 65% return. RETOOL requires
at least 85% return and can pursue a production gain or capital gain with
preserved production; a modest production sacrifice at balanced terms can be
FAIR / OPTIONAL. These are inspectable policy bounds, not recalibrated prices
or claims that current points and capital are equivalent. More than 50% Market
loss rejects a capital construction; poor packages remain NOT WORTH IT.

All five recommendation labels are supported. Pure pick parity can be FAIR /
OPTIONAL for the user, but parity alone supplies no credible counterparty benefit
and is not generated as an opportunity. Missing capital price/identity,
incomplete projection coverage, absent strategy for a sacrifice, or unresolved
capacity keeps the assessment unavailable and blocks eligibility. Unknown pick
range does not fabricate a premium outcome or automatically veto known priced
capital; its range and confidence remain disclosed.

Hard ownership, duplicate and inconsistent exact-pick identity/owner failures
reject before recommendation. Capacity still reports REQUIRES ROSTER RESOLUTION;
neither cuts nor capacity exceptions are inferred. A legal strategic cost is
recorded in production, capital and explanation instead of becoming invalidity.
An unsupported playoff calendar now remains incomplete evidence rather than
raising during horizon comparison.

Each counterparty gets its own strategy, Market-return, capital and lineup
assessment. Large production losses cannot be erased by a tiny positive horizon;
severe Market losses cannot be rescued by weak signals. FOIS history remains
supporting context with no automatic veto. Positive user recommendations remain
distinct from generated eligibility and do not promise manager acceptance.

Recommended discovery adds bounded player/capital theses from observed player
slot opportunities (six theses total, two per counterparty). Targeted construction
permits capital in its one-for-one shape while preserving six candidate shapes.
No exhaustive Trade Center search or independent calculator is included.

## Acceptance results

The fixtures use current normalized provider quotes and a real prepared canonical
projection generation with optimal legal lineups. All six have zero Market
difference, WORTH PURSUING, PLAUSIBLE counterparty rationale and generated
eligibility. Production below is a mean over unique supported weeks.

| Contract | Manager strategy | Production change | Net draft capital |
| --- | --- | ---: | ---: |
| A: player -> pick | REBUILD | -4 | +250 |
| B: pick -> player | WIN NOW | +2 | -250 |
| C: player + pick -> player | WIN NOW | +2 | -100 |
| D: player -> player + pick | REBUILD | -2 | +100 |
| E: pick package -> player | WIN NOW | +2 | -350 |
| F: player package -> pick | REBUILD | -4 | +250 |

RETOOL also qualifies for the balanced mixed C exchange. A reserve-player sale
with preserved supported lineup/reserve capacity receives SMASH ACCEPT. Equal
pick capital receives FAIR / OPTIONAL; strategy-inappropriate capital expenditure
receives NOT WORTH IT. An elite 900-price asset for a fourth-round 20-price pick
receives REJECT, and its reverse has LOW counterparty plausibility. Missing price,
identity, strategy or compatible projection evidence remains unavailable. A 0.01
positive week cannot mask three -10-point counterparty weeks.

Real generated Shop Asset / Draft Capital, Shop Pick, Trade For, Recommended and
adjustment paths return qualified capital offers; their evaluations equal direct
Create Trade evaluation under the same intent and evidence. API and browser
fixtures verify strategy selection changes judgment without changing Market or
projection truth. Mobile (390px) and desktop (1280px) journeys use the real API.

The acquired pick `2028-R1-4` retains year 2028, round 1, original franchise 4,
current owner 2, exact canonical ID, supported range/confidence where present,
and UNKNOWN/LOW when no range is established. Generic provider round quotes do
not replace that franchise-specific asset identity. Conflicting owner or identity
is rejected.

## Validation and checkpoint outcome

- Final focused capital / strategy / workflow / identity / legal-lineup / API suite:
  **171 tests passed** in 8.425 seconds. Includes all sixteen new capital tests
  and actual mobile/desktop browser interactions.
- Canonical `.venv/bin/python -m tools.validation.validate_release`:
  **all 10 gates passed** in 230.468 seconds on the final source.
- Full regression suite: 2,409 discovered cases; canonical regression gate passed.
- Authoritative repository-wide `.venv/bin/python -m ruff check .`: zero findings.
- `.venv/bin/python -m compileall -q .`, dependency integrity, working-tree and
  staged `git diff --check`: passed.
- Route/OpenAPI validation: 257 method registrations, 236 OpenAPI paths,
  required routes present, no duplicates.
- HTTP smoke: 114 requests, including 22 Trade requests; startup, graceful
  shutdown, tracked cleanup and final process cleanup passed.
- Validation used an isolated temporary cache with the existing 250-player
  sanitized fixture generator and separate temporary runtime databases. It did
  not change storage code, production state, release metadata or source fixtures.

Initial checks caught application imports crossing the core facade; those were
corrected through public intelligence exports. An initial cold-cache HTTP run
returned 503 before first Sleeper sync. The documented disposable cache setup
resolved the test precondition. Its offline provider URL conflicted with two
onboarding mocks during a combined run; the final canonical run retained the
normal provider URL and passed. No validation gate was suppressed or weakened.

Detailed local logs: `/tmp/capital-focused-final.log`,
`/tmp/capital-browser.log`, `/tmp/capital-http-validation.log`, and
`/tmp/capital-final-validation.log` (final complete passing run).

**P1 capital-trade evaluator blocker: locally resolved.** Checkpoint branch:
`fix/capital-strategy-reconciliation`, based on `7e6bd6e`. No push, PR, merge,
release tag or production deployment was performed. Local checkpoint commit is
reported in the task response.

## Files changed

- `src/core/trade_intelligence/capital_assessment.py`: capital evidence and bounded strategy rules.
- `src/core/trade_intelligence/strategy_dimensions.py`: bilateral reconciliation, counterparty materiality, recommendation and eligibility.
- `src/core/trade_intelligence/bilateral.py`: exact pick consistency and strategy inputs.
- `src/core/trade_intelligence/horizon_impact.py`: honest unavailable-calendar handling.
- `src/core/trade_intelligence/engine/trade_generator.py`: capital-capable one-for-one construction in the existing budget.
- `src/core/intelligence/__init__.py`: public facade exports; application/core boundary preserved.
- `services/trade_intelligence.py`: request-local strategy propagation and exact pick presentation.
- `services/recommended_trade_search.py`: bounded capital opportunity discovery.
- `services/trade_explanation.py`: separate capital evidence, strategy rationale and costs.
- `components/trade_workspace.py`: one strategy selector in the existing workspace.
- `static/js/trade_workspace.js`: strategy request field and stale-result invalidation.
- `tests/test_capital_strategy_reconciliation.py`: acceptance, legal impact, strategy, Market invariance, identity, missing evidence, workflow, API and browser contracts.
- `tests/test_batch5_trade_strategy.py`: the old unresolved poor-return fixture now expects explicit rejection while preserving unavailable long-term utility.
- `docs/CAPITAL_STRATEGY_CHECKPOINT.md`: current-state map, policy, fixtures and local checkpoint report.

## Remaining limits and next release step

This is a bounded capital-policy correction, not empirical acceptance calibration
or a dynasty forecast. Longevity, class quality, liquidity, cut choice and missing
FOIS context remain explicit limitations. Discovery is not exhaustive; no new live
league candidate count or production acceptance claim is made. The independent
Trade Calculator remains a separate workstream using unchanged canonical values.

Next release step: review this local feature-branch checkpoint and its validation
results, choose the release version, rebase/compare against then-current main,
update centralized metadata and release documentation, and run the canonical
validator before opening the release PR. Merge and deployment require a separate
release instruction; neither is part of this checkpoint.
