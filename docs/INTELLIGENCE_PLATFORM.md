# Intelligence Integration Platform v1

## Purpose

DTOS v0.9.8 turned the Decision, Asset, Trade, and Front Office engines into providers behind one Front Office Operating System. DTOS v0.9.9 adds Market Intelligence through the same boundary. Application services ask the orchestrator for an analysis; they do not independently assemble competing recommendations.

The platform preserves every v0.9.7 engine and API contract. Provider adapters translate the shared context into each stable engine contract while the orchestrator owns execution order, caching, evidence aggregation, conflict resolution, confidence, timing, and the final recommendation.

## System architecture

```mermaid
flowchart TD
    Request[Application or API request] --> Context[Shared IntelligenceContext]
    Context --> Cache[TTL intelligence cache]
    Cache --> Registry[Intelligence provider registry]
    Registry --> Decision[Decision Engine provider]
    Decision --> Asset[Asset Intelligence provider]
    Asset --> FrontOffice[Front Office Intelligence provider]
    FrontOffice --> Trade[Trade Intelligence provider]
    Trade --> Market[Market Intelligence provider]
    Market --> Evidence[Unified evidence aggregation]
    Evidence --> Resolver[Conflict resolver]
    Resolver --> Confidence[Shared confidence model]
    Confidence --> Result[One IntelligenceResult and recommendation]
    Result --> UI[Commissioner Desk, Team HQ, Trade and Front Office views]
    Result --> API[/api/intelligence]
```

## Module responsibilities

- `context.py` builds one immutable league, roster, settings, opponents, market, Front Office, cache-data, and preference context.
- `registry.py` registers providers by capability so future engines can be added without hard-coded application routing.
- `pipeline.py` instruments every provider and total orchestration runtime.
- `cache.py` supplies thread-safe TTL entries, prefix invalidation, refresh behavior, hit/miss metrics, and health.
- `evidence.py` normalizes engine evidence into one traceable contract and removes duplicate observations.
- `confidence.py` combines data completeness, evidence agreement, market certainty, sample size, and missing information.
- `recommendations.py` resolves disagreement and produces one answer with why, why not, assumptions, evidence, counterarguments, and change conditions.
- `orchestrator.py` owns the complete request and recommendation lifecycle.

## Request and recommendation lifecycle

1. Select a valid Active Front Office and build the shared snapshot key.
2. Return the cached result when the same successful Sleeper snapshot is still valid.
3. Evaluate every team once through the Decision provider.
4. Evaluate the active roster's player and pick portfolios through Asset Intelligence.
5. Build the league Front Office model from the shared decisions.
6. Generate Trade Intelligence with those same decisions and Front Office profiles.
7. Evaluate traceable market providers, trends, value gaps, and trade impacts without replacing intrinsic values.
8. Normalize and deduplicate evidence from all five providers.
9. Resolve conflicts conservatively. Low acceptance or negative expected value produces a wait recommendation rather than contradictory advice.
10. Calculate one confidence score and retain each disclosed input.
11. Return the unified result and runtime metrics.

Sleeper and transaction refreshes invalidate the shared snapshot namespace. If Sleeper is unavailable, the existing cache file remains the source of the shared context.

## Evidence lifecycle

Every evidence item retains its provider, factor, observed value, explanation, direction, and impact. The final recommendation exposes supporting factors and counterarguments separately. Missing market or historical information reduces confidence and appears in assumptions; it is never filled with invented data.

## Runtime health and performance

`/api/platform/health` reports each registered provider, Sleeper connection or cached-fallback state, cache entries/hits/misses/hit rate/invalidations/TTL, database status, orchestration count, provider timings, and the latest error. `/api/intelligence` returns the final recommendation, timing metrics, and cache-hit state.

The cache stores league decisions, asset portfolios, Front Office profiles, trade evaluations, and the final result under one snapshot namespace. Repeated views for the same Front Office avoid duplicate engine work. Tests require cached orchestration to be faster than the initial run.

## Validation platform

`src/platform/validation/` is the supported application-level import surface for route validation, server lifecycle management, and real-process detection. The executable release tools remain under `tools/validation/` and consume that platform API:

- `validate_routes.py` verifies canonical routes, duplicates, required endpoints, and OpenAPI.
- `run_http_validation.py` owns a dynamically allocated port and tracked Uvicorn PID in a `finally` block.
- `smoke_http.py` validates major pages, all Team HQ and Front Office contexts, Trade Intelligence, player dossiers, and expected 404 behavior.
- `process_check.py` detects only genuine Python/Uvicorn DTOS hosts and cannot self-match a shell query.

## Developer onboarding

Use `intelligence_orchestrator.analyze(data, roster_id)` for a complete intelligence request. Register future providers through `IntelligenceRegistry`; do not call them from presentation code or add a second final-recommendation pipeline. Preserve the stable provider outputs and normalize new evidence at the orchestration boundary.

Run the release checks documented in `AGENTS.md`. The standalone validation entry points are Windows-safe and independently executable from the repository root.

## Extension points and boundaries

Future intelligence domains register as providers and contribute evidence; they do not create competing application recommendations. Persistent caches, historical accuracy, external market feeds, and database health may replace neutral placeholders without changing the public result. V1 introduces no new fantasy-football domain, league rule, or opaque score.
