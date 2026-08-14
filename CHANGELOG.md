# Changelog

## v1.10.23 - HistoricalStore Consumer & Writer Migration

- Migrated canonical league-history consumers to disposable normalized Sleeper
  season caches and current operational league contexts.
- Preserved sparse DTOS-owned historical intelligence in IntelligenceCheckpoint
  while removing recurring current-sync writes to the legacy provider archive.
- Added a compact system metadata store for cache checkpoints and sync generations.
- Added shadow-forbidden legacy read/write accounting and made legacy package
  imports non-opening and non-initializing.
- Preserved the legacy HistoricalStore database physically and non-destructively
  for the separately authorized v1.10.24 retirement decision.

## v1.10.22 - Resource Admission & Heavy-Work Coordination

- Replaced the static raw-memory emergency boundary with a deterministic,
  reclaimable-cache-aware hard-pressure calculation while preserving the 2 GiB
  cgroup limit, 1.5 GiB effective ceiling, and 500 MiB reserve.
- Added versioned admission evidence for reclaimable allowance, predicted hard
  pressure, and the absolute cgroup safety margin.
- Prioritized first Asset Market generation work over Live Visual and DINS browser
  capture without changing projection, market, or warming contracts.

## v1.10.21 - Sleeper Canonical Projection Mirror

- Make league-scored Sleeper weekly projections the sole canonical production projection.
- Cover relevant rostered and unowned players with explicit projected-zero and unavailable states.
- Add scoring-profile identities, bounded Week 1-18 provider caching, and semantic no-change behavior.
- Migrate canonical intelligence, matchup, audit, inspection, and market consumers away from the legacy forecast.
- Keep provider caches disposable and permanent projection evidence compact and event-scoped.

## v1.10.20 - Intelligence Checkpoint Runtime Integration

- Connect canonical Sleeper transaction and fantasy-draft ingestion to permanent intelligence checkpoints.
- Add idempotent trade, waiver, drop, draft, and scheduled checkpoint processing with league isolation.
- Expose bounded checkpoint-pipeline health while preserving side-effect-free request routes.
- Make permanent checkpoint evidence available to FOIS without treating reconstructed or unavailable evidence as definitive process quality.

## v1.10.19 - Sleeper-Backed League Memory & Permanent Intelligence Checkpoints

- Discover each dynasty league's actual Year 1 through Sleeper's season chain with no calendar cutoff.
- Add compact, checksummed, disposable completed-season provider caches with honest partial/unavailable states.
- Add an immutable, deduplicated IntelligenceCheckpoint store with provenance, temporal confidence, triggers, pick lineage, and storage contracts.
- Separate current Market Value from historical evidence and prohibit stale historical fallback.
- Expose public-safe ownership, completeness, cache, checkpoint, and storage diagnostics while preserving legacy Historical Memory unchanged.

## v1.10.18 - Multi-League Resource Observability & Storage Hygiene

- Added bounded durable Asset Market admission history with explicit reason
  codes, cgroup/OOM evidence, browser counts, and public-safe lifecycle context.
- Added explicit diagnostic-only retained-memory attribution for league runtime,
  projection, Brain, FOIS, player-catalog, and Market components.
- Added manifest-safe one-current-artifact-per-league pruning with non-fatal
  cleanup telemetry, disk health, and 30/100/300-league storage projections.
- Added public-safe multi-league resource health without request-time provider,
  Market-construction, Brain-generation, or deep-sizing work.

## v1.10.17 - Multi-League Consumer Integration

- Added a request-scoped CanonicalLeagueContext that routes canonical crawl,
  projections, Brain, Asset Market, FOIS, history, audit, and inspection reads
  through the explicitly requested hydrated LeagueRuntime.
- Added league-scoped source-generation and product-readiness diagnostics while
  preserving bounded two-runtime residency and derived-context eviction.
- Prevented secondary/private league visual artifacts from being exposed or
  generated through ordinary inspection routes.
- Added explicit secondary routing, concurrency, feature-gate, and state
  isolation regressions.

## v1.10.16 - Multi-League Runtime Foundation

- Added a lazy bounded LeagueRuntimeManager with per-league single-flight, LRU
  eviction, failure isolation, health metrics, and deterministic shutdown.
- Added structured league/scoring cache identities and deterministic scoring
  profiles for future shared projection evidence.
- Scoped Sleeper state, locks, current-state caches, projection restoration,
  Asset Market manifests, and inspection artifacts by league identity.
- Added permanent A/B, concurrent, invalid-league, eviction, shutdown,
  projection-restore, and 30-league residency regressions.


## v1.10.15 - Projection Snapshot Upgrade Compatibility

- Added explicit schema, model, contract, and semantic-policy compatibility checks
  before a durable Projection snapshot can become canonical.
- Added one cached-input upgrade generation when the provider fingerprint is
  unchanged but the running Projection contract advances.
- Separated application and active-snapshot identity in projection health, with
  compatible/incompatible restore and durable-publication lifecycle counters.

## v1.10.14 - Player-Specific Projection Calibration

- Replaced final positional-default projection clusters with deterministic player,
  role, production, and cached Sleeper-evidence calibration.
- Preserved raw DTOS forecasts separately from calibrated canonical projections,
  with confidence, evidence depth, fallback state, and disagreement explanations.
- Expanded projection health and audit exports with fallback concentration,
  disagreement, distribution, and calibration diagnostics.

## v1.10.13 - External Mirror Matchup Surface Classification Correction

- Added one strict shared parser for numeric matchup-detail surface IDs.
- Kept `matchups-page` mirrorable as the directory without applying detail-only
  22-starter reconciliation.
- Added explicit matchup-directory traversal metadata and matching GitHub-only
  verification coverage.

## v1.10.12 - Permanent External Visual Mirror

- Added a small immutable GitHub mirror of exact Live Visual PNGs, semantic page
  contracts, current projection audit, and discovery metadata.
- Added stable latest-release discovery plus deterministic, human-readable artifact
  names and cross-artifact SHA-256 validation.
- Made core visual capture and mirror eligibility inherit automatically from the
  canonical public-surface registry.
- Added bounded release/scheduled publication automation with no DTOS runtime
  dependency on GitHub.

## v1.10.11 - Live Visual Inspection

- Added durable, anonymous mobile and desktop screenshots of every current
  matchup, captured from the real rendered DTOS production routes.
- Added compact DOM presentation metadata, canonical projection reconciliation,
  semantic fingerprints, single-flight capture, and last-valid failure behavior.
- Added automatic post-deployment and material-matchup refresh scheduling while
  preserving zero-work HTTP reads and v1.10.10 Live Product Inspection.

## v1.10.10 - Universal Live Product Inspection & Matchup Projection Presentation

- Added a compact anonymous Live Product Inspection root derived automatically
  from the canonical FastAPI route registry, with dynamic team, matchup, player,
  pick, season, API, search, health, and semantic traversal contracts.
- Added default-on public-surface participation and explicit approved exclusions,
  shared with existing dynamic DINS page discovery.
- Added canonical Sleeper and DTOS projection values, differences, explicit
  missing states, coverage, and reconciled team totals to matchup presentation.
- Preserved the v1.10.9 projection audit exports and all zero-side-effect lifecycle
  contracts.

