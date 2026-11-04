# DTOS Valuation Universe

DTOS v1.7.0 introduces one deterministic, read-only valuation universe over the current successful Sleeper synchronization. It is calibration infrastructure: it does not recalibrate or blend existing DTOS values.

## Canonical identity

Players use `player:{sleeper_id}`. Picks use `pick:{year}:{round}:{original_roster_id}`. The universe includes every cached Sleeper player—rostered, taxi, injured, suspended, inactive, retired, practice-squad, and free-agent records—and every row in the canonical pick ledger. Unknown future slots remain explicitly unknown; DTOS does not guess them.

## Valuation layers

Each asset independently exposes market, intrinsic DTOS, league-adjusted, contender, rebuilder, liquidity, confidence, risk, age-curve, provider-consensus, future, and current-production values. Every layer includes source, schema version, generation timestamp, confidence, and availability. Missing evidence produces an `unavailable` layer rather than a fabricated value.

Market comparison is separate from valuation. When both market and intrinsic values exist, DTOS reports the percentage difference and a deterministic `No Difference`, `Minor`, `Moderate`, `Major`, or `Extreme` band. v1.7.0 does not act on that difference.

## Freshness

Every response records DTOS version, build, deployment commit, Sleeper synchronization time, valuation time, provider refresh time, generation time, data age, status, and explicit reasons. Status is `Current`, `Refreshing`, `Partial`, `Provider Delayed`, or `Unavailable`. Cached data is never silently described as fresh.

## Providers

The public provider contract is neutral across DTOS, KTC, FantasyCalc, and DynastyProcess. Each provider reports raw value, normalized value, rank, last update, confidence, availability, reason, and source version. KTC remains explicitly unsupported until an approved licensed or public API is configured; no KTC assumptions are embedded in DTOS calculations.

## API and exports

- `GET /api/valuation`
- `GET /api/valuation/status`
- `GET /api/valuation/providers`
- `GET /api/valuation/assets?offset=0&limit=100&asset_type=player`
- `GET /api/valuation/assets/{asset_id}`
- `GET /api/valuation/export.json`
- `GET /api/valuation/export.csv`
- `GET /api/inspect/valuation`

The exports use the same live cached universe as the API. They do not read retained DINS bundles or trigger provider refreshes independently.
