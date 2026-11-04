# Canonical Historical Intelligence Contract

## v1.21.69 — Single-publication provenance and unavailable scoring

Retained record projection pins the facts and checksum from the same verified
`CachedSeason` read. It never obtains a newer mutable checksum after capturing
older facts, and never invents a publication identity from projected fragments.
Publication replacement can yield the earlier or later verified snapshot, but
cannot relabel an earlier score with the later publication checksum. No new
lock, cache, archive or provider request is required.

Player history renders unavailable season scoring as a concise explanation,
not null-valued metrics. Genuine zero production remains numeric; an unavailable
individual metric such as consistency at zero mean is labeled Unavailable.
Player identity, season and dossier navigation remain available. All v1.21.68
admission and identity-conflict rules continue to apply. Retained FOIS remains
RETAINED / NOT REVALIDATED; the historical integration batch awaits independent
Scout acceptance.

## v1.21.68 — Retained admission and rejected identity updates

Active matchups, retained Sleeper caches and existing compact reader checkpoints
share source-confirmed completion admission: an integer `last_scored_leg` from
0–18, excluding booleans, or the provider's explicit completed-season status.
Missing, malformed and out-of-range markers do not admit actuals; calendar
position is not completion evidence. Rejected weeks never reach career totals,
season leaders or historical production. Historical decision cutoffs remain
independent and stricter than source completion.

Retained numeric player scores require a supported source league/season and
finite league-scoring settings. Same-season operational league, scoring and
lineup context must agree when present; current-season rules never replace
independently supported older-season rules. Unsupported numeric observations
retain raw source scores and membership/roles but have unavailable admitted
production, not zero. Reconciliation preserves that qualification, including
when another copy contains a numeric score. Existing compact checkpoint reads
reapply these rules without rewriting the retained source.

An identity-mismatched update cannot replace an accepted identity or its birth
date candidates. The existing normalized cache retains the accepted identity
and unresolved conflict through restart; rejected raw dates are not republished
under a corrected ID. A later single-date refresh does not resolve a known
conflict. Ordinary refresh has no conflict-resolution authority. Legitimate
resolution requires explicit reviewed source reconciliation that establishes
the exact player/provider identity, authoritative corrective provenance and why
each conflicting candidate is invalid or superseded. No such reconciliation,
history rewrite or new resolution mechanism is performed by this release.

Source replacement invalidates existing bounded read indexes. No cache limits,
schema, archive, provider calls, valuation policy or legal-lineup rules change.
Retained FOIS grades remain RETAINED / NOT REVALIDATED. Independent Scout
acceptance of these controls is required before closing the integration batch.

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
6. Market Trends now derives deterministic direction, magnitude, milestones,
   observed range, volatility, and confidence from sparse Step 2 global
   checkpoints. League transaction liquidity remains a separate private,
   indexed context. The standalone `MarketHistoryStore` remains only as a
   runtime compatibility input for the older orchestration report and is not a
   durable source for the Asset Market, its trend API, or its UI.
7. Trade Historical Upgrade will separate decision-time process evidence from
   later outcome evidence.

Existing consumers remain unchanged in Step 1 unless a later release explicitly
migrates them. This avoids changing current intelligence recommendations merely
because the foundation now exists.

## v1.21.67 — Active player-week and historical age admission

The canonical adapter reuses `season_matchups`, already prepared during normal
Sleeper synchronization. League, season, calendar and methodology identities
must match; only source-confirmed completed periods (`last_scored_leg`, or a
completed league season) enter the active actuals family. Individual scores are
Sleeper's league-scored actuals, not projections or recomputed raw NFL stats.
Rows retain endpoint, generation, observation time, league scoring, lineup rules,
player, franchise and explicit starter/bench/unknown roles. A bench observation
is not an official starting-lineup contribution. Missing scoring/identity or a
conflicting score is not replaced by zero. Retained current-season placeholders
also respect the source's explicit completed-week boundary.

Historical decision consumers still exclude the decision's ongoing week and
later weeks. A boundary without a supported week cannot admit weekly production.
A known Week 5 result can support that observed sample without establishing full
Weeks 1–5 coverage. Transaction/anchor/order and canonical historical price
qualifications introduced in v1.21.66 remain independent and required.

Birth dates are retained as bounded metadata on the existing canonical player
identity and normal league-cache publication, not a separate history record.
At most two distinct date candidates suffice to preserve a conflict; omission
cannot erase supported evidence or resolve conflicting dates. Exact Sleeper and
supported provider-ID joins remain authoritative; names and current ages are
never evidence joins or substitutes. Date-only and ISO datetime birth evidence
are normalized to a calendar date, then age is calculated relative to the
actual decision date. Missing, invalid, conflicting, identity-incompatible and
post-decision birth dates yield unavailable age with reason codes.

Existing compact isolated-process input retains the same prepared matchups and
minimal birth-date metadata, not a new source copy. Player history/career,
season leaders, historical franchise production/lineups/age and historical
transaction context can consume these facts. Existing FOIS preparation can
receive them, but retained grades are not regenerated, migrated or revalidated.
No Market-trend wiring or reserve-quality work is included. Reads neither fetch
providers nor append source files, and irrelevant identity/trade queries do not
materialize weekly rows. Existing cache limits and resource gates are retained.
