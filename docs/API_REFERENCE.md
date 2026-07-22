# API Reference and Compatibility Policy

DTOS v1 freezes the following public HTTP contracts. Additive fields and endpoints are permitted in compatible minor releases. Removing or renaming fields, changing meanings, or tightening accepted input requires a major version or a documented deprecation period of at least one minor release.

All JSON errors use FastAPI's `{"detail": ...}` shape unless an endpoint documents a domain payload. Data-dependent routes may return 503 before initial data is available. Unknown entities return 404. Unhandled failures return 500 and include an `X-Request-ID` response header for log correlation.

| Method | Path | Inputs | Successful output |
|---|---|---|---|
| GET | `/health` | none | service, league, sync, and runtime health |
| GET | `/api/status` | none | version, sync state, and entity counts |
| GET | `/api/platform/health` | none | runtime, engines, providers, caches, timings, and configuration mode |
| GET | `/api/intelligence` | `front_office` integer, optional | unified recommendation, market summary, timings, cache state |
| GET | `/api/data/providers` | none | provider catalog, capabilities, licensing, and health |
| GET | `/api/data/health` | none | provider, cache, snapshot, freshness, and failure health |
| GET | `/api/data/{category}/{key}` | category and data key | standardized source envelopes with provenance and quality |
| GET | `/api/data/consensus/{category}/{key}` | category and data key | consensus, confidence, variance, agreement, and missing sources |
| GET | `/api/data/history/{category}/{key}` | category and data key | timestamped attributed snapshots |
| GET | `/api/data/trend/{category}/{key}` | category and data key | 7-day through lifetime trend contract |
| POST | `/api/data/refresh/{category}` | optional `key` and `provider` | isolated on-demand refresh result |
| GET | `/api/league` | `include_players` boolean | normalized league snapshot; player index is opt-in |
| GET | `/api/players` | none | canonical rostered-player IDs and dossier URLs |
| GET | `/api/front-offices` | `front_office` integer, optional | observable Front Office dossiers and relationships |
| GET | `/api/trades` | `front_office` integer, optional | contextual Trade Dossiers including market impact |
| POST | `/sync` | `Accept: application/json` for JSON | synchronization result or 303 redirect |

HTML routes are `/`, `/teams`, `/teams/{roster_id}`, `/front-offices`, `/trades`, `/matchups`, `/matchups/{matchup_id}`, `/picks`, `/transactions`, `/transactions/refresh`, `/players/{player_id}`, and `/settings`. Query parameters on Transactions provide filtering, sorting, pagination, and preserved state.

The generated schema at `/openapi.json` is authoritative for parameter types. New clients should ignore unknown additive fields. No v1.0.0 endpoint is deprecated.

As of v1.4.0, provider-backed responses disclose source, timestamp, freshness, confidence, provider, cache state, retrieval mode, quality, and limitations. Existing `/api/intelligence` fields remain additive and compatible.