## v1.10.9 - Projection Intelligence Audit Export

- Added bounded JSON and CSV exports for current matchup starters, canonical
  projections, valuation layers, FOIS context, reconciliation, and snapshot identity.
- Reused only retained Projection Intelligence, Asset Market, and persisted FOIS
  state; audit requests cannot synchronize providers or regenerate intelligence.
- Added explicit unavailable states where no persisted canonical recommendation
  exists, plus a clearly labeled static screenshot regression fixture.

## v1.10.8 - Asset Market No-Op Invalidation Correction

- Replaced process-local synchronized-data identity with a bounded semantic
  Asset Market request revision.
- Added a final semantic-generation admission guard so stale or duplicate
  refresh requests cannot enter artifact loading or market construction.
- Added explicit rebuild-request, admission-skip, and actual-construction
  metrics for production zero-work verification.

## v1.10.7 - Freshness Semantic Threshold Correction

- Replaced continuously decaying evidence freshness with a shared, versioned,
  evidence-family-aware tier contract.
- Preserved exact evidence age for health and diagnostics while stabilizing
  Brain confidence, provider weights, explanations, and Asset Market identity
  inside each semantic freshness tier.
- Added deterministic same-tier, threshold-crossing, immutable-history, and
  production confidence-drift regression coverage.

## v1.10.6 - Brain No-Change Regeneration Correction

- Removed raw provider evidence age from Brain semantic identity while retaining every derived confidence, reliability, weight, score, rank, and valuation output as a strict semantic dependency.
- Added bounded Brain input-family manifests and per-asset semantic-change diagnostics without exposing raw provider, league, or player datasets.
- Added explicit regeneration-attempt, candidate, no-change, changed-asset, and downstream-invalidation counters for production acceptance evidence.
- Preserved projection semantics, valuation formulas, Asset Market construction, FOIS, Matchups, and Historical Memory unchanged.

## v1.10.5 - Projection Semantic Compatibility Correction

- Canonicalized Brain and Asset Market semantic hashing to exclude only named observational metadata while retaining every value, confidence, ordering, ownership, and provider dependency.
- Retained the currently published Brain report when a refresh produces the same semantic generation, preventing false downstream invalidation.
- Added explicit projection refresh/change/no-change metrics and compact Brain/market semantic diagnostics.
- Preserved v1.10.4 durable projection and Asset Market restoration, including offline startup and original freshness timestamps.

## v1.10.4 - Durable Projection & Asset Market Restoration

- Anchored the normalized Sleeper cache and Projection Intelligence database to the configured durable storage root on production deployments while preserving every explicit path override.
- Restored the last valid canonical projection snapshot and compatible Asset Market artifact before background provider refresh, without changing projection, Brain, valuation, FOIS, or matchup formulas.
- Added atomic Asset Market manifests, bounded manifest recovery, explicit discovery states, and restore/publication counters.

## v1.10.3 - Sleeper Projection Provider Redirect Correction

- Added a provider-scoped, HTTPS-only, allowlisted, three-hop redirect policy for the undocumented Sleeper projection feed.
- Preserved the shared HTTP client, projection parser, semantic snapshot contract, and every downstream intelligence formula unchanged.
- Added sanitized redirect diagnostics and deterministic regressions for success, loops, excessive chains, missing locations, host escape, downgrade, and final-response failure.

## v1.10.2 - Sleeper Projection Sync & System-Wide Forward Intelligence

- Added the optional, undocumented Sleeper bulk weekly projection feed as defensively parsed external evidence with a provider kill switch, immutable durable snapshots, freshness, fingerprints, single-flight synchronization, and stale fallback.
- Added league-scoring reconciliation and a bounded canonical consensus that keeps Sleeper, DTOS, and consensus projections separately attributed.
- Extended projection health, provider, accuracy, matchup starter, team-total, Brain, and valuation contracts without request-time provider calls.
- Added semantic no-change detection so observational refreshes do not regenerate Projection Intelligence, Brain, or Asset Market state.
- Preserved startup readiness, historical isolation, source-pure partial coverage, and the independent DTOS Forward Production fallback.

## v1.9.6 - Historical Player Leaders Query Optimization

- Added a measured league/entity/season/player index for bounded player-week aggregation.
- Split season statistical aggregation from one canonical bulk identity-enrichment query.
- Removed correlated per-leader identity sorting while preserving totals, ordering, names, positions, and warm section caching.
- Preserved all v1.9.5 section isolation and event-loop offloading behavior.

## v1.9.5 - History Read-Path Performance

- Replaced full-archive construction on season subroutes with bounded, section-specific Historical Memory reads.
- Moved season read-model construction off the event loop and added request-safe section caching keyed by durable dataset identity.
- Aggregated season leaders in SQLite with one bounded identity join instead of hydrating every player-week record and issuing identity N+1 queries.
- Preserved historical schemas, ordering, provenance, canonical progress, and provider-free read behavior.

## v1.9.4 - Valuation, FOIS & League History Corrections

- Completed independent intrinsic, contender, and rebuilder valuation layers for supported active players and draft picks, with explicit evidence limitations for genuinely unavailable assets.
- Corrected the FOIS centered-score calibration while preserving confidence and completeness as separate evidence-quality measures and retaining prior model snapshots under their original versions.
- Added provider-free season archives with human standings, verified postseason results, weekly matchups, transactions, drafts, player leaders, and explicit current/partial completeness states.
- Routed Asset Market, Brain valuation intelligence, rankings, history presentation, APIs, and inspection discovery through the corrected canonical contracts.

## v1.9.3 - Asset Market Restart Lifecycle Correction

- Added lifecycle-driven Asset Market reconciliation after startup and periodic synchronization.
- Enforced a single-flight self-healing invariant when construction is eligible but no model or compatible artifact exists.
- Added sanitized scheduler state, invocation, and skip-reason diagnostics to market health.
- Preserved background-only construction, bounded warming responses, memory gates, and v1.9.2 presentation behavior.

## v1.9.2 - Intelligence Presentation & Data Utilization

- Added reusable human-first status, availability, rank, and technical-detail presentation contracts.
- Upgraded player history, pick lineage, search, matchup state, and FOIS executive presentation using existing canonical intelligence.
- Added a human Executive Profile with explicit league rank, category evidence, confidence, strengths, and opportunities.
- Documented the site-wide presentation audit and Human Meaning First policy.

## v1.9.1 - FOIS Presentation Contract Correction

- Routed `/fois` through the canonical DTOS shared page header and navigation contract.
- Resolved an omitted league parameter through the current loaded-league state so persisted profiles render by default.
- Added a functional GM Rankings primary action and distinct pending, unavailable, and no-league states.
- Preserved FOIS scoring, persistence, startup orchestration, Historical Memory, and Asset Market behavior.

## v1.9.0 - FOIS General Manager Intelligence System

- Promoted the v1.6 FOIS foundation into a tenure-scoped General Manager
  Intelligence System with permanent GM/franchise separation and immutable
  takeover context.
- Added full-history Results, impact-weighted process/outcome/recovery evidence,
  production Trading, Roster Construction, and Drafting contracts, confidence,
  completeness, honest missing-evidence states, and model versioning.
