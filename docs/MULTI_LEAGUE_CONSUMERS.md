# Multi-League Consumer Contract

DTOS resolves league-dependent requests through one immutable request boundary:

`league_id -> LeagueRuntimeManager -> LeagueRuntime -> CanonicalLeagueContext`

The configured league is attached to the manager at startup. Secondary leagues
are hydrated lazily only while `DTOS_MULTI_LEAGUE_IMPORT_ENABLED` is enabled.
An explicit invalid or unavailable league fails closed and is never replaced by
the configured league.

## Consumer inventory

| Consumer | Runtime input | Durable/shared input | Scoped derived state |
|---|---|---|---|
| Crawl and canonical snapshot | league data/state | shared public schema | response cache keyed by league |
| Projection Intelligence | league/scoring context | league-keyed SQLite snapshots | `ProjectionService` per runtime |
| Brain and recommendations | league canonical data | shared model code | `BrainService` per runtime |
| Asset Market | league data, Brain inputs, ownership | league-indexed history store | `AssetMarketCache` and artifact manifest per league |
| Team HQ, Front Office, trades, matchups | request-scoped league data | shared NFL player identities | request-local intelligence |
| FOIS | league roster and evidence | league-keyed FOIS repository | league-specific scores |
| Historical Memory | requested league identity | normalized shared SQLite archive | bounded league read models |
| Inspection and audit | canonical context services | designated public artifact store | namespace selected by league |

Shared NFL identity and immutable provider facts may be reused. Ownership,
settings, scoring, lineups, picks, transactions, projections, recommendations,
FOIS, history, and presentation metadata may not cross league boundaries.

## Lifecycle and privacy

A runtime progresses from `hydrating` to `warm` only after canonical data,
projection restoration, FOIS generation, Brain construction, and context
publication complete. Asset Market remains independently warming until its own
single-flight cache publishes a compatible model. Product diagnostics expose
these states and league-scoped source generations.

Eviction clears large derived contexts and cancels runtime tasks while retaining
intended durable projection/history/market artifacts. Secondary leagues do not
automatically schedule or expose Live Visual captures, DINS, or public mirror
assets.
