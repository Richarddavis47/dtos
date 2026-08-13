# Multi-League Runtime Contract

DTOS remains one shared application and intelligence engine. A
`LeagueRuntimeManager` lazily creates bounded league contexts and retains at most
two warm runtimes by default (`DTOS_MAX_WARM_LEAGUE_RUNTIMES`, hard bounded to
1–3). The configured Sleeper league is pinned as the backward-compatible default.

## Route classification

- Global/shared: liveness, deployment metadata, runtime-manager health, provider
  registry metadata, and public release discovery.
- Default-league: existing UI and API routes without an explicit league selector.
  These continue to resolve the configured Day Traders runtime.
- Explicitly league-scoped: `/api/leagues/{league_id}/runtime` and future route
  contracts that explicitly accept a league ID. An explicit ID never falls back
  to the default. Secondary hydration remains feature-gated until deployment
  isolation validation opts in.

## Storage and residency

Durable Historical Memory remains normalized in one SQLite store with league ID
in record and query identity. Completed facts, checkpoints, FOIS evidence, and
compact artifacts are durable. Current Sleeper state and provider results are
league-scoped TTL caches. Brain, Team HQ, current recommendations, and Asset
Market objects are recomputable and released on runtime eviction.

Asset Market and inspection manifests use a non-reversible league namespace.
One league's publication never deletes another league's compatible artifact.
Full DINS and the External Visual Mirror remain designated validation-league
products; importing a league does not automatically create browser evidence.

## Inactive work

Evicted leagues have no scheduled projection, FOIS, market, or visual work.
Only the configured active runtime participates in legacy periodic refresh.
Secondary runtimes refresh when explicitly requested or through a future bounded
maintenance policy.

## Projection preparation

Projection snapshots restore by league identity. A deterministic
`scoring_profile_id` canonicalizes scoring settings and roster positions, allowing
future NFL-wide provider evidence to be shared between leagues with identical
profiles without confusing their league-specific assembled snapshots.

## Scale and retention policy

Runtime count, hydrations, restore hits, failures, and evictions are observable at
`/api/leagues/runtime`. Raw provider payloads are not permanent league history.
Completed immutable history is normalized and indexed; current caches expire;
recomputable objects are evicted; old visual evidence remains on-demand rather
than multiplying by every saved league.