- Added append-only FOIS snapshots, evidence provenance, executive profiles,
  resumes, comparisons, franchise ownership history, category APIs, a compact UI,
  and Front Office integration without adding a second Brain or history store.

## v1.8.15 - Relevant Player Universe

- Adds one canonical Relevant Player Universe spanning durable league history, current ownership, reserve states, and the top 150 canonically ranked free agents.
- Persists deterministic membership reasons and ranking-snapshot provenance without rewriting immutable historical evidence.
- Routes valuation, Brain, Asset Market, search, and downstream consumers through the same membership contract while preserving pick assets.

## v1.8.14 - Deterministic Asset Market Restart Lifecycle

- Establishes a process startup epoch that keeps Asset Market generation fenced until durable storage, canonical synchronization, Brain/valuation generation, cache persistence, and bounded historical maintenance have completed.
- Consolidates startup-adjacent synchronization into one deterministic cycle and begins periodic refresh timing only after that cycle reaches its terminal state.
- Defers durable artifact discovery until canonical startup inputs are stable, while retaining precise missing, incomplete, corrupt, and incompatible classifications.
- Fsyncs completed Asset Market artifacts before atomic rename and persists the containing-directory rename on supported platforms.
- Exposes bounded startup-fence state and reason through existing lifecycle-aware market health metadata.

## v1.8.13 - Production Combined-Read Memory Safety

- Adds a production-shaped 1 GiB sanitized historical fixture covering 461,166 records and 2,050,532 identity observations.
- Adds an exact sequential and overlapping combined-read cgroup lifecycle audit with phase-level retained-memory evidence.
- Preserves the 2 GiB hard limit, 1.5 GiB target, 500 MiB reserve, complete outputs, and provider-free read routes.

## v1.8.12 - Cgroup-Aware Market Memory Admission

- Distinguishes verified Linux cgroup v2 `inactive_file` cache from live working memory while preserving the 2 GiB hard limit, 1.5 GiB target, and 500 MiB reserve.
- Adds fail-closed cgroup metric validation, memory-event and construction-growth safeguards, and sanitized admission diagnostics.
- Adds bounded generation-aware retry backoff so repeated directory polling cannot launch identical memory-rejected workers.

## v1.8.11 - Retained Asset Market Summary Contract

- Made `/api/market` an immediate metadata-only index over retained Asset Market health.
- Preserved honest cold, warming, ready, replacement, and failed-replacement states without starting market work.
- Kept directory warming, live-store search/detail provenance, memory safety, and semantic compatibility unchanged.

## v1.8.10 - Asset Market Health Dataset Scope

- Added the canonical `artifact_build` dataset-version scope to retained Asset Market health metadata.
- Published the historical dataset version and scope atomically across cold construction, compatible artifact loading, replacement, and last-valid warming.
- Preserved `live_store` semantics for search and detail responses without adding request-time database or provider work.

## v1.8.9 - Semantic Asset Market Artifact Identity

- Replaced timestamp and archive-wide Asset Market artifact invalidation with deterministic semantic content identities.
- Separated compact directory compatibility from live historical-detail reads so current evidence remains visible without unnecessary reconstruction.
- Added bounded manifest discovery with precise sanitized rejection reasons for corrupt, incomplete, cross-store, cross-league, schema, and semantic mismatches.
- Preserved single-flight construction, atomic publication, durable restart reuse, and all historical capture and checkpoint contracts.

## v1.8.8 - Season-Scoped Historical Checkpoint Compatibility

- Replaced global identity-generation checkpoint invalidation with deterministic season-scoped dependency identities.
- Added verified, metadata-only legacy checkpoint migration and compatibility audit records.
- Added a durable audit ledger for committed material identity-mapping changes.
- Added explicit sanitized compatibility reasons across canonical historical progress diagnostics.
- Preserved importer 1.2 event identities, immutable evidence, and the canonical 2026 pending state.

## v1.8.7 - Canonical Historical Progress Selection

- Derives league-wide player-week progress from the configured season universe and durable checkpoints instead of the newest enrichment job.
- Separates canonical history, latest refresh job, active job, and foundation progress without mutating historical evidence.
- Aligns history, coverage, readiness, inspection, DINS, and Asset Market metadata on one progress serializer.
- Extends smoke validation to poll exact warming during registered lifecycle blockers before requiring one market build and HTTP 200.

## v1.8.6 - Asynchronous Market Generation

- Moves cold cache-key, durable generation, identity aggregation, artifact discovery, construction, and publication into one background worker.
- Returns bounded Asset Market warming responses using only retained in-memory lifecycle and build state.
- Preserves a labeled last-valid generation during compatible replacement and publishes completed replacements atomically.
- Adds preparation, loading, building, publishing, failure, duration, and refresh diagnostics to metadata-only market health.
- Keeps liveness, historical reads, and market health responsive during production-scale identity aggregation.

## v1.8.5 - Bounded Historical Identity Context

- Evaluates durable player-week checkpoints before constructing enrichment identity state.
- Streams one compact current identity projection instead of hydrating identity history.
- Treats unchanged identity observations as no-ops and advances durable semantic generations only for material changes.
- Persists enrichment preparation, lease, generation, and context-build diagnostics.
- Adds a metadata-only migration with a fail-safe disk-capacity gate; existing identity history remains untouched.

## v1.8.4 - Bounded Asset Market Construction

- Replaced process-resident Asset Market universe copies with a streaming, atomic SQLite read model that paginates, filters, and searches before hydration.
- Added cgroup-aware construction budgets, single-flight background warming, durable compatible-generation reuse, and bounded stage-level allocation telemetry.
- Preserved canonical Brain, valuation, ranking, history, provenance, and provider-free read contracts while reducing retained cold-build memory to a few megabytes.

## v1.8.3 - Production Memory Lifecycle

- Added one process-local lifecycle coordinator that prevents overlapping synchronization, provider, valuation, historical-import, persistence, and market-build memory peaks.
- Changed Asset Market health to report bounded retained metadata without constructing assets, indexes, recommendations, or historical dossiers.
- Serialized startup maintenance and replaced whole-string cache serialization with durable incremental encoding and atomic replacement.
- Added bounded RSS, available-memory, and Linux cgroup telemetry at lifecycle boundaries plus warming, last-valid, persistence-failure, and startup-order regressions.

## v1.8.2 - Asset Market Query Performance

- Memoized canonical Historical Memory dataset identities with committed-write invalidation, cross-league isolation, and durable database-generation detection.
- Added build-time compact search documents so current, structured, empty, and no-result queries avoid unnecessary Historical Graph discovery and per-asset normalization.
- Added a bounded, single-flight, dataset-versioned player-dossier cache while preserving canonical Brain snapshots, serialized outputs, provenance, and provider-free reads.

## v1.8.1 - Asset Market Cache Stability

- Added a private durable database UUID that survives ordinary SQLite/WAL activity and changes only for a genuinely recreated HistoricalStore database.
- Prevented unrelated enrichment commits from rebuilding the compact 12,000+ asset directory while retaining live historical dataset identity and on-demand detail/search invalidation.
- Avoided unnecessary historical discovery for already-satisfied current-asset searches and added cache-generation, replacement, concurrency, and path-disclosure regressions.

