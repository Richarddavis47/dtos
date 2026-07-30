# Front Office Intelligence System Foundation

## Purpose and mission

FOIS is DTOS's long-horizon framework for evaluating how effectively an owner
manages a dynasty franchise. Its mission is:

> A great dynasty GM consistently builds and maintains championship-caliber
> franchises over a long competitive horizon, adapts to changing circumstances,
> understands the league better than competitors, and makes bold but calculated
> decisions—even when short-term rebuilding is necessary to create long-term
> success.

FOIS is parallel to the existing DTOS intelligence stack in v1.6.0. It does not
replace team grading, roster intelligence, valuation, projections, historical
memory, or the competitive-window contract.

## Evaluation philosophy

Championships are the objective, but process explains results. Evaluation favors
sustained contention, adaptability, liquid assets, productive activity, league
knowledge, and competitive-cycle management. One or two deliberate down seasons
can be productive; prolonged rebuilding generally reduces the score.

Trade volume alone is not quality. A supported 10–20% premium can be strategically
positive when it materially improves championship outlook. FOIS separates a
decision's observable process from its eventual outcome and never fabricates
missing evidence.

## Versioned scoring contract

The initial configurable category weights are:

- Results: 35%
- Trading and Asset Management: 25%
- Roster Construction: 20%
- Drafting and Talent Evaluation: 20%

Configuration validation requires a 100% total. Model version `1.0` is independent
of the DTOS application version. The metric registry contains all named foundation
metrics, including future metrics that currently report an explicit unavailable
state.

The public contracts are `FrontOfficeIntelligenceScore`,
`FrontOfficeCategoryScore`, `FrontOfficeMetricScore`, `FrontOfficeEvidence`,
`FrontOfficeScoringConfiguration`, and `CrossCategoryTrait`.

Scores expose raw and normalized values, weights, contributions, letter grades,
sample size, confidence, completeness, explanations, evidence references,
warnings, status, model version, and a stable score key.

## Data, identity, and availability

The foundation accepts explicit, league-scoped season, trade, draft, roster, and
evidence facts. It evaluates at most ten completed seasons. League settings remain
attached for later league-relative normalization.

`active`, `provisional`, `insufficient_data`, `unavailable`, and `disabled` are
distinct states. Missing categories are excluded from aggregation and disclosed;
they never become zero. Confidence reflects sample depth, completeness reflects
supported coverage, and partial scores remain visibly provisional.

Owner and franchise identity are separate. A franchise has a stable league and
roster identity while its owner is optional, supporting future ownership changes
without rewriting franchise history.

## Runtime, persistence, and API boundaries

`DTOS_FOIS_ENABLED` defaults to false. Disabled mode performs no FOIS calculation
and existing DTOS behavior remains unchanged. `/api/fois/status` is memory-only.

When enabled, explicitly requested calculation runs in a worker thread over cached
application data and optional `fois_history`; it performs no provider I/O. SQLite
persistence can be overridden with `DTOS_FOIS_DB_FILE`. Keys are deterministic
across league, franchise, window, and model version. Unchanged fingerprints make
writes idempotent.

The feature-flagged API includes status, model, league scores, franchise scores,
categories, metrics, completeness, and an explicit calculate endpoint under
`/api/fois`. All except status return 404 while disabled. No FOIS page or startup
job is introduced in this release.

## Recalculation, limitations, and future phases

Recalculation is explicit. Future triggers may follow historical reconciliation,
transaction import, draft completion, or model-version changes. Existing snapshots
remain model-versioned.

Many advanced metrics remain provisional until historical valuation, lineup,
transaction, probability, and draft evidence is sufficient. This release
establishes the framework; it does not claim every registry metric is scored.

Planned phases cover results and competitive cycles; historical trade outcomes,
liquidity, timing, and relationship capital; draft-slot expectation and talent
evaluation; multi-year roster construction; and a final FOIS UI with evidence
timelines, comparisons, trends, and franchise-versus-owner views.

## Results engine (v1.6.1)

Results is the first production category. Its 35% top-level weight is unchanged.
The category consumes canonical `season_standing`, `playoff_result`, `matchup`,
`league_season`, and `franchise_identity` records from Historical Memory.
Provider access is prohibited.

Production metrics cover championships, championship-game and Final Four
appearances, playoffs and streaks, winning seasons and streaks, observed
regular-season matchup win rate, league-size-normalized average/best/worst
finishes, title conversion, playoff advancement, contention-window length,
reload efficiency, rebuild duration, and long-term competitive consistency.
Championships carry the highest individual achievement weight but only 10% of
the Results category, preventing a single outcome from overwhelming sustained
performance.

`CompetitiveCycleAnalyzer` classifies each completed season as rebuild,
ascending, contender, elite contender, decline, reload, or transition. Adjacent
seasons form rebuild, contention, or transition cycles with stable IDs, duration,
peak finish and years, championships, playoff appearances, rebuild length, and
reload time. Explanations identify why each state and cycle was assigned.

The engine exposes full history (capped at ten completed seasons), trailing ten,
trailing five, trailing three, and current-cycle windows when sufficient seasons
exist. One- and two-year rebuilds remain inside the productive-cycle threshold;
longer rebuilds receive progressively lower rebuild-duration scores. Isolated
poor finishes have limited effect, while repeated bottom-quartile finishes are
visible.

Ownership transitions and incomplete seasons reduce confidence. Missing seasons
reduce completeness. Neither becomes a zero-valued outcome. Timeline, cycles,
rebuild summary, strengths, weaknesses, and narrative explanation are persisted
with the Results category and returned by:

`GET /api/fois/leagues/{league_id}/franchises/{franchise_id}/results`

Known limitations: historical roster-age, draft-capital, veteran-concentration,
and championship-probability signals are not yet used for cycle classification.
Observed standings, matchups, and postseason placements are authoritative in this
release. Those additional signals can refine states in later versions without
changing the cycle contract.
