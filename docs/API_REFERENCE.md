# API Reference and Compatibility Policy

DTOS v1 freezes the following public HTTP contracts. Additive fields and endpoints are permitted in compatible minor releases. Removing or renaming fields, changing meanings, or tightening accepted input requires a major version or a documented deprecation period of at least one minor release.

All JSON errors use FastAPI's `{"detail": ...}` shape unless an endpoint documents a domain payload. Data-dependent routes may return 503 before initial data is available. Unknown entities return 404. Unhandled failures return 500 and include an `X-Request-ID` response header for log correlation.

## Public crawl API

All crawl endpoints are unauthenticated, read-only JSON views over the most recently synchronized DTOS cache. They never initiate synchronization.

- `GET /api/crawl` — discovery index, league support, sync state, public pages, endpoints, and cache metadata.
- `GET /api/crawl/snapshot?league=<league_id>` — consolidated public league snapshot.
- `GET /api/crawl/teams?league=<league_id>&limit=100&offset=0&team=<roster_id>`
- `GET /api/crawl/front-offices?league=<league_id>`
- `GET /api/crawl/trades?league=<league_id>`
- `GET /api/crawl/transactions?league=<league_id>&limit=100&offset=0&since=<ISO-8601>&team=<roster_id>`
- `GET /api/crawl/matchups?league=<league_id>`
- `GET /api/crawl/picks?league=<league_id>&season=<year>&team=<roster_id>`
- `GET /api/crawl/standings?league=<league_id>`

Invalid league identifiers return a stable JSON `404`. Responses include schema, application version, generation time, league ID, and cache metadata. `GET /robots.txt` and `GET /sitemap.xml` provide crawler discovery.

| Method | Path | Inputs | Successful output |
|---|---|---|---|
| GET | `/health` | none | backward-compatible readiness, league, sync, and runtime health |
| GET | `/health/live` | none | lightweight process liveness |
| GET | `/health/ready` | none | cached/synchronized data readiness; HTTP 503 until ready |
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
| GET | `/api/players/{player_id}/intelligence` | canonical player ID | normalized player, provider values, availability, consensus, trend, freshness, confidence, and unavailable reasons |
| GET | `/api/valuation/providers` | none | versioned provider registry, compliance, freshness, coverage, reliability, dependencies, and safe evidence summary |
| GET | `/api/valuation/providers/{provider_id}` | provider ID | public-safe provider contract |
| GET | `/api/valuation/providers/{provider_id}/status` | provider ID | availability and explanatory state |
| GET | `/api/valuation/providers/{provider_id}/coverage` | provider ID | record, coverage, identity-match, and unmatched counts |
| GET | `/api/valuation/providers/{provider_id}/reliability` | provider ID | dynamic overall and category reliability dimensions |
| GET | `/api/valuation/providers/{provider_id}/history` | provider ID | versioned reliability observations |
| GET | `/api/valuation/provider-consensus` | none | family-aware weighted consensus summary and audit samples |
| GET | `/api/valuation/provider-agreement` | none | disagreement and provider dependency evidence |
| GET | `/api/valuation/observed-market` | none | aggregated, quality-filtered Sleeper trade evidence |
| GET | `/api/valuation/league-market` | none | active-league isolated market context; no private raw records |
| GET | `/api/front-offices` | `front_office` integer, optional | observable Front Office dossiers and relationships |
| GET | `/api/trades` | `front_office` integer, optional | contextual Trade Dossiers including market impact |
| POST | `/sync` | `Accept: application/json` for JSON | synchronization result or 303 redirect |

HTML routes are `/`, `/teams`, `/teams/{roster_id}`, `/front-offices`, `/trades`, `/matchups`, `/matchups/{matchup_id}`, `/picks`, `/transactions`, `/transactions/refresh`, `/players/{player_id}`, and `/settings`. Query parameters on Transactions provide filtering, sorting, pagination, and preserved state.

The generated schema at `/openapi.json` is authoritative for parameter types. New clients should ignore unknown additive fields. No v1.0.0 endpoint is deprecated.

