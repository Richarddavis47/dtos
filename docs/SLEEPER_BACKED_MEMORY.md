# Sleeper-Backed League Memory

DTOS v1.10.19 formalizes a strict data-ownership boundary:

- Sleeper and external providers own facts.
- DTOS may normalize and cache those facts for performance and provider etiquette.
- DTOS permanently retains only compact, meaningful intelligence and system metadata.
- Existing Historical Memory remains intact until a future reversible migration is separately approved.

## League history

The provider-backed history path starts from the current Sleeper league ID and walks
`previous_league_id` until Sleeper terminates the chain. It has a cycle/corruption
safety bound but no calendar-year cutoff. Missing provider history is reported as
`unavailable` or `partial`; the proof path never fills gaps from legacy Historical
Memory.

Completed seasons are stored as compressed, checksummed, disposable provider caches.
Deleting a cache causes a bounded provider reconstruction attempt. If the provider no
longer supplies the season, the evidence remains unavailable. Current-season facts
remain mutable and continue through the existing bounded synchronization path. The NFL
player catalog remains shared by reference across league runtimes.

## Permanent intelligence

`IntelligenceCheckpoint` captures what DTOS knew at a meaningful moment. It supports
players, future picks, exact rookie slots, pick lineage, league/scoring context, DTOS
value layers, legitimate market evidence, confidence, completeness, model identity,
Brain semantic identity, related events, and compact provider observations.

Provenance is explicit:

- `live_captured`: contemporaneous DTOS intelligence.
- `historical_source_backfill`: later import of a genuine period observation.
- `reconstructed`: later estimate; never definitive historical process evidence.
- `unavailable`: no legitimate evidence; never treated as zero.

Checkpoint insertion is immutable and semantic-key deduplicated. Model upgrades create
new observations rather than rewriting history. No daily full-universe logging exists.
Scheduled season benchmarks and event triggers are idempotent.

## Market evidence

Current Market Value requires current, fresh provider evidence. Historical checkpoints
are never a fallback for current value. A provider outage produces an unavailable or
incomplete current Market.

Historical selection uses the newest approved observation at or before the event.
Later snapshots are excluded. Confidence declines at 24 hours, three days, seven days,
and again when a major intervening valuation event is known. DynastyProcess is approved
for historical backfill. FantasyCalc history is schema-supported but systematic use of
its undocumented historical interface remains disabled pending separate approval.

Single-source historical evidence is valid but labeled single-source. Consensus requires
multiple legitimate providers. Missing important trade assets make the assessment
`partial`; their value is never silently zero.

## Pick lineage and event triggers

Generic pick knowledge is preserved exactly as it existed at execution. Later slot and
selected-player links append outcome lineage without rewriting the historical generic
pick. Trade, waiver, drop, fantasy draft, NFL Draft, material teammate impact, major NFL
event, and scheduled benchmark trigger contracts are bounded and deduplicated. Global
events do not hydrate inactive leagues.

## Storage classification

| Category | Owner | Retention |
|---|---|---|
| Sleeper settings, rosters, matchups, drafts, transactions | Sleeper | Disposable cache |
| External provider current facts | Provider | Disposable cache |
| Intelligence checkpoints and pick lineage | DTOS | Compact permanent |
| Shared NFL catalog and provider metadata | Shared/global | One shared cache |
| League references, checksums, model versions | DTOS | Small permanent metadata |
| Legacy Historical Memory | Mixed | Preserved pending future migration |

Storage diagnostics report the permanent checkpoint database separately from provider
caches, Projection storage, Asset Market artifacts, and legacy Historical Memory.

## Future Historical Memory migration

Provider-derived league settings, rosters, matchups, standings, playoffs, drafts,
transactions, trades, waivers, and traded picks are candidates for reclassification as
disposable cache after production equivalence is proven. Import/checkpoint metadata,
irreplaceable external observations, DTOS intelligence, and quality audit state require
separate treatment. v1.10.19 deletes or rewrites none of them.
