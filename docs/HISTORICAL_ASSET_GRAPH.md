# Historical Asset Graph

DTOS v1.7.6 introduces Historical Asset Graph schema `1.0`, preserves the backward-compatible Historical Memory schema `1.0`, adds Player History schema `2.0`, and advances the importer to `1.2`. The graph is a deterministic read model over DTOS's immutable SQLite historical records; it never synchronizes Sleeper or changes state during a request.

## Read-model lifecycle (v1.7.7)

As of v1.7.8, graph construction is lazy and route-specific. Coverage uses compact SQLite aggregation, player reads load only the requested player's weekly payloads, asset directories resolve indexed identities without hydrating all player-week evidence, and the process retains one active dataset generation. Expired importer leases are recovered automatically from completed checkpoints without permitting two live importers.

The process-local read model is keyed by league, historical dataset content identity, all relevant schema/importer/calculation versions, and verified current identity metadata. It builds once under a lock, publishes only after every index is complete, retains at most two versions, and invalidates automatically when stored history or identity inputs change. Multi-worker deployments independently build the same deterministic model per worker.

Directory requests filter and paginate stable player/pick references before hydrating summaries. Detail requests use indexed asset events, parent transactions, player weeks, season totals, ownership evidence, trades, and conversions. Cache and query diagnostics are returned by `/api/history/coverage`; directory responses include the same read-model metadata. No read method imports or invokes provider synchronization.

## Identity contracts

- Players: `DTOS-P-{Sleeper player ID}`
- Picks: `PICK-{season}-R{round}-ORIG{original roster ID}`
- Transactions: `TX-{source league ID}-{Sleeper transaction ID}`
- Trades: `TRADE-{source league ID}-{Sleeper transaction ID}`
- Events: a deterministic `EVENT-` hash of source identity and movement leg
- Franchises: `{root league ID}:franchise:{roster ID}`

Unknown historical players retain their raw Sleeper ID, an `unresolved` status, and a missing-data explanation. DTOS does not infer a name or merge identities by display name.

## Event and ownership rules

Every normalized event exposes asset and event identity, status, season/week, occurrence and observation times, source league and record, parent transaction/draft, movement franchises, provenance, schema/importer versions, and completeness. Only verified completed events can modify ownership. Failed and pending transactions remain queryable but are excluded from ownership intervals.

Transactions are reconciled with weekly roster snapshots. Conflicts remain visible through reconciliation statuses rather than being silently repaired. Missing timestamps, unsupported provider fields, incomplete current seasons, and unresolved identities are warnings; they are never converted into invented values.

## Public contracts

- `GET /api/history/assets`
- `GET /api/history/assets/{asset_id}`
- `GET /api/history/assets/{asset_id}/events`
- `GET /api/history/assets/{asset_id}/ownership`
- `GET /api/history/players/{player_id}` and child season/transaction/trade endpoints
- `GET /api/picks/{pick_id}` and `/api/picks/{pick_id}/history`
- `GET /api/trades/history/{transaction_id}`
- `GET /api/history/transactions`
- `GET /api/history/franchises/{roster_id}`
- `GET /api/history/coverage`
- `GET /api/search`

The HTML routes `/picks/{pick_id}`, `/trades/history/{transaction_id}`, and `/search` render these same contracts. Current and historical surfaces use the same canonical IDs.

## Intelligence boundary

The canonical Brain can use historical coverage to reduce Decision Confidence by at most ten points. History does not change intrinsic or market valuations, failed activity is not market evidence, and current values are never described as historical values. Recommendation provenance discloses whether historical evidence was available and which limitations applied.

## Future Asset Market boundary

Asset Market v1.8.0 may consume stable asset identities, events, ownership intervals, summaries, and provenance from this graph. It must not duplicate historical reconciliation or redefine these IDs.
