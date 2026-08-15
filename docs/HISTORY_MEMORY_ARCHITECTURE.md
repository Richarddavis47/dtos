# DTOS History and Intelligence Memory Architecture

## Ownership model

DTOS separates provider facts, operational state, permanent DTOS intelligence,
and system metadata. These stores have deliberately different retention rules.

| Component | Ownership | Retention | Purpose |
| --- | --- | --- | --- |
| Sleeper | Provider | Authoritative upstream | Reconstructible league facts |
| Sleeper Season Cache | Provider cache | Disposable, rebuildable | Normalized completed-season facts |
| Current League Runtime | Operational | Bounded and evictable | Current rosters, scoring, identities, and league state |
| IntelligenceCheckpoint | DTOS | Permanent and sparse | Event-time values, decisions, provenance, and outcome evidence |
| Minimal Metadata Store | DTOS | Permanent and small | Cache checkpoints, sync generations, lifecycle and compatibility audit |
| Projection Cache | Provider cache | Disposable | Canonical Sleeper projection evidence |
| Asset Market Artifact | Operational | Bounded and replaceable | Current market read model and indexes |
| Legacy HistoricalStore | Legacy | Physically retired in v1.10.27 | Fail-closed path guard; no recreation |

The Sleeper Season Cache is not permanent Historical Memory. IntelligenceCheckpoint
does not own provider history. Missing upstream history is reported as partial or
unavailable and never filled from the legacy archive.

## Runtime flow

A saved league keeps a small reference and cache metadata. Opening a cold league
discovers its Sleeper season chain, reads or rebuilds normalized completed-season
caches, assembles a bounded `LeagueRuntime`, and runs shared DTOS intelligence.
Only one or two active runtimes remain warm; inactive runtimes may be evicted.

Current synchronization replaces bounded operational state and invokes canonical
IntelligenceCheckpoint event triggers. It does not append roster, valuation,
identity, or provider snapshots to HistoricalStore. Completed-season cache writes
are atomic and their compact checksums are recorded in the metadata store.

## Shadow-forbidden legacy state

In v1.10.23 the legacy database remains on disk unchanged. Importing the legacy
package does not validate, open, initialize, or recreate that database. Canonical
runtime consumers receive `CanonicalHistoryStore`, a read model over Sleeper cache
and bounded current state. Diagnostics require zero legacy read and write attempts.

Legacy classes, migrations, and fixture utilities remain solely for compatibility
tests and the future physical-retirement workflow. They are not canonical runtime
dependencies.

## Scale and cache behavior

Stored league count is cheap: references, completed-season compressed caches, and
sparse checkpoints grow with saved leagues, while RAM grows mainly with active
runtimes. A conceptual 30-league deployment with ten completed seasons each keeps
roughly 300 compressed provider-cache objects plus sparse intelligence and metadata;
only two league runtimes need be resident. Exact capacity must be based on measured
production cache sizes rather than the former archive size.

Completed-season cache entries are immutable by checksum and may later be governed
by an LRU policy because they are rebuildable. Eviction cannot remove permanent
IntelligenceCheckpoint evidence or minimal system metadata.

## v1.10.24 handoff (read-only plan)

Physical retirement must be a separate, explicitly authorized release. It should:

1. Reconfirm zero canonical legacy reads and writes through sync, smoke, multi-league,
   restart, inspection, and DINS.
2. Inventory the legacy database, WAL, SHM, configuration, manifests, and remaining
   source references; classify them as test-only, migration-only, deprecated, or bug.
3. Verify no required permanent DTOS data exists only in the legacy database.
4. Record file sizes and hashes, then remove the dormant files directly without
   `VACUUM` or creating a second full database copy.
5. Restart and prove DTOS neither needs nor recreates the archive.

No physical removal, table mutation, compaction, or disk reclamation is performed
by v1.10.23.
