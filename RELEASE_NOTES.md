# DTOS v0.9.8 - Intelligence Integration Platform v1

DTOS v0.9.8 unifies Decision Engine, Asset Intelligence, Trade Intelligence, and Front Office Intelligence behind one explainable Front Office Operating System.

## Highlights

- Builds one shared context for league, roster, picks, settings, opponents, market, Front Offices, cached data, and user preferences.
- Registers intelligence providers behind a central orchestrator and timed pipeline.
- Produces one final recommendation with current and future outlooks, supporting evidence, risks, counterarguments, assumptions, confidence, and change conditions.
- Resolves disagreement conservatively rather than exposing contradictory engine recommendations.
- Reuses shared TTL cache entries for decisions, asset portfolios, Front Office profiles, trade evaluations, and final results.
- Invalidates intelligence snapshots after successful Sleeper or transaction refresh while preserving cached fallback behavior.
- Adds runtime engine, Sleeper, cache, database, orchestration, and latency health through `/api/platform/health`.
- Adds the backward-compatible `/api/intelligence` contract and integrates unified recommendations into existing application surfaces.
- Promotes validation into `src/platform/validation/` with independently executable Windows-safe release tools.

## Metadata

- Application: DTOS
- Version: 0.9.8
- Build: 908
- Codename: Intelligence Integration Platform v1

## Intentional boundaries

- Existing engine report and API contracts remain available for detailed domain views.
- V1 does not add a new fantasy-football intelligence domain or change league business rules.
- Market certainty remains limited until a validated external market provider exists.
- Historical accuracy remains disclosed as unavailable until persistent outcome snapshots exist.
- The orchestrator coordinates deterministic providers; it does not use machine learning or opaque scoring.