## v1.8.0 - Asset Market & Dynasty Exchange

- Replaced the primary homepage destination with a canonical, searchable Asset Market while retaining the Commissioner Desk at `/commissioner`.
- Added deterministic player and draft-pick rankings, layered valuation filters, pagination, canonical Brain recommendations, and on-demand Historical Asset Graph dossiers.
- Added provider-free market search across current assets, former players, teams, managers, trades, and transactions, with explicit unavailable and evidence states.
- Added a versioned, single-flight, bounded read model plus market health, inspection, route, smoke, and regression contracts.

## v1.7.14 - Canonical Trade History Discovery

- Derived DINS historical trade pages from completed durable Historical Memory records instead of current cached Sleeper transactions.
- Added deterministic, machine-readable exclusions for current trades that do not yet have canonical historical evidence.
- Kept discovery bounded and provider-free while preserving the historical trade detail contract, dataset identity, and stable ordering.

## v1.7.13 - Canonical History Progress Presentation

- Added one presentation-ready player-week enrichment progress contract shared by the History UI, progress and coverage APIs, inspection health, and DINS artifacts.
- Distinguished completed foundation import work from the canonical enrichment state, exact season counters, completed seasons, and expected pending active-season evidence.
- Preserved historical evidence, checkpoints, importer behavior, storage, and the durable v1.7.12 progress repair without mutation.

## v1.7.12 - Historical Enrichment Progress Contract

- Separated enrichment batch sequence/counts from season-level job progress.
- Derived player-week completion exclusively from distinct durable completed-season checkpoints and enforced bounded counters.
- Added an idempotent migration repair with an audit record for inconsistent persisted progress such as `78/6`, without rewriting historical evidence.
- Added explicit completed, pending, and failed season details to import-status progress diagnostics while preserving foundation workflow semantics.

## v1.7.11 - Historical Enrichment Batch Persistence

- Streamed nflverse enrichment data in bounded configurable batches instead of retaining an entire season payload.
- Added durable, atomic batch progress that commits raw evidence, derived scoring, checkpoint metadata, and lease renewal together.
- Preserved importer version 1.2 record identities so replaying v1.7.10 evidence remains idempotent and creates no logical duplicates.
- Added database migration version 4 and regression coverage for streaming, checkpoint reuse, identity reuse, and v1.7.10-compatible record keys.

## v1.7.10 - Durable Historical Storage

- Added a strict production storage boundary that validates the Render disk mount, path containment, and writable state without silently creating an ephemeral fallback.
- Added atomic first-time SQLite initialization and durable single-instance journaling settings while preserving existing databases, checkpoints, leases, reconciliation state, and historical records.
- Added a versioned durable Historical Asset Graph read-model manifest and explicit storage health in readiness responses.
- Kept temporary league caches, source, logs, and unrelated application state outside the persistent disk.

## v1.7.9 - Historical Import Memory Stability

- Replaced coverage event hydration with compact indexed SQLite aggregation and lazy identity resolution.
- Added asset-specific player, pick, trade, franchise, and search reads that remain available during an active import without constructing the global graph.
- Bounded Sleeper weekly retrieval to one week at a time and released normalized provider payloads after each persistence batch.
- Added a retained-dataset 512 MB concurrency benchmark covering import, coverage, player, directory, and post-import read workloads.

## v1.7.8 - Historical Import & Read-Model Lifecycle Stability

- Replaced eager full-history graph hydration with lazy, route-specific indexes and compact SQLite coverage aggregation.
- Reduced production-scale read-model peak allocation and retained only one immutable dataset generation per process.
- Added automatic expired-worker lease recovery with checkpoint continuation and removal of stale lock records.
- Added full-dataset memory, latency, provider-free read, concurrency, and worker-recovery regression coverage.

## v1.7.7 - Historical Asset Graph Read-Path Optimization

- Added a single-flight, dataset-versioned Historical Asset Graph cache shared by historical APIs, dossiers, search, Team Headquarters, Transactions Center, and Front Office reads.
- Added bounded player, pick, event, transaction, trade, ownership, season-summary, and directory indexes with pagination before dossier hydration.
- Added cache invalidation, stale-model recovery, bounded memory retention, build/query instrumentation, and production-scale performance regression coverage.
- Preserved v1.7.6 historical schemas, ordering, provenance, missing-data disclosures, transaction rules, and provider-free read behavior.

## v1.7.6 - Historical Asset Graph & Connected Dossiers

- Added a versioned, deterministic Historical Asset Graph connecting players, picks, transactions, trades, franchises, ownership intervals, and season summaries.
- Added Player, Pick, and Historical Trade dossier contracts with stable canonical IDs, provenance, explicit missing-data states, and bidirectional links.
- Expanded Transactions Center, Team Headquarters, Front Office Intelligence, League History, unified search, public APIs, and DINS discovery with historical evidence.
- Extended resumable Sleeper history ingestion with traded-pick snapshots and lossless source metadata while ensuring failed and pending transactions never alter ownership.
- Added a capped historical-coverage contribution to Brain Decision Confidence without backdating current values or changing intrinsic valuation.

## v1.7.5 - League Payload Memory Safety

- Replaced embedded full-universe Brain caches in `/api/league` with a compact backwards-compatible Brain summary and canonical endpoint links.
- Removed the duplicated internal Brain timeline from the generic league response while preserving dedicated asset and timeline APIs.
- Reduced response serialization memory pressure that could intermittently restart the production worker and surface as an empty HTTP 502.

## v1.7.4 - Brain Integration & Unified Decision Engine

- Established `BrainService` as the cached public source for canonical valuation layers, evidence quality, explanations, diagnostics, and timelines.
- Migrated application intelligence consumers through the Intelligence Orchestrator and added explainable Decision Confidence.
- Added Brain health, migration, asset, timeline, dashboard, and DINS inspection contracts.
- Retained the v1.7.3 valuation APIs as backwards-compatible adapters and added cross-consumer consistency tests.

## v1.7.3 - Valuation Intelligence Engine (DTOS Brain Phase I)

- Added a canonical cached Evidence Engine for every player and draft pick.
- Added distinct, reproducible Evidence Coverage, Confidence, and Provider Agreement scores.
- Added dynamic provider contributions based on reliability, freshness, identity quality, observation confidence, and evidence-family independence.
- Added explainable asset reports, bounded evidence timelines, and valuation diagnostics.
- Added eight versioned evidence-intelligence APIs and expanded valuation asset responses, dashboard, and DINS contracts.
- Preserved Market, Intrinsic, League Adjusted, Contender, and Rebuilder values as independent layers with zero request-time provider calls.

## v1.7.2 - Multi-Source Market Intelligence Provider Network

- Added a canonical, versioned provider registry and immutable evidence contract with explicit licensing, availability, lineage, freshness, identity, and redistribution rules.
- Added dynamic category reliability, independent-family weighted consensus, and transparent missing/disagreement evidence.
- Promoted completed Sleeper trades and league-local demand into quality-filtered, league-isolated observed-market providers.
- Expanded calibration safety, provider APIs, the calibration dashboard, and DINS inspection without adding request-time provider calls.
- Added permanent compliance, privacy, deterministic-output, trade-quality, API, and pending-lifecycle regression gates.

