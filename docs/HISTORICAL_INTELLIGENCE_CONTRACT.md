# Canonical Historical Intelligence Contract

DTOS v1.12.0 establishes one read boundary above the existing Sleeper-backed
`CanonicalHistoryStore`. It does not add a provider archive or a league-history
database.

## Architecture inventory before v1.12.0

- Raw completed-season facts are normalized in `SleeperSeasonCache` and read
  through `CanonicalHistoryStore`. Current operational facts are retained only
  in bounded runtime state.
- Front Office Intelligence independently merges current transactions with
  cached historical trades. Historical asset routes, FOIS, Asset Market, and
  inspection surfaces also query the canonical store for their own bounded
  purposes. These consumers are intentionally not redesigned in Step 1.
- `MarketHistoryStore` is an independent snapshot list used by the current
  market-trend engine. It is not the canonical long-term source for historical
  market evidence.
- Permanent DTOS history consists of minimal lifecycle/discovery metadata and
  sparse, globally deduplicated intelligence evidence already owned by DTOS.
  Completed Sleeper season archives remain disposable provider caches.

## The canonical boundary

`HistoricalIntelligenceService` normalizes reconstructable facts into stable,
league-scoped `HistoricalEvent` values. It provides bounded reads by league,
franchise, player, season, transaction type, time window, and event identity.
One selected league is indexed at a time and reused until its canonical dataset
generation or active-season revision changes.

Event identity derives from provider, league, normalized event type, and source
record identity. It does not use display text or random UUIDs. The same provider
transaction therefore deduplicates when it moves from active operational state
into a completed-season cache.

Missing timestamps remain missing. Available Sleeper occurrence timestamps keep
their field-level provenance. League-season context IDs bind events to the
settings and lineup rules that applied in that season.

## Privacy and storage boundaries

League transactions, franchises, matchups, drafts, and results are always
league-scoped. A query for one league cannot return another league's events.

`GlobalMarketCheckpoint` represents a single sparse, public/provider market
observation. It contains no manager, roster, league, or trade-package field.
League events may reference its stable checkpoint ID without copying the market
payload. A checkpoint requires an explainable retention reason and can identify
a small, evidence-backed related-player set; it never implies a full-universe
snapshot.

The v1.12.0 service itself performs no writes. It creates no new database, full
league snapshot, or recurring player-market archive.

## Event-time semantics

Checkpoint lookup explicitly selects `exact`, `at_or_before`, or `after`.
Decision-time consumers must use `at_or_before`; future observations are never
silently selected. Later outcome analysis may use later evidence without
rewriting the original decision-time event.

## Consumer roadmap

1. Event-Relevant Global Player Market Memory will supply sparse
   `GlobalMarketCheckpoint` values to this boundary.
2. Historical Franchise State will query league events and league-season context
   without rescanning every provider cache independently.
3. Historical Transaction Intelligence will link private transaction events to
   legitimate event-time checkpoints.
4. FOIS, Front Office Intelligence, and Brain unification will consume the same
   normalized event identities and timestamp rules.
5. GM Behavioral Intelligence will derive tenant-isolated behavior from
   league-scoped events only.
6. Market Trends will migrate from the standalone snapshot store to sparse
   global checkpoints.
7. Trade Historical Upgrade will separate decision-time process evidence from
   later outcome evidence.

Existing consumers remain unchanged in Step 1 unless a later release explicitly
migrates them. This avoids changing current intelligence recommendations merely
because the foundation now exists.
