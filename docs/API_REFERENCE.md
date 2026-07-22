# API Reference and Compatibility Policy

DTOS v1 freezes the following public HTTP contracts. Additive fields and endpoints are permitted in compatible minor releases. Removing or renaming fields, changing meanings, or tightening accepted input requires a major version or a documented deprecation period of at least one minor release.

All JSON errors use FastAPI's `{"detail": ...}` shape unless an endpoint documents a domain payload. Data-dependent routes may return 503 before initial data is available. Unknown entities return 404. Unhandled failures return 500 and include an `X-Request-ID` response header for log correlation.

| Method | Path | Inputs | Successful output |
|---|---|---|---|
| GET | `/health` | none | service, league, sync, and runtime health |
| GET | `/api/status` | none | version, sync state, and entity counts |
| GET | `/api/platform/health` | none | runtime, engines, providers, caches, timings, and configuration mode |
| GET | `/api/intelligence` | `front_office` integer, optional | unified recommendation, market summary, timings, cache state |
| GET | `/api/league` | `include_players` boolean | normalized league snapshot; player index is opt-in |
| GET | `/api/players` | none | canonical rostered-player IDs and dossier URLs |
| GET | `/api/front-offices` | `front_office` integer, optional | observable Front Office dossiers and relationships |
| GET | `/api/trades` | `front_office` integer, optional | contextual Trade Dossiers including market impact |
| POST | `/sync` | `Accept: application/json` for JSON | synchronization result or 303 redirect |

HTML routes are `/`, `/teams`, `/teams/{roster_id}`, `/front-offices`, `/trades`, `/matchups`, `/matchups/{matchup_id}`, `/picks`, `/transactions`, `/transactions/refresh`, `/players/{player_id}`, and `/settings`. Query parameters on Transactions provide filtering, sorting, pagination, and preserved state.

The generated schema at `/openapi.json` is authoritative for parameter types. New clients should ignore unknown additive fields. No v1.0.0 endpoint is deprecated.

As of v1.3.0, `/api/intelligence` additively exposes `player_values`, `roster`, and `league_intelligence` contracts, including provider status, freshness, projections, lineup value, quality-based team needs, surpluses, directions, compatibility, league economy, availability, and prioritized opportunities.
