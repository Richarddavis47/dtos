# Historical League Memory

DTOS v1.5.0 introduces one shared longitudinal evidence layer for league and player history. It supplements current-state JSON caching; it does not replace Sleeper synchronization, Valuation Calibration, Team Intelligence, or the Intelligence Orchestrator.

## Storage and migration

The default database is `DTOS_HISTORY_DB_FILE` or the platform temporary directory's `dtos_history.sqlite3`. Production deployments should set `DTOS_HISTORY_DB_FILE` to persistent storage. Migration version `1` creates:

- `historical_records`, an append-only evidence table;
- `player_identity`, a versioned provider-ID map;
- `import_runs`, resumable checkpoints and outcomes;
- `data_quality_issues`, classified reconciliation findings;
- indexes for league/entity/season/week, player, and franchise access.

Historical schema, player-history schema, prediction model, Team Intelligence model, and valuation schema versions remain attached to records so later models cannot reinterpret old snapshots silently.

## Identity

League identity and source-season league IDs remain distinct. A franchise uses a stable root-league and roster-slot identifier while owner IDs, usernames, and team names are dated season records. Player history joins by provider IDs, never display name. Duplicate names therefore remain independent.

## Provenance and availability

Every record stores provider, source record ID, retrieval time, observation time, season, week, availability, confidence, calculation method, derived/raw status, and schema version.

Availability distinguishes `observed`, `unavailable`, `estimated`, `calculated`, `incomplete`, and `provider_not_supported`. An observed zero remains zero; missing evidence remains null.

## Sleeper import

The importer follows `previous_league_id` from the selected league, checkpoints each season, and uses deterministic record keys. Re-running a season inserts no duplicates. It imports available:

- league/scoring/roster/playoff/draft settings;
- owner and franchise name instances;
- season standings source fields;
- weekly rosters, lineups, bench lists, matchups, and league-scored player points;
- winners and consolation brackets;
- drafts and selections;
- transactions and first-class trades.

Current synchronization additionally captures current roster state, canonical provider values, Team Intelligence cards, and preseason predictions.

## Player production and usage

Sleeper matchup history supplies player fantasy points under the historical league configuration, but does not supply the raw NFL stat line or advanced snap/route/target/carry usage. Those fields are explicitly unavailable. The scoring helper deterministically reproduces a score when raw stats and season-specific scoring multipliers are supplied by an approved provider.

Aggregates include total, PPG, median, floor, ceiling, standard deviation, coefficient of variation, consistency, and rolling 3/5/8-game averages. Null weeks are excluded, not converted to zero.

## Workbook reconciliation

The optional Day Traders workbook path is `/mnt/data/Day_Traders_Front_Office_Database_v13_8_Master(1).xlsx`. It was not present in the development workspace. The importer records that status and does not require a workbook for other leagues. No workbook value can replace authoritative Sleeper data without a future explicit field-level reconciliation rule.

## Public API

Historical routes under `/api/crawl/history` support bounded pagination and league, season, week, franchise, and player filters. Discovery is published by `/api/crawl`. Large default payloads are capped at 100 and hard-limited to 500 records.

## Data quality

Quality issues are informational, warning, or blocking. Current checks disclose missing weeks and provider gaps. A release/backfill cannot be considered complete while unresolved blocking issues exist.

## Limitations

- Sleeper does not expose historical raw NFL stat components or advanced usage.
- Historical taxi/IR distinctions are not present in matchup payloads.
- Trade-time market values exist only when a contemporaneous provider snapshot is available.
- Standings ranks tied on record are not inferred from API ordering.
- Workbook reconciliation remains unavailable until the optional file is supplied.
- Persistent production history requires a durable `DTOS_HISTORY_DB_FILE` mount.
## Snapshot identity and immutability

Current Team Intelligence snapshots are uniquely identified by league, franchise,
season, week, observation timestamp, snapshot type, and model version. Prediction
snapshots use the same dimensions with their own explicit snapshot type. Replaying
an identical observation is idempotent; a new observation or model version creates
a separate immutable record. Current roster recalculation never updates an earlier
snapshot.