## v1.7.0 - Market Calibration Foundation

- Added one canonical valuation universe for every cached Sleeper player and every canonical future pick.
- Added live valuation status, provider, asset, detail, JSON export, and CSV export APIs.
- Exposed twelve independent, traceable valuation layers without recalibrating existing values.
- Added explicit synchronization and provider freshness contracts, comparison metadata, identity auditing, and DINS valuation inspection.
- Added regression coverage for uniqueness, ownership, free agents, picks, providers, exports, layers, and unchanged DTOS values.

## v1.6.7 - GitHub DINS Artifact Publication Completion

- Added immutable DINS publication through deterministic GitHub Release assets.
- Added public release discovery with brief caching, identity and checksum checks,
  explicit pending/partial/failed/stale states, and production health integration.
- Added deterministic ZIP, manifest, checksum, sanitization, and idempotency tests.
- Kept generated inspection artifacts outside Git history and preserved v1.6.6
  mobile, accessibility, product-contract, and intelligence behavior.

## v1.6.6 - Team Headquarters Mobile Overflow Correction

- Corrected the Team Headquarters intelligence grid so it collapses to two
  columns on tablets and one column on narrow mobile viewports.
- Added a permanent regression contract for the mobile grid breakpoint.
- Preserved all v1.6.5 product design, intelligence, and data behavior.

## v1.6.5 - Product Design System, Navigation & Consistency

- Added Product Design System 1.0 with shared page headers, action hierarchy,
  recommendation evidence, grade context, freshness, accessibility, and mobile rules.
- Standardized primary navigation and Commissioner Desk briefing order around the
  General Manager workflow.
- Replaced generic dynamic-page and internal-identifier presentation with real
  franchise, player, owner, and matchup language.
- Added truthful preseason projections to the Teams directory and preserved all
  underlying intelligence calculations.
- Extended DINS and canonical HTTP validation with product-contract and deployment-
  provenance gates.

## v1.6.4 - Team Identity Normalization & Team Headquarters Polish

- Centralized canonical team-name resolution across presentation, intelligence, inspection, and transaction boundaries.
- Reorganized Team Headquarters around recommendation, core intelligence, roster, assets, activity, and collapsed evidence.
- Made the canonical Competitive Window Contract the sole visible team-window classification.
- Replaced misleading preseason results with projected wins, power ranking, and playoff/championship outlook.
- Removed unavailable bye labels and unfinished Team Headquarters controls.
- Added a permanent HTTP validation gate that rejects rendered generic numbered team and roster labels.

## v1.6.3 - Complete Visual Inspection & Release Verification System

- Upgraded DINS to schema 2.0 with automatic public-page discovery and deterministic dynamic fixtures.
- Added cached public visual, DOM, accessibility, geometry, interaction, health, schema, site-map, and release-manifest APIs.
- Added Playwright Chromium capture at 1440x1200, 1024x1366, and 390x844 with viewport and full-page screenshots.
- Added version-namespaced artifact storage, tolerant image comparison, inspection-mode no-sync isolation, and route-coverage validation.
- Centralized v1.6.3/build 1603 metadata across status, crawl, OpenAPI, and inspection contracts.

## v1.6.2 - AI Inspection System Foundation

- Added DINS, a deterministic read-only page inspection contract under
  `/api/inspect` that projects only the current cached DTOS state.
- Added page catalog, Team Headquarters, Player Dossier, Front Office, and Trade
  Intelligence inspection endpoints with typed structural JSON.
- Standardized sections, cards, tables, charts, buttons, navigation, links,
  empty states, placeholders, warnings, page metrics, and cache timestamps.
- Prohibited synchronization, provider access, intelligence execution, HTML
  rendering, and application-state mutation from the inspection boundary.
- Added contract, determinism, immutability, cached-data, empty-state, and
  no-execution regression coverage.

## v1.6.1 - FOIS Results and Competitive Cycle Engine

- Promoted all 15 Results registry metrics to deterministic production scoring
  over canonical Historical Memory standings, playoff placements, and matchups.
- Added reusable season-timeline, competitive-cycle, rebuild, contention-window,
  reload-efficiency, peak, longevity, and historical-window analysis.
- Added league-size-normalized finishes, actual-matchup win rates, explicit
  strengths and weaknesses, and ownership/missing-history confidence handling.
- Persisted Results timelines and cycles inside existing idempotent FOIS score
  snapshots and exposed them through a dedicated feature-flagged Results API.
- Added ten representative Results scenarios plus cycle, window, history adapter,
  determinism, confidence, persistence, and API regression coverage.

## v1.6.0 - Front Office Intelligence System Foundation

- Added a parallel, feature-flagged FOIS domain with versioned score, category,
  metric, evidence, configuration, identity, and cross-category trait contracts.
- Added configurable 35/25/20/20 category weighting, deterministic aggregation,
  letter grades, and explicit confidence, completeness, and availability states.
- Added idempotent SQLite score persistence and nonblocking orchestration over
  explicitly supplied historical facts.
- Added feature-flagged model, score, category, metric, and completeness APIs
  without changing existing intelligence or UI behavior.
- Added ten representative management scenarios and focused regressions.

## v1.5.11 - Competitive Window Contract

- Added one immutable, versioned competitive-window contract with classification, confidence, horizon scores, evidence, strengths, weaknesses, and generation metadata.
- Removed the Decision Engine and Front Office secondary classifiers; Team Intelligence now creates the sole league-relative classification.
- Reordered orchestration so calibrated market/player valuation and Team Intelligence complete before Front Office, Trade Intelligence, and recommendations.
- Added public contract serialization and consistency regressions proving every consumer shares the same result.

## v1.5.10 - Intelligence Quality Audit

- Audited all ten league franchises, representative player tiers, every supported pick category, competitive windows, and 120 prioritized trade recommendations.
- Fixed active-Front-Office bias in league comparisons by evaluating every franchise against the same cached market-backed calibration context.
- Removed a stale duplicate draft-pick scale from Team Intelligence and reused the canonical pick evaluator.
- Corrected elite-asset counts and prevented older low-value players from receiving a developmental label.
- Expanded the permanent golden benchmark from 50 to 82 player, pick, archetype, team-window, and trade-package scenarios.

## v1.5.9 - Valuation Calibration

- Added one explainable player calibration boundary that blends independent DTOS intrinsic value with normalized, confidence-weighted market consensus.
- Corrected roster grades, tiers, positional ranks, contender/rebuilder values, and Trade Intelligence to consume the calibrated value without duplicating provider logic.
- Rebalanced draft-pick rounds and disclosed slot adjustments so low-value pick bundles cannot impersonate premium assets.
- Added a permanent 50-asset golden calibration set spanning every player tier and representative rookie-pick slots.

## v1.5.8 - Matchup Performance

- Prepared provider market distributions once per evaluation instead of rebuilding and scanning them for every player quote.
- Replaced linear percentile counting with equivalent binary-search lookups over the prepared immutable distribution.
- Preserved matchup projections, player values, market normalization formulas, ordering, request isolation, and historical behavior.
- Added equivalence, work-reduction, concurrency, and request-isolation regression coverage.

## v1.5.7 - Historical Recovery

