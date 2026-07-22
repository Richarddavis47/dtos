# League Intelligence Engine v1

## Purpose

League Intelligence answers a league-level question: where are the explainable opportunities created by differences in roster quality, timelines, asset supply, market evidence, and observable Front Office behavior?

It evaluates the league as a connected market. It does not count players as a proxy for need, infer private manager intent, or collapse current and future value into a single unexplained score.

## Architecture

`src/core/league_intelligence/` is a registered Intelligence Orchestrator provider. Application services consume the orchestrator contract and never import League Intelligence directly.

The engine consumes existing outputs:

- Decision Engine for independent current and future outlooks and team windows.
- Player Value and Roster Intelligence for quality, projections, depth, scarcity, lineup leverage, liquidity, and construction metrics.
- Asset and Market Intelligence for intrinsic value, consensus, trends, coverage, and explicit unavailable states.
- Trade Intelligence for realistic packages, separate horizon impacts, negotiation structure, and evidence.
- Front Office Intelligence for observable activity, preferences, compatibility, and relationship history.

League Intelligence owns synthesis only. Source engines remain responsible for their calculations.

## Contracts

`LeagueIntelligenceReport` contains deterministic contracts for team needs, surpluses, directions, pairwise compatibility, asset availability, league economy, GM profiles, team reports, prioritized opportunities, trade recommendations, and dashboard summaries.

Needs are derived from league-relative room quality and strategic context. Surplus requires usable quality and liquidity; duplicate quantity alone is insufficient. Direction preserves current and future horizons. Compatibility combines complementary needs, timeline fit, and observed behavior without inferring personal relationships.

## Explainability

Every conclusion includes reasoning or evidence. Unsupported behavioral fields use explicit neutral states such as `Unavailable without offer events` or `Unestablished`. Market gaps remain neutral when no external consensus exists. Availability describes an evidence-based negotiation posture, not certainty about another manager's intentions.

## Commissioner Desk and API

The Commissioner Desk renders a compact League Opportunity Dashboard with best partners, top opportunities, and economy signals. `/api/intelligence` exposes the same report additively as `league_intelligence`.

## Extension points

Stable contracts allow future provider upgrades for historical transaction depth, live projections, richer pick markets, trade-block signals, offer-event behavior, and notification delivery without changing application-service boundaries.

## Limitations

- No probability model is introduced.
- No private behavior or personality is inferred.
- Negotiation response and counteroffer metrics require future observable offer-event data.
- External market provider gaps are disclosed rather than estimated.
- Recommendations remain advisory; the General Manager makes the final decision.
