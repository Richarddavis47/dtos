# Retained-season memory residency

All production consumers now share the canonical history store’s single
`SleeperSeasonCache`: history services, intelligence-memory compatibility
exports, GM observations and the default Weekly Report router. Explicit
disposable cache injection remains available for tests. The former duplicate
owners no longer multiply the process-wide residency allowance.

This process-wide cache is independent of the league runtime
manager. Before build 2182, writes and verified reads retained league, roster
and transaction sections indefinitely. Runtime idle eviction released neither
those objects nor the separate verified-checksum index. Registering a league
alone does not load this cache.

## Ownership and limits

`src/core/history_context/season_cache.py` now maintains LRU section references
with two simultaneous limits: 36 sections and 8 MiB of estimated Python objects.
The count permits two idle contexts, six retained seasons each and three compact
sections per season. The independent byte cap uses the existing historical
memo's 8 MiB allowance. Checksum metadata has a separate 12-archive LRU limit.
These limits do not change disk retention, runtime limits or historical DTOs.

The object estimate traverses Python containers once per insertion, includes
entry identity overhead and counts shared values conservatively across entries.
It is not RSS, total process memory or an allowance for all active readers.
Oversized sections bypass residency and remain available in complete verified
reads. No silent truncation or provider fetch occurs on a section-cache miss.

Readers borrow read-only objects, as before this release. Eviction removes only
the cache's references and never clears/mutates those objects. A reader holding
an old snapshot keeps that snapshot; a later lookup checks the archive identity
and cannot treat it as the replacement source. Caller-owned active results are
not charged as idle residency; the existing historical-response admission and
runtime ownership controls still bound their respective workloads.

## Refill, publication and shutdown

One per-instance reentrant decode lock serializes cold local archive decoding.
Waiting readers recheck the cache before decoding, coalescing same-section
misses when the result fits. Warm reads and source writes do not acquire that
lock. The metadata lock covers only identity checks and bounded reference/LRU
updates; it never surrounds provider requests or reconstruction.

File identity includes device, inode, compressed size and nanosecond mtime.
Verified reads keep facts and identity together. Writers capture the temporary
file's identity before atomic replacement, and check that exact identity before
publishing cache references. A superseded writer cannot tag old objects with a
new writer's identity. Replacement, rollback, missing files and deletion discard
incompatible cached entries. Existing checksum and retained scoring/provenance
verification remain authoritative.

After historical requests, runtimes and FOIS workers drain, application shutdown
calls `clear_resident`. An epoch fence prevents a refill that already started
from restoring retired residency. The cache owns no threads, subprocesses,
background jobs, database rows or durable snapshots.

## Consumers and verification

The canonical transaction adapter now borrows league and transaction sections
together for its entire read, so eviction or replacement cannot mix source
identity into later rows. Compact section consumers are that adapter and
shared GM behavioral observations. Full source reads, player-week admission,
historical checkpoints and acquisition coverage continue using verified
`CachedSeason` snapshots. Runtime eviction needs no cache deletion hook: the
global LRU preserves useful reuse across runtime reconstruction while enforcing
its own count/byte bounds. No global Market/player universe is copied here.

`tests/test_season_cache_residency.py` covers distinct leagues, active borrowers,
rebuild equivalence, useful warm reuse, oversized bypass, source replacement and
rollback, delayed writers, concurrent misses, clear/refill fencing, corrupt and
missing archives, and unchanged durable files. Existing full-history response,
source-publication and cancellation suites remain preservation gates.

Author-run disposable 5/10/25-league measurements and raw failed/passing runs are
provided separately for independent Scout review. They do not establish the
cause or resolution of the production OOM, the original cold-Home delay or
hundreds-of-leagues capacity. Retained FOIS grades are not regenerated or
revalidated.