- Classified interrupted HTTP response reads as retryable transport failures under the existing bounded four-attempt policy.
- Added path-aware retry logging while preserving the original exception when all attempts fail.
- Resume foundation imports by skipping completed season checkpoints and replaying only incomplete seasons through immutable duplicate-safe record keys.
- Distinguished preseason 2026 weekly, matchup, transaction, trade, and player data as pending instead of unsupported or failed.
- Reconciled a fresh real-provider import to 30,051 records; consecutive recovery runs produced no duplicate rows or identities.

## v1.5.6 - Deployment Readiness

- Separated lightweight process liveness from cached-data readiness with dedicated `/health/live` and `/health/ready` probes.
- Added a configurable cached-deployment maintenance delay so first requests do not compete with synchronization and historical backfill startup.
- Added opt-in request timing and process-uptime response headers for deployment diagnosis without changing normal responses.
- Added lifecycle, readiness, diagnostics, failure-state, and canonical HTTP smoke regression coverage.

## v1.5.5 - Production Request Latency

- Removed redundant Trade Intelligence package valuations from cold Commissioner Desk requests by valuing each eligible combination once.
- Deferred trade guardrail evaluation until after the existing balance filter and reused the already-calculated package values.
- Preserved proposal selection, ordering, guardrails, matchup request isolation, and serialized trade output.
- Reduced the populated-league cold homepage model from approximately 4.49 seconds to 1.04 seconds locally.

## v1.5.2 - Initial Backfill Performance

- Changed bounded historical record batches to use one SQLite transaction per batch instead of one transaction per record.
- Reduced a measured 30,051-record empty-database backfill from 468 seconds to 29 seconds while preserving immutable record keys, checkpoints, leases, and idempotency.
- Added regression coverage for bounded transaction count and duplicate-safe batch replays.

## v1.5.1 - Historical Data Reliability & Player Data Enrichment

- Added persistent import jobs, per-season/data-type checkpoints, database leases, bounded provider retries, stalled-worker recovery, and deterministic completeness reporting.
- Added an approved nflverse CC-BY-4.0 adapter for free weekly raw player statistics with stable-ID reconciliation and explicit metric availability.
- Added versioned raw-stat and league-specific fantasy scoring records without conflating missing values with observed zero.
- Added read-only completeness, provider, stats, fantasy, availability, aggregate, signal, and player-quality APIs plus import monitoring on League History.
- Added reliability, restart, locking, retry, scoring, normalization, enrichment, idempotency, and API regressions.

## v1.5.0 - Historical League Memory & Player Performance Intelligence

- Added an indexed, versioned, append-only SQLite historical evidence store with migrations, stable dimensions, provenance, availability, confidence, and model versions.
- Added resumable and idempotent Sleeper season backfills for league settings, franchise identity, weekly rosters, matchups, standings, playoffs, drafts, transactions, trades, and observed player points.
- Added current-sync valuation, roster, Team Intelligence, and prediction snapshots without overwriting earlier observations.
- Added deterministic player production aggregation, season-specific scoring recalculation, conservative role signals, explicit usage gaps, and data-quality reporting.
- Added paginated historical crawl endpoints plus minimal League, Team, and Player History views.
- Added focused identity, rename, idempotency, checkpoint, scoring, usage, aggregation, and historical API regressions.

## v1.4.5 - League Intelligence & Team Grading

- Added league-relative grades, ranks, percentiles, confidence, and explanations across 13 team categories.
- Added one reusable Team Intelligence Card consumed by team, homepage, league, Front Office, and crawl surfaces.
- Standardized competitive windows to six mutually exclusive classifications.
- Replaced meaningless 0–0 standings presentation with preseason projected order.
- Corrected canonical 0–1000 player values before roster-level 0–100 scoring.
- Added deterministic homepage league summaries and 12 focused grading regressions.

## v1.4.4 - Valuation Calibration and Trade Safety

- Added a shared canonical 0–1000 valuation layer for players, picks, consensus, and trade packages.
- Added provider-specific normalization with raw-value preservation, freshness, confidence, and method versioning.
- Added calibrated market consensus, Player Intelligence Cards, explicit calibration states, and cautious recommendation language.
- Added package-quality adjustments and guardrails for market floors, elite consolidation, low-value aggregation, and superflex quarterbacks.
- Added concise valuation summaries and schema versioning to public crawl responses without removing existing fields.
- Added 20 focused valuation and trade-safety regressions, including the 50-vs-7500 mismatch and two-thirds-for-a-premium-QB cases.

## v1.4.3 - Public Crawl API

- Added a lightweight public crawl index, consolidated snapshot, and section-specific JSON endpoints backed by synchronized DTOS data.
- Added safe league selection, pagination and filtering, strict public serialization, explicit JSON errors, and cross-origin read access.
- Reused the shared intelligence cache with per-sync namespaces, serialized cache creation, stale-data continuity, and sync-driven invalidation.
- Added `robots.txt` and a public-page-only XML sitemap for `https://dtos.onrender.com`.
- Added regression coverage for discovery, snapshots, every section, cache reuse and invalidation, league selection, empty data, sensitive fields, robots, and sitemap behavior.

## v1.4.2 - Provider Data Flow Activation

- Activated cached, attributed FantasyCalc and DynastyProcess public market ingestion with canonical Sleeper-ID reconciliation.
- Added isolated provider refresh status, record counts, timestamps, next-refresh schedules, recovery, and disclosed cached fallback.
- Completed player-page market, trend, Sleeper metadata, depth-chart, ownership, transaction, and trending data flow.
- Replaced generic unavailable states in the player workflow with provider-specific explanations and disabled unsupported sources.
- Added regression coverage for empty, partial, failed, recovered, and successful provider responses plus end-to-end consensus and player context.

## v1.4.1 - Provider Activation & Data Normalization Platform

- Added mandatory player identity and provider normalization contracts for names, IDs, teams, positions, values, rankings, ADP, timestamps, confidence, and metadata reconciliation.
- Added observable provider reliability scoring and freshness-, reliability-, agreement-, and coverage-aware consensus weighting.
- Activated official Sleeper trending add/drop ingestion alongside existing league, player, roster, transaction, trade, matchup, and metadata synchronization.
- Added normalized player intelligence APIs and live player-page market sections with provider values, confidence, freshness, availability, licensing, and explicit unavailable reasons.
- Expanded Settings into a Provider Activation Dashboard with reliability, failures, licensing, schedules, and missing configuration.
- Added regression coverage for identity resolution, normalization, invalid values, reliability, weighted consensus, player APIs, availability, deterministic outputs, and engine boundaries.

## v1.4.0 - Live Data Platform & Market Integration

- Added a unified external-data platform with a public provider SDK, dynamic registry, licensing-aware configuration, refresh scheduling, isolated cache namespaces, durable historical snapshots, health reporting, and deterministic fallback states.
- Added source-preserving robust consensus, confidence, disagreement, bullish/bearish source, quality, and 7-day through lifetime trend contracts.
- Registered Sleeper, dynasty-market, rankings, ADP, and news provider capabilities with transparent disabled states where approved access is not configured.
- Routed Market Intelligence and Sleeper HTTP transport through the Data Platform boundary while preserving Intelligence Orchestrator behavior.
- Added standardized provider, health, data, history, trend, consensus, and on-demand refresh API endpoints plus a Provider Health table on Settings.
- Added deterministic structured news interpretation and regression coverage for registration, refresh, storage, consensus, trend, outages, rate limits, licensing, fallback, determinism, and architecture boundaries.

