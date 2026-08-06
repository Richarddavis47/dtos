# DTOS Asset Market

## Purpose

The Asset Market is the canonical, read-only dynasty exchange for DTOS. It combines the existing Valuation Universe, Brain, ownership data, and Historical Asset Graph without copying their business logic or initiating provider synchronization.

The browser experience is available at `/` and `/market`. The Commissioner Desk remains available at `/commissioner`.

## Public contract

- `GET /api/market` — identity, health, counts, and endpoint discovery.
- `GET /api/market/health` — dataset, cache, duplicate-ID, timing, and read-path diagnostics.
- `GET /api/market/assets` — deterministic filtered and paginated canonical assets.
- `GET /api/market/assets/{asset_id}` — canonical valuation, Brain recommendation, provider evidence, and on-demand historical dossier.
- `GET /api/market/search` — current and historical asset, team, manager, trade, and transaction discovery.
- `GET /api/market/trending` — evidence-qualified trends or an explicit unavailable reason.
- `GET /api/inspect/market` — read-only DINS representation of the market.

Every response identifies the application version/build, market schema, league, market dataset, Brain snapshot, valuation generation, and generation timestamp.

## Dependency boundary

```text
Asset Market routes
  -> versioned Asset Market read model
      -> canonical Valuation Universe
      -> canonical Brain service
      -> durable Historical Asset Graph / store
```

Routes format existing contracts; they do not compute new valuations or recommendations. Distinct value layers remain distinct. Missing provider or historical evidence is reported explicitly.

## Determinism and performance

The read-model key includes application/build/schema identity, league synchronization state, Brain generation, valuation schema, and durable historical dataset version. Rebuilds are single-flight. A failed rebuild can retain the last valid immutable model while health reports the failure. The cache is process-local and bounded to one current and one last-valid market model.

Directory filtering, sorting, ranking, and pagination use compact summaries. Full provider evidence and historical dossiers hydrate only after a canonical asset is selected. Warm reads perform no provider calls.

## Sorting and filtering

The API supports asset type, position, availability, owner, value range, age range, pick year, pick round, value layer, direction, offset, and limit. Ranking is deterministic and exposes its canonical-asset-ID tie-breaker. Search understands common asset phrases such as free agent, rookie, taxi, position names, and draft picks.

## Trending evidence

Trending requires at least two comparable, timestamped observations for an asset. When that evidence does not exist, the contract says so instead of inferring movement. “Most Discussed” remains unavailable until a supported discussion provider exists.

## Safety

The v1.8.0 actions are advisory links and placeholders only. The Asset Market never submits trades, writes Sleeper state, changes ownership, or modifies Historical Memory.