As of v1.4.1, player/provider responses additionally disclose canonical identity reconciliation, normalized contracts, availability state, reliability, and field-specific unavailable reasons. Existing fields remain additive and compatible.
# Historical crawl API

DTOS v1.5.0 advertises paginated historical endpoints from `/api/crawl`. Routes under `/api/crawl/history` cover seasons, matchups, standings, playoffs, transactions, trades, drafts, players, player weekly/usage/value history, Team Intelligence history, import status, and data quality.

Common filters are `league`, `season`, `week`, `franchise`, `player`, `limit`, and `offset`. Defaults are bounded and all records include schema version and provenance. Unsupported usage returns an explicit `provider_not_supported` state.
- `GET /api/crawl/history/completeness` — per-season supported-category coverage.
- `GET /api/crawl/history/providers` — provider capabilities, attribution, and limits.
- `GET /api/crawl/history/player/{player_id}/stats` — versioned weekly raw statistics.
- `GET /api/crawl/history/player/{player_id}/fantasy` — league-specific scoring.
- `GET /api/crawl/history/player/{player_id}/availability` — observed status or an explicit unsupported reason.
- `GET /api/crawl/history/player/{player_id}/aggregates` — deterministic season aggregates.
- `GET /api/crawl/history/player/{player_id}/signals` — explainable versioned signals.
- `GET /api/crawl/history/player/{player_id}/data-quality` — provenance and quality findings.
# AI Inspection System

DINS exposes cached, read-only structural page descriptions:

- `GET /api/inspect`
- `GET /api/inspect/pages`
- `GET /api/inspect/team/{roster_id}`
- `GET /api/inspect/player/{player_id}`
- `GET /api/inspect/front-office/{roster_id}`
- `GET /api/inspect/trades`

These routes perform no synchronization or intelligence calculation. See
`docs/DINS_INSPECTION.md` for the schema and guarantees.
# DINS 2.0 inspection API

`/api/inspect` discovers all public inspection capabilities. Use `/api/inspect/site-map`
for the canonical page inventory, `/api/inspect/visual/pages/{page_id}/{viewport}` for
rendered evidence, `/api/inspect/health` for bundle readiness, and
`/api/inspect/releases/current` for the release manifest. Supported viewports are
`desktop`, `tablet`, and `mobile`. Artifact URLs are absolute and never expose local paths.
# Brain, valuation, evidence intelligence, and calibration API (v1.7.5)

The canonical intelligence contract is `/api/brain`. Asset, health, migration, and timeline resources live beneath that path. Existing `/api/valuation` resources are compatibility contracts and remain supported.

`/api/league` includes a compact Brain summary, safety state, diagnostic counts, and canonical endpoint links. Full-universe Brain assets and timelines are intentionally served only by the dedicated Brain APIs so generic league serialization remains bounded.

The `/api/valuation` family exposes only the current cached production universe. Asset lists are paginated; `/export.json` and `/export.csv` provide complete deterministic exports. Every payload includes explicit freshness and source metadata. See [VALUATION.md](VALUATION.md) for identity and layer contracts.

Evidence Intelligence endpoints are `/api/valuation/evidence`, `/api/valuation/evidence/{asset_id}`, `/api/valuation/confidence`, `/api/valuation/coverage`, `/api/valuation/agreement`, `/api/valuation/explanation`, `/api/valuation/timeline`, and `/api/valuation/diagnostics`. Every response includes application version, build, commit, intelligence schema version, generation timestamp, availability, and canonical asset count. Asset-specific routes use canonical IDs such as `player:10213` and return HTTP 404 for missing identities.

Automated calibration is exposed through `/api/valuation/calibration`, `/api/valuation/calibration/categories`, `/api/valuation/calibration/recommendations`, and `/api/valuation/calibration/history`. The HTML dashboard is `/api/valuation/dashboard`. These endpoints reuse the most recent full-universe audit and never initiate provider synchronization.