## v1.3.0 - League Intelligence Engine v1

- Added deterministic league-wide needs, surpluses, directions, asset availability, market mapping, positional economy, and pairwise trade-compatibility analysis.
- Added evidence-backed GM profiles and team reports derived only from observable fantasy-football data, with neutral unavailable states for unsupported behavior metrics.
- Added prioritized league opportunity and complete trade recommendation contracts that preserve separate current, future, lineup, risk, market, and negotiation impacts.
- Added a League Opportunity Dashboard to the Commissioner Desk and additive League Intelligence output to the unified intelligence API.
- Extended Roster Intelligence with reusable league-wide room, player, and construction metrics so League Intelligence consumes shared evaluations instead of duplicating them.
- Added regression coverage for quality-based needs, evidence-backed surpluses, deterministic compatibility, economy, availability, GM evidence, opportunities, dashboard integration, and architecture boundaries.

## v1.2.0 - Player Value & Projection Integration v1

- Added shared, contextual player-value profiles that keep DTOS dynasty, market consensus, contender, rebuilder, current-season, positional, replacement-adjusted, and liquidity values independent.
- Added registry-backed weekly projection and production contracts with league-scoring awareness and explicit live, cached, fallback, and unavailable states.
- Added roster-specific lineup roles, points above replacement/current starter, positional scarcity/ranks, market posture, evidence, freshness, and portrait fallbacks.
- Integrated player values into player dossiers, Roster Intelligence, weekly matchups, Trade Intelligence, unified APIs, and multidimensional league rankings.
- Added regression coverage for scoring settings, provider states, replacement value, team context, matchup aggregation, trade horizons, portrait fallback, determinism, and architecture boundaries.

## v1.1.0 - Roster Intelligence Engine v1

- Replaced position-count grading with quality-first room evaluations built from shared Asset, Market, Decision, and league context.
- Added independent position-room dimensions, elite asset tiers, league-relative positional advantages, and explainable reasoning.
- Added deterministic roster construction metrics, team identities, enhanced Team HQ player cards, and championship/future window widgets.
- Added regression coverage for elite-but-thin rooms, deep replacement rooms, identities, consistency, integration, and explainability.

Notable DTOS changes are recorded here from the repository's Git history.

## v1.0.0 - 2026-07-21

- Stabilized Decision, Asset, Trade, Front Office, and Market Intelligence behind the single Intelligence Orchestrator boundary.
- Added validated production configuration with preserved environment overrides and configurable intelligence/market cache TTLs.
- Added structured JSON logging, request correlation IDs, request/error/runtime metrics, startup timing, and expanded health reporting.
- Added a single permanent release-validation entry point covering documentation, architecture, whitespace, compilation, lint, dependencies, regression tests, routes, OpenAPI, HTTP smoke tests, and process cleanup.
- Added production-readiness, large-league, cache-performance, configuration, observability, documentation, and architecture regression coverage.
- Froze and documented v1 public APIs, compatibility guarantees, and deprecation policy.
- Completed installation, architecture, developer, deployment, configuration, validation, API, market-provider, caching, release, contribution, troubleshooting, versioning, readiness, and validation-report documentation.
- Added updated architecture diagrams, production-readiness checklist, and post-release v1.1 roadmap.
- Updated application metadata to DTOS v1.0.0, build 1000, codename Front Office Operating System.

## v0.9.9 - 2026-07-21

- Added Market Intelligence as a fifth provider behind the unified Intelligence Orchestrator.
- Added replaceable FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess adapters with explicit missing-provider behavior.
- Added robust market consensus, agreement, dispersion, confidence, intrinsic-versus-market value gaps, opportunity discovery, and explainable evidence.
- Added persistent-capable provider snapshot history with 7-day, 30-day, season, and career trends, momentum, volatility, and confidence drift.
- Added execution-mode-aware provider caching, explicit cached fallback, freshness and age reporting, invalidation, provider health, and offline isolation.
- Enriched player dossiers and Trade Dossiers with provider-backed market context while preserving DTOS intrinsic evaluations.
- Extended `/api/intelligence` and `/api/platform/health` with backward-compatible market output.
- Added provider, consensus, outlier, value-gap, trend, history, cache, offline, recovery, health, and cross-engine regression coverage.
- Updated application metadata to DTOS v0.9.9, build 909, codename Market Intelligence v1.

## v0.9.8 - 2026-07-21

- Added the unified Intelligence Orchestrator, shared request context, provider registry, timed pipeline, and one final recommendation contract.
- Combined Decision, Asset, Trade, and Front Office evidence with explicit conflict resolution, counterarguments, assumptions, change conditions, and centralized confidence.
- Added shared TTL caching for league decisions, asset portfolios, Front Office profiles, trade evaluations, and final results, including refresh invalidation and health metrics.
- Added `/api/intelligence` and `/api/platform/health` without changing existing API contracts.
- Updated Commissioner Desk, Team Headquarters, Trade Center, and Front Office services to reuse the same orchestration result.
- Promoted route, OpenAPI, lifecycle, process, smoke, and release validation behind `src/platform/validation/`.
- Added cross-engine, API compatibility, cache, performance, health, and validation-platform regression tests.
- Updated application metadata to DTOS v0.9.8, build 908, codename Intelligence Integration Platform v1.

## v0.9.7 - 2026-07-21

- Added centralized Front Office Intelligence profiles derived only from observable cached fantasy-football actions.
- Added deterministic competitive windows, organizational philosophies, activity profiles, negotiation styles, asset preferences, evidence, confidence, and explicit sparse-data defaults.
- Added pairwise Trade Compatibility, conservative Negotiation Forecasts, and an informational league relationship graph.
- Updated Trade Intelligence to consume shared Front Office Intelligence rather than maintaining duplicate partner logic.
- Added Front Office dossiers at `/front-offices` and a stable `/api/front-offices` contract, with Commissioner Desk navigation and Team Headquarters integration.
- Added privacy and fairness boundaries prohibiting personal-trait inference and unsupported manager judgments.
- Added focused behavioral, integration, relationship, probability-threshold, and API/page contract tests.
- Updated application metadata to DTOS v0.9.7, build 907, codename Front Office Intelligence v1.

## v0.9.6 - 2026-07-21

- Added a centralized Trade Intelligence module that consumes Decision Engine and Asset Intelligence outputs without duplicating their evaluations.
- Added deterministic partner compatibility, balanced package generation, contextual trade impacts, opportunity prioritization, and negotiation guardrails.
- Added support for 1-for-1, 2-for-1, 3-for-2, player-plus-pick, pick-package, and multi-asset proposal structures.
- Added explainable Trade Dossiers covering both sides, current and future impact, risk, evidence, alternatives, fallback, counter, and walk-away guidance.
- Added the read-only Trade Intelligence Center at `/trades` and a stable `/api/trades` contract.
- Connected Team Headquarters and shared navigation to Trade Intelligence.
- Added focused tests for package realism, evidence, engine reuse, API/page parity, and contextual evaluation.
- Updated application metadata to DTOS v0.9.6, build 906, codename Trade Intelligence v1.

## v0.9.5 - 2026-07-20

- Added a centralized Asset Intelligence module as the shared source of player and draft-pick evaluations.
- Added contextual player dossiers with independent Dynasty, Redraft, Market, and Team Fit values.
- Added traceable evidence, explicit confidence, limitations, risk, opportunity horizons, conservative archetypes, and contextual recommendations.
- Added deterministic draft-pick value, uncertainty, expected range, time horizon, and strategic recommendation reports.
- Updated player pages and the draft-pick ledger with collapsed supporting evidence while preserving the existing visual system.
- Added a canonical cached `/api/players` dossier index and optional lightweight player inclusion in `/api/league`.
- Replaced Decision Engine player and pick heuristics with Asset Intelligence portfolio adapters.
- Added focused Asset Intelligence contract tests and architecture documentation.
- Updated application metadata to DTOS v0.9.5, build 905, codename Asset Intelligence v1.

## v0.9.4 - 2026-07-20

- Added a centralized, reusable Decision Engine with typed context, profile, evaluation, team-window, and recommendation contracts.
- Separated Current Championship Outlook from Future Outlook and added independent Depth and Asset Health evaluations.
- Added deterministic positional depth analysis, five competitive-window classifications, and contextual recommendation categories.
- Standardized recommendation priority, confidence, metrics, collapsed reasoning, and future explanation hooks across DTOS.
- Connected Commissioner Desk and Team Headquarters intelligence surfaces to the shared engine without redesigning either page.
- Replaced the ambiguous overall team grade with a clearly scoped Roster Construction grade.
- Added Decision Philosophy documentation and focused engine contract tests.
- Updated application metadata to DTOS v0.9.4, build 904, codename Decision Engine v1.

## v0.9.3 - 2026-07-20

- Replaced the homepage with the Commissioner Desk executive briefing organized around what changed, what matters, and what to do.
- Added extensible Active League and Active Front Office models, selectors, URL state, and browser-local persistence.
- Added deterministic daily briefings, evidence-backed league headlines, personalized Front Office summaries, explainable prioritized recommendations, league intelligence, and expandable league snapshots.
- Added reusable Commissioner models, services, and presentation components with future intelligence hooks.
- Removed the hardcoded league identity from shared application chrome and added league-personality extension points.
- Added `docs/CommissionerDesk.md`, expanded the README, and added targeted Commissioner Desk tests.
- Updated application metadata to DTOS v0.9.3, build 903, codename Commissioner Desk.

## v0.9.2 - 2026-07-20

- Rebuilt every franchise detail page as a responsive Team Headquarters with front-office identity, assets, performance, roster rooms, draft capital, recent activity, future outlook, and quick actions.
- Added deterministic, explainable roster-construction grades for core positions, youth, depth, draft capital, flexibility, and the overall team.
- Added objective Front Office Summaries that disclose missing data and avoid speculative player-value or competitive claims.
- Added reusable Team Headquarters calculation and view-model services plus targeted unit tests.
- Added `DTOS_PHILOSOPHY.md` to establish evidence-first, transparent, deterministic standards for future intelligence systems.
- Updated application metadata to DTOS v0.9.2, build 902, codename Team Headquarters.

## v0.9.1 - 2026-07-20

- Rebuilt the Transactions page as a responsive Front Office dashboard with activity summaries.
- Added cached filtering by team, owner, transaction type, player, draft-pick involvement, date range, and search text.
- Added sortable transaction columns, configurable pagination, team links, player transaction pages, position badges, asset movement details, and preserved raw Sleeper payload access.
- Added transaction-only Sleeper synchronization with preserved filter state, last-successful-refresh reporting, and graceful failure handling.
- Added a dedicated transaction business-logic service and targeted unit tests.
- Updated application metadata to DTOS v0.9.1, build 901, codename Transactions Center.

## v0.9.0 - 2026-07-20

- Completed the Settings migration into `routes/settings.py`.
- Moved health, API, and synchronization endpoints into `routes/api.py` so `dtos_app.py` remains focused on application setup and router registration.
- Centralized application name, version, build number, and release codename in `app_metadata.py`.
- Added DTOS version, build, Git branch, and latest commit information to the Settings page.
- Cleaned and reorganized `dtos_app.py` without changing existing endpoint behavior.
- Made the default cache location portable across Linux and Windows.

## v0.8.9 - 2026-07-20

- Moved the Draft Picks page from `dtos_app.py` into a dependency-injected router in `routes/draft.py`.
- Registered the Draft router with the FastAPI application while preserving the existing `/picks` endpoint behavior.

## v0.8.8 - 2026-07-20

- Moved transaction history rendering from `dtos_app.py` into `routes/transactions.py`.
- Registered the Transactions router through the shared application dependencies.
- Refreshed the repository's packaged DTOS archive.

## v0.8.7 - 2026-07-20

- Moved the Front Office HQ dashboard from `dtos_app.py` into `routes/hq.py`.
- Registered the HQ router through the shared application dependencies.

## v0.8.6 - 2026-07-19

- Moved team list and team detail routes from `dtos_app.py` into `routes/teams.py`.
- Registered the Teams router through the shared application dependencies.
- Added a packaged v0.8.5 archive to the repository at that point in history.

## v0.8.5 - 2026-07-19

- Moved matchup list and matchup detail routes from `dtos_app.py` into `routes/matchups.py`.
- Registered the Matchups router through the shared application dependencies.
- Added a packaged DTOS archive to the repository.
# v1.7.1 - Automated Market Calibration Dashboard

- Added full-universe, category-level market calibration audits after provider refreshes.
- Added explainable recommendations, impact scoring, safety-gated automatic model adjustments, and retained calibration history.
- Added calibration dashboard and status, category, recommendation, and history APIs.
- Preserved independent DTOS intrinsic valuation; market consensus remains evidence rather than authority.
# DTOS Changelog

## v1.7.4 - Brain Integration & Unified Decision Engine

- Established `BrainService` as the public, cached source for canonical valuation layers, evidence quality, explanations, diagnostics, and timelines.
- Migrated application intelligence consumers through the Intelligence Orchestrator and added explainable Decision Confidence.
- Added Brain health, migration, asset, timeline, dashboard, and DINS inspection contracts.
- Retained the v1.7.3 valuation APIs as backwards-compatible adapters and added permanent cross-consumer consistency tests.
# v1.10.0 - Live Projection Intelligence & Forward Production Engine

- Added one persisted canonical projection snapshot used by Brain and matchup intelligence.
- Added league-scoring-aware forward production, immutable snapshots, provider health, coverage, and accuracy foundations.
- Added read-only Projection Intelligence APIs with explicit provider provenance and no request-time provider access.
- Documented that Sleeper remains the league/roster/matchup source; no approved Sleeper projection feed was found.
# v1.10.1 - Projection Generation Production-Shape Correction

- Normalized canonical mapping- and sequence-shaped player containers without duplicate projection identities.
- Added deterministic mapping-key fallback, identity-conflict rejection, relevant-universe filtering, and coverage diagnostics.
- Added explicit generating, ready, failed, and stale health states with sanitized lifecycle errors.
