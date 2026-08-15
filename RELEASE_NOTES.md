# DTOS v1.10.23 - HistoricalStore Consumer & Writer Migration

DTOS now sources reconstructible league history from normalized Sleeper season
caches, sources permanent DTOS intelligence from sparse IntelligenceCheckpoint
records, and keeps current identities and relevant-player state in bounded
operational caches. A new compact metadata database retains system-owned cache
checkpoint and synchronization state without copying provider history.

The legacy HistoricalStore remains physically intact but is dormant. Canonical
startup, synchronization, history, FOIS, Front Office, Team HQ, dossiers, Brain,
Asset Market, inspection, and API paths no longer initialize, read, or write it.
Shadow-forbidden diagnostics expose any attempted regression. Physical deletion
and disk reclamation are explicitly deferred to v1.10.24.

## Previous release

# DTOS v1.10.22 - Resource Admission & Heavy-Work Coordination

DTOS now distinguishes verified reclaimable Linux file cache from live memory
pressure during Asset Market admission. The existing 500 MiB reserve, 1.5 GiB
effective ceiling, OOM-event rejection, and 2 GiB runtime limit remain unchanged.

One canonical heavy-work coordinator now gives an unavailable Asset Market first
priority over optional Chromium and DINS capture. Visual work remains pending and
starts after the market generation reaches a safe terminal state.

## Previous release

# DTOS v1.10.21 - Sleeper Canonical Projection Mirror

Sleeper is now DTOS's canonical weekly fantasy projection provider. DTOS scores
Sleeper projected football statistics using each league's actual scoring profile
and never fabricates positional fallback points when provider evidence is
missing. Legitimate zero projections remain distinct from unavailable evidence.

The former DTOS weekly forecast remains legacy/research-only and has zero
canonical production consumers.

## Previous release

# DTOS v1.10.20 - Intelligence Checkpoint Runtime Integration

DTOS now invokes its permanent intelligence-memory service from the canonical
Sleeper synchronization boundary. Newly observed trades, waiver adds, drops,
fantasy draft selections, and deterministic season benchmarks are captured once
with event-time provenance and unavailable evidence represented honestly.
Repeated synchronization is idempotent and ordinary read routes remain free of
checkpoint writes. NFL event triggers without a reliable canonical source remain
explicitly unconnected.

## Previous release

# DTOS v1.10.19 - Sleeper-Backed League Memory & Permanent Intelligence Checkpoints

Sleeper and external providers are now formally the source of reconstructible
facts; DTOS keeps those facts only as disposable caches. League history begins
at the actual provider-discovered Year 1 rather than a DTOS calendar cutoff.
Missing provider history is explicitly partial or unavailable and is never
fabricated or secretly filled from legacy Historical Memory.

DTOS now has a compact permanent intelligence checkpoint contract for meaningful
trade, waiver, draft, NFL-event, and scheduled observations. Checkpoints preserve
execution-time knowledge, source/model provenance, temporal confidence, and pick
lineage without daily full-universe logging or hindsight rewrites. Fresh provider
evidence remains mandatory for current Market Value. Existing Historical Memory
remains untouched and reversible.

## DTOS v1.10.18 - Multi-League Resource Observability & Storage Hygiene

DTOS v1.10.18 makes every significant Asset Market memory-admission decision
durably diagnosable without changing the admission contract. The bounded journal
records explicit decision reasons, cgroup working-set inputs, OOM deltas, browser
process counts, and sanitized lifecycle context across restart and runtime
eviction.

An explicit diagnostic operation now attributes approximate retained memory to
league runtime components without adding profiling work to normal requests.
Asset Market publication also retains exactly one manifest-selected current
artifact per league and safely removes complete stale generations only after
atomic publication. Resource health reports artifact and durable-disk pressure
with documented 20% warning and 10% critical free-space thresholds.

## Previous release

# DTOS v1.10.17 - Multi-League Consumer Integration

DTOS v1.10.17 completes the product boundary introduced by the bounded runtime
manager. An explicit league request now resolves one request-scoped canonical
context and routes crawl, projections, Brain inputs, Asset Market, FOIS,
historical reads, audits, and inspection through that exact runtime.

Secondary league history remains honestly unavailable until its own dynasty
chain is imported, and private secondary runtimes never trigger or expose Live
Visual captures. Default routes retain the configured league contract, while
concurrent A/B requests no longer depend on mutable process-global selection.

## Previous release

# DTOS v1.10.16 - Multi-League Runtime Foundation

DTOS v1.10.16 introduces a lazy league-scoped runtime boundary while preserving
the configured Day Traders league as the default. Runtime state, synchronization,
projection context, Asset Market residency, and diagnostics now have explicit
league identities rather than relying on a last-request-wins singleton contract.

The manager retains at most two warm leagues by default, hydrates a league only
when requested, collapses concurrent hydration, evicts inactive runtimes by LRU,
and releases league-scoped background and market resources. Secondary-league
import is deliberately feature-gated until enabled by deployment configuration.

Durable Historical Memory remains one normalized league-indexed database. Asset
Market artifacts and Live Inspection/Visual evidence are namespaced by league,
while full release DINS remains limited to the designated validation league.

## Previous release

# DTOS v1.10.15 — Projection Snapshot Upgrade Compatibility

DTOS v1.10.15 ensures a durable Forward Production snapshot is reused only when
its schema, model, contract, and semantic policy match the running application.
Incompatible or corrupt snapshots remain durable for diagnostics but are not
published as current intelligence. Cached canonical and Sleeper inputs produce
exactly one compatible replacement without a provider request.

Projection health now reports the running application contract separately from
the actual active and restored snapshot identities, including explicit restore,
upgrade-generation, failure, and durable-publication counters.

## Previous release

# DTOS v1.10.14 — Player-Specific Projection Calibration

DTOS v1.10.14 makes Forward Production genuinely player-specific. The model keeps
its independent raw forecast, then calibrates it using evidence strength, current
role, availability, recent production, and the cached Sleeper projection feed.
Sleeper remains external evidence rather than copied truth; strong DTOS evidence
can still support a documented disagreement.

Projection APIs and audits now expose raw and calibrated DTOS values, adjustment,
reason, confidence, fallback state, evidence depth, zero-versus-missing semantics,
and large-disagreement diagnostics. The calibrated value flows once through the
canonical Brain while Market Value, Historical Memory, FOIS history, Asset Market
lifecycle, and request-time provider boundaries remain unchanged.

## Previous release

# DTOS v1.10.13 — External Mirror Matchup Surface Classification Correction

DTOS v1.10.13 corrects the external mirror's matchup-surface classifier. One
shared strict parser now recognizes only `matchups-<numeric-id>` as a matchup
detail. The public `matchups-page` directory remains mirrorable without being
subjected to detail-only 22-starter validation.

Individual matchup validation remains unchanged and strict: two teams, 22
starters, visible Sleeper and DTOS projections, and semantic/audit reconciliation.
The mirror manifest also exposes deterministic directory-to-detail traversal for
GitHub-only inspection.

## Previous release

# DTOS v1.10.12 — Permanent External Visual Mirror

DTOS v1.10.12 permanently publishes the verified Live Product and Live Visual
Inspection state as a compact GitHub release mirror. External assistants can start
from one stable manifest, download individual current-page PNGs and semantic JSON,
and reconcile matchup projections without rendering the Render origin or downloading
the full DINS archive.

The mirror copies exact verified captures, validates PNG dimensions and SHA-256,
reconciles all matchup starters against semantic inspection and the projection audit,
and sanitizes every public JSON artifact. Core public pages inherit capture and
mirror eligibility from canonical route registration; entity-heavy pages remain
bounded representative/on-demand surfaces. Release-triggered and hourly automation
waits for matching production, Live Visual, and DINS completion before publishing.

GitHub remains inspection-only. DTOS performs no request-time GitHub calls for the
mirror, and mirror availability cannot affect canonical runtime health.

# DTOS v1.10.11 — Live Visual Inspection

DTOS now exposes current rendered product screenshots through the permanent
`/api/inspect/live/visual` contract. Every current matchup is captured at mobile
and desktop viewports from its real public route, validated against canonical
Sleeper and DTOS projections, and served anonymously as a durable PNG.

Capture work is asynchronous, single-flight, fingerprint-deduplicated, and
preserves the previous valid image after failure. Ordinary inspection requests
never launch a browser or mutate canonical application state.

See `docs/LIVE_VISUAL_INSPECTION.md` for discovery, freshness, and future-release
requirements.

## Previous release

# DTOS v1.10.10 — Universal Live Product Inspection & Matchup Projection Presentation

DTOS now has one permanent current-production inspection entry point:
`/api/inspect/live`. Public GET routes register automatically through the
canonical application router, while dynamic collections provide bounded links
for teams, matchups, relevant players, picks, seasons, FOIS, and APIs. Approved
machine/internal exclusions are explicit, and the inspection observer does not
refresh or regenerate canonical DTOS state.

Matchup starter cards now display exact Sleeper and DTOS projections alongside
actual points, with explicit unavailable states and visible partial-coverage team
totals. Semantic matchup inspection exposes displayed and canonical values for
permanent reconciliation checks.

See `docs/LIVE_PRODUCT_INSPECTION.md` for the traversal and developer contract.

## Previous release

# DTOS v1.10.9 — Projection Intelligence Audit Export

DTOS v1.10.9 adds one trustworthy, read-only view of the projection and
intelligence numbers already used by the application. The JSON export at
`/api/audit/projections/current` and its player-oriented CSV companion expose
current matchup starters, projection differences, team reconciliation,
valuation layers, FOIS context, provider diagnostics, and canonical snapshot
identities without triggering synchronization or recalculation.

See `docs/PROJECTION_INTELLIGENCE_AUDIT.md` for the contract and audit-only
difference thresholds.

## Previous release

# DTOS v1.10.7 — Freshness Semantic Threshold Correction

DTOS v1.10.7 makes evidence age semantically stepwise. Exact age remains
observable, but Brain output changes only at documented evidence-family quality
boundaries. Same-tier provider refreshes now retain the canonical Brain and
compatible Asset Market generation; meaningful threshold crossings still
propagate exactly once.

The policy distinguishes time-sensitive projections, slower dynasty-market
evidence, league transaction evidence, performance data, and immutable
historical facts. It is versioned as freshness policy 2.0.

## Previous release

DTOS v1.10.6 introduced bounded Brain input manifests and early semantic
candidate comparison.

DTOS now distinguishes raw provider-observation age from the derived Brain
opinion. A periodic refresh that advances `freshness_age_hours` without changing
confidence, reliability, evidence weight, score, rank, or valuation retains the
published Brain and compatible Asset Market generation. Once staleness becomes
material to those derived outputs, normal semantic publication still occurs.

Compact input-family fingerprints and bounded changed-asset diagnostics make
future semantic differences attributable without exposing raw datasets.

## Previous release

# DTOS v1.10.5 — Projection Semantic Compatibility Correction

DTOS now treats semantically identical restored and freshly observed projection
state as one canonical generation. Nested observation timestamps, transport
latency, request counters, and restore metadata no longer invalidate the Brain or
its durable Asset Market artifact. Stable values, confidence, evidence,
ownership, ordering, and provider dependencies remain strict semantic inputs.

Equivalent background refreshes retain the existing Brain report and market
generation; material projection or valuation changes still publish exactly once.
Projection, Brain, and Asset Market health expose compact semantic diagnostics
and explicit change/no-change counters.

## Previous release

# DTOS v1.10.4 — Durable Projection & Asset Market Restoration

DTOS restores the last valid Projection Intelligence snapshot and compatible
Asset Market artifact from durable storage before background refresh. Original
freshness timestamps and semantic identities survive restart, while bounded
manifests and recovery preserve atomic publication.

## Previous release

# DTOS v1.10.3 — Sleeper Projection Provider Redirect Correction

DTOS now safely follows the single relative redirect used by Sleeper's optional,
undocumented projection service. The policy is scoped only to this provider,
permits at most three HTTPS redirects to allowlisted Sleeper API hosts, rejects
loops, missing locations, insecure downgrades, and host escape, and exposes only
sanitized transport diagnostics.

The projection parser, scoring conversion, consensus model, Brain, valuation,
FOIS, Matchups, historical contracts, and shared HTTP client are unchanged.

## Previous release

# DTOS v1.10.2 — Sleeper Projection Sync & System-Wide Forward Intelligence

DTOS now treats Sleeper's undocumented bulk weekly projection service as optional
external evidence. Background synchronization retrieves one bounded weekly data
set, validates its schema and identities, converts projected statistics with the
league's scoring rules, fingerprints semantic content, and persists immutable
last-valid evidence. Feed failure never blocks readiness or erases DTOS's own
Forward Production model.

Player and matchup contracts distinguish **Sleeper Projection**, **DTOS
Projection**, and the bounded **DTOS Consensus Projection**. Source-pure team
totals disclose starter coverage; the canonical Brain continues to consume one
Projection Intelligence snapshot. Identical feed content causes no downstream
regeneration.

The Sleeper projection interface is undocumented and may change or disappear.
DTOS therefore classifies it as “Sleeper Unofficial Projection Feed — Optional
External Evidence,” provides a kill switch, retains stale evidence safely, and
continues independently when it is unavailable.

## Previous release

# DTOS v1.10.1 — Projection Generation Production-Shape Correction

DTOS now accepts the canonical production player mapping as well as sequence
fixtures when generating Forward Production. Mapping keys safely supply missing
player IDs, conflicting identities fail closed, roster duplicates are collapsed,
and projection health exposes sanitized failure and recovery state.

No projection formula, valuation weight, provider attribution, or matchup logic
changed. Sleeper remains the canonical league/roster/matchup source, while
projections remain attributed to the DTOS Forward Production Model.

## Previous release

### DTOS v1.10.0 — Live Projection Intelligence & Forward Production Engine

DTOS now persists a canonical Forward Production snapshot and reuses it across
Brain decisions, player valuation profiles, and Matchups. Projection evidence is
league-scoring aware, immutable, freshness-labelled, and failure-isolated.

Sleeper's documented public API does not expose an approved projection feed.
Sleeper therefore remains DTOS's canonical league, roster, matchup, identity,
transaction, draft, and NFL-state source. Projections are explicitly attributed
to the DTOS Forward Production Model; they are never called Sleeper projections.

Read-only endpoints are available at `/api/projections`, `/api/projections/health`,
`/api/projections/providers`, `/api/projections/players/{player_id}`, and
`/api/projections/weeks/{week}`. No endpoint performs external provider work.

## Previous release

### DTOS v1.9.6 — Historical Player Leaders Query Optimization

DTOS v1.9.6 removes the final cold History bottleneck by using a measured
season-scoped player aggregation index and one bounded canonical identity query.
Historical totals, names, positions, ordering, presentation, progress, FOIS,
valuation, and Asset Market behavior remain unchanged.

## Previous release

# DTOS v1.9.5 — History Read-Path Performance

DTOS v1.9.5 makes season History pages responsive by building only the requested
section, offloading database-backed read-model work from the event loop, and
aggregating player leaders in a bounded SQL query. It preserves the v1.9.4
historical evidence, schemas, ordering, provenance, canonical `5/6` progress,
valuation behavior, and FOIS model unchanged.

## Previous release

# DTOS v1.9.4 — Valuation, FOIS & League History Corrections

DTOS v1.9.4 completes independent intrinsic, contender, and rebuilder valuation
layers for supported active assets, corrects the FOIS centered-score calibration
without conflating score and confidence, and adds provider-free year-level league
archives backed by immutable Historical Memory. Unsupported layers retain honest
evidence limitations, prior FOIS snapshots retain their model versions, and the
active 2026 season remains explicitly current rather than final.

## Previous release

# DTOS v1.9.3 — Asset Market Restart Lifecycle Correction

DTOS now deterministically schedules one background Asset Market build when startup or restart finishes without a compatible durable artifact. The correction closes an orchestration hole where the market could become eligible while remaining model-less and idle. It does not change valuation, Historical Memory, FOIS, or v1.9.2 presentation behavior.

## Previous release

### v1.9.2 — Intelligence Presentation & Data Utilization

DTOS now turns more existing Brain, FOIS, Asset Market, and Historical Memory evidence into readable product guidance. Human-facing pages lead with names, ranks, values, confidence, availability, and outcomes; technical provenance remains accessible without replacing the decision meaning. This release does not add an intelligence engine or change canonical valuation behavior.

## Previous release

### v1.9.1 — FOIS Presentation Contract Correction

DTOS v1.9.1 completes the public presentation contract for the Front Office Intelligence System introduced in v1.9.0. The `/fois` page now uses the shared DTOS page header, selects the active loaded league when no query parameter is supplied, presents persisted executive profiles, and provides a functional GM Rankings action.

The release does not change FOIS scores, evidence, model outputs, persistence, startup scheduling, Historical Memory, or Asset Market behavior. Explicit unavailable leagues and genuinely missing or pending FOIS data remain honest, distinct states.

## Validation focus

- Shared page-header and primary-action contracts at desktop, tablet, and mobile.
- Canonical loaded-league selection and explicit valid-league override.
- Ten persisted production GM profiles visible without a league query parameter.
- FOIS output equivalence and v1.9.0 startup-correction preservation.

## Previous release

# DTOS v1.9.0 — FOIS General Manager Intelligence System

DTOS now evaluates the executive responsible for a franchise during a specific
tenure—not merely the current team. FOIS separates results, decision process,
context, and recovery; keeps GM quality distinct from current team quality; and
uses the canonical Brain, Competitive Window, Asset Universe, Relevant Player
Universe, and immutable Historical Memory as evidence sources.

Versioned tenure identities and takeover snapshots prevent new owners from
inheriting prior-owner decisions or scores. Full-history evaluation has no hard
ten-year cap. Trading, roster construction, drafting, Results, confidence,
completeness, evidence provenance, Executive Profiles, resumes, comparisons, and
franchise GM history are available through persisted read-only FOIS contracts.
Missing evidence remains visibly unavailable rather than becoming a failing grade.

## Previous release: v1.8.15

# DTOS v1.8.15 - Relevant Player Universe

DTOS now retains active model state only for players relevant to imported league history, current ownership, or the top 150 available canonical free agents. Every retained player carries explicit reason codes, while retired and former players required by immutable evidence remain directly discoverable. The durable migration derives membership from existing history without replaying providers or changing historical events, checkpoints, provenance, or the canonical 5/6 progress contract.

## Previous release: v1.8.14

# DTOS v1.8.14 - Deterministic Asset Market Restart Lifecycle

DTOS v1.8.14 makes Asset Market restart behavior a single deterministic lifecycle. The application now completes one canonical startup epoch before it evaluates durable market artifacts or permits market construction. A compatible artifact loads once without reconstruction; incompatible, corrupt, incomplete, and missing candidates retain distinct diagnostics.

The release also prevents request freshness and delayed deployment maintenance from creating duplicate startup-adjacent synchronizations. Normal periodic refresh begins after the startup epoch and continues to publish exactly one safe replacement when semantic market inputs genuinely change. Existing memory, backoff, historical `5/6`, dataset-scope, provider-free read, and output contracts are unchanged.

## Previous release: v1.8.13

DTOS v1.8.13 closes the production-scale retained-memory gap exposed when historical coverage and Asset Market reads run against the complete durable database shape. The release adds bounded combined-read diagnostics and preserves every existing output, historical record, memory ceiling, reserve, and provider-free read contract.

---

# DTOS v1.8.12 — Cgroup-Aware Market Memory Admission

DTOS v1.8.12 corrects Asset Market memory admission under Linux cgroup v2. It subtracts only validated reclaimable `inactive_file` cache from `memory.current`, retains all existing hard limits and reserves, and fails conservatively when metrics are unavailable or inconsistent. Generation-aware backoff prevents repeated polling from launching identical rejected builds while preserving safe retries after time, input changes, or meaningful memory improvement.

The release does not change market calculations, historical data, infrastructure, or public product output.

---

# DTOS v1.8.11 — Retained Asset Market Summary Contract

DTOS v1.8.11 makes `/api/market` a bounded metadata-only summary that returns retained lifecycle, availability, generation, provenance, historical progress, and subresource links without constructing or loading an Asset Market model. It remains HTTP 200 during cold startup, warming, replacement, and safely failed replacement states.

Directory routes keep their established bounded-warming behavior. Search and detail remain `live_store`; retained directory, health, and artifact metadata remain `artifact_build`. No provider, SQLite, artifact, digest, or historical work was added to the summary route.

---

# DTOS v1.8.10 — Asset Market Health Dataset Scope

DTOS v1.8.10 completes the Asset Market historical provenance contract by exposing `historical_dataset_version_scope: artifact_build` wherever market health exposes a retained artifact dataset version. The version and scope are published atomically with the active model and remain consistent through compatible restart loading, non-semantic reuse, replacement warming, and failed publication.

Search and asset-detail responses continue to expose current `live_store` history. Directory and retained-artifact responses remain `artifact_build`. This correction adds no request-thread database work, provider synchronization, archive scanning, semantic invalidation, or market-output changes.

---

# DTOS v1.8.6 — Asynchronous Market Generation

DTOS v1.8.6 removes archive-wide durable-generation preparation from cold Asset Market request execution. The first request now claims one process-local background worker using retained in-memory lifecycle state and immediately returns the canonical retryable warming response.

The worker performs database UUID lookup, historical dataset calculation, identity archive aggregation, cache-key resolution, compatible-artifact loading, bounded construction, and atomic publication away from the event loop. Market health reports the current preparation phase, refresh state, duration, served generation, and failures without hydrating product state.

Compatible last-valid generations continue serving while a replacement is prepared. Incompatible store instances warm safely. Completed generations preserve existing rankings, ordering, Brain snapshots, valuation layers, historical provenance, serialization, and provider-free read behavior.

No infrastructure, storage, compute plan, pricing, database schema, valuation formula, ranking, or historical evidence changed.

---

# DTOS v1.8.4 — Bounded Asset Market Construction

DTOS v1.8.4 removes the production OOM path in the first cold Asset Market request. Profiling found four simultaneous universe-wide representations: full canonical valuation envelopes, compact summaries, an ID dictionary, and duplicated normalized search strings. The old builder retained roughly 260 MB locally and exceeded the 2 GB Render cgroup when added to the synchronized production baseline.

The market now streams canonical assets directly into an atomic, versioned SQLite read model on the existing durable storage. Directory filtering, ordering, and pagination run in SQL before JSON hydration; search uses the indexed compact representation; expanded dossiers hydrate only the selected canonical asset and its history. Compatible generations survive process restarts without rebuilding.

Cold requests start one bounded background build and receive an explicit retryable warming response. A cgroup-aware guard checks available construction budget before and between stages and defers safely rather than risking worker termination. Market health remains metadata-only.

No market formulas, public schemas, ordering, Brain snapshots, valuation layers, historical evidence, provider behavior, infrastructure, or pricing changed.

---

# DTOS v1.8.3 — Production Memory Lifecycle

DTOS v1.8.3 coordinates its largest in-process memory phases instead of allowing their peaks to overlap. Initial Sleeper synchronization and cache persistence finish before historical backfill begins, and cold Asset Market construction is deferred while synchronization, valuation, persistence, or historical work is active.

`/api/market/health` is now a metadata-only readiness surface. It reports retained generation, count, build, cache, lifecycle, and bounded memory information without constructing a market model or triggering providers, Brain evaluation, historical hydration, or synchronization. Ordinary warm reads remain lock-light, and a last-valid market remains available during unsafe rebuild windows.

Cache persistence now incrementally encodes JSON to a same-directory temporary file, flushes and synchronizes it, and atomically replaces the prior cache only after success. Failed writes retain the previous valid cache and remove temporary artifacts.

The lifecycle coordinator records bounded process RSS, virtual memory, system availability, and Linux cgroup current/limit values at phase boundaries. It never publishes host paths, database identities, secrets, or raw payloads.

No Asset Market formulas, rankings, canonical Brain snapshots, historical outputs, provider behavior, infrastructure, or pricing changed in this release.

# DTOS v1.8.2 — Asset Market Query Performance

DTOS v1.8.2 removes repeated aggregate database work from warm Asset Market reads. HistoricalStore now computes each league's canonical dataset identity once under concurrency and invalidates it only after a successful committed evidence, identity, quality, migration, or repair change. Durable database UUIDs continue detecting same-path database replacement without exposing private storage details.

Asset Market search retains normalized compact documents at model construction. Current players, structured filters, empty searches, future picks, free agents, and no-result queries remain inside the compact index; retained historical aliases provide former-player discovery without constructing full dossiers or recommendations.

Historical Graph player dossiers now use a bounded dataset-versioned LRU with single-flight first construction. Repeated expansion preserves byte-equivalent canonical history, Brain identity, recommendation provenance, and API contracts while avoiding repeated ownership, season-summary, and positional preparation.

---

# DTOS v1.8.1 — Asset Market Cache Stability

DTOS v1.8.1 corrects the production performance blocker discovered after v1.8.0. Instrumentation proved that ongoing enrichment changed the logical Historical Memory dataset version on every commit, causing the compact 12,331-asset market model to rebuild repeatedly even though those writes did not change its directory summaries.

HistoricalStore now owns a private random database UUID persisted inside SQLite. It remains stable across reads, writes, WAL checkpoints, vacuum-compatible maintenance, and controlled restarts, while a recreated database receives a new identity. The process cache additionally retains store-instance isolation and never exposes paths or the private UUID.

Compact market invalidation now follows only inputs that can change compact output. Historical search, detail dossiers, and response metadata continue to consume the independently versioned durable Historical Asset Graph. Current-asset searches skip historical discovery once the requested page is already satisfied.

---

# DTOS v1.8.0 — Asset Market & Dynasty Exchange

DTOS v1.8.0 introduces the Asset Market as the application’s primary destination. Players, free agents, retired players present in durable history, rookies, taxi assets, and owned draft picks are discoverable through one deterministic market contract. The Commissioner Desk remains available at `/commissioner`.

The market preserves distinct market, intrinsic, league-adjusted, contender, and rebuilder layers. It consumes existing Valuation Universe and Brain contracts instead of recalculating intelligence in routes. Missing evidence remains unavailable and is never silently replaced. Canonical Brain recommendations expose confidence, snapshot identity, evidence, and reasoning.

The read model is versioned, bounded, single-flight, and provider-sync-free. Directory pagination occurs before historical dossier hydration; player and pick history is loaded only for selected assets. Market health and DINS inspection expose dataset identity, cache state, build timing, duplicate identity checks, and read-path guarantees.

---

# DTOS v1.7.14 — Canonical Trade History Discovery

DTOS v1.7.14 makes Historical Trade Dossier discovery use the same durable Historical Memory dataset and completed-status contract as its detail routes. DINS no longer advertises current cached Sleeper transactions as historical dossiers when canonical historical evidence is absent.

Current-only transactions remain available through current Transactions and Trade surfaces. Inspection discovery records a deterministic `canonical_historical_trade_unavailable` exclusion with the durable dataset version, rather than fabricating a dossier or capturing a known 404 route.

Discovery remains read-only, bounded, deterministic, and provider-sync-free.

---

# DTOS v1.7.13 — Canonical History Progress Presentation

DTOS v1.7.13 makes the durable player-week enrichment progress contract the single presentation source for History, coverage, inspection, and DINS. Exact counters and season states remain primary; rounded percentages are secondary.

The History page now distinguishes foundation import completion from player-week enrichment. A current-season `completed_with_pending` state is presented honestly as terminal and ready with expected evidence pending, without marking the active season complete or mutating historical state.

Migration version 5 safely repairs inconsistent persisted job metadata, including the v1.7.11 `78/6` state, and records the prior value, repaired value, derivation, and season classification. The repair is idempotent and does not modify immutable evidence, record keys, provenance, leases, or batch rows.

Import diagnostics now expose completed, pending, and failed seasons with an explicit consistency flag. Foundation imports retain their established category-level progress semantics.

---

# DTOS v1.7.11 — Historical Enrichment Batch Persistence

DTOS v1.7.11 makes historical player enrichment durable and efficient on the persistent Render volume. Nflverse weekly data is consumed as bounded batches, while each batch atomically persists raw evidence, derived fantasy scoring, durable progress, and lease renewal.

Importer identity remains at version 1.2. Existing v1.7.10 record keys therefore remain canonical, completed work can be replayed safely, and logically duplicate evidence is ignored instead of rewritten.

The new migration adds durable batch-progress records without changing historical API schemas, canonical identities, provider provenance, scoring outputs, or immutable historical evidence.

---

# DTOS v1.7.10 — Durable Historical Storage

DTOS v1.7.10 makes Historical League Memory restart-safe on a single Render instance. Production now requires an explicitly mounted and writable durable-storage root; the historical database must resolve beneath that root, and startup readiness fails with a clear reason instead of creating an ephemeral substitute.

The SQLite database remains the canonical durable home for immutable records, import jobs, checkpoints, leases, heartbeats, data-quality issues, reconciliation evidence, and dataset-version inputs. First-time initialization is built beside the target and atomically installed without replacing an existing database. WAL journaling, full synchronous durability, foreign keys, and a bounded busy timeout support the single-instance deployment contract.

Historical graphs remain bounded process-local objects to avoid persisting large hydrated payloads. A small, atomic read-model manifest on the durable disk records the cache identity, dataset version, schema version, and successful generation timestamp so restarts retain deterministic rebuild provenance. Temporary Sleeper caches, provider payloads, source files, and logs remain outside the persistent disk.

---

# DTOS v1.7.9 — Historical Import Memory Stability

DTOS v1.7.9 corrects the confirmed Render OOM mechanism without changing historical contracts. Coverage statistics are calculated directly from indexed SQLite records, asset details hydrate only their relevant source rows, and global graph hydration is blocked while an import owns the write lease.

The importer fetches and persists one week at a time instead of retaining a season of raw Sleeper responses. Production-scale concurrency validation uses the retained 200 MB historical database and enforces a hard 450 MiB RSS ceiling with a target below 400 MiB.

Historical outputs, ordering, provenance, unresolved identities, leases, checkpoints, and provider-free read behavior remain unchanged.

---

## Previous release: v1.7.8 — Historical Import & Read-Model Lifecycle Stability

DTOS v1.7.8 stabilizes the production lifecycle discovered during v1.7.7 verification. Historical graph objects now start lightweight and construct only the route-specific indexes needed by asset, player, or coverage reads. Player directories use indexed identities without loading every weekly payload, player dossiers load only the requested player's weekly records, and coverage counts are aggregated directly in SQLite.

The process retains one immutable graph generation instead of two. Production-scale validation measures the entire cold-to-warm read workflow and confirms identical historical outputs without provider synchronization.

Historical import recovery now waits for a live worker heartbeat, detects bounded lease expiration, removes the stale lock atomically, requeues the interrupted job visibly, and continues from completed checkpoints with a single importer.

---

## Previous release: v1.7.7 — Historical Asset Graph Read-Path Optimization

DTOS v1.7.7 corrects the production read-path timeout discovered after v1.7.6 without changing historical outputs or synchronization behavior. A dataset-keyed read model now builds the normalized graph once per immutable history/current-identity version and reuses deterministic indexes across every historical consumer.

The cache key includes league identity, historical dataset hash, historical schema, importer, graph, player-history/calculation, read-model, and current verified identity metadata. Concurrent first reads are single-flight, only complete models are published, a failed rebuild retains the prior valid model with an explicit stale diagnostic, and process memory is bounded to two dataset versions.

Directory pagination occurs before dossier hydration. Player detail reads use asset, parent-transaction, player-week, season-total, trade, and pick-conversion indexes rather than reconstructing unrelated assets. Historical reads remain provider-free and never initiate Sleeper synchronization.

Diagnostics expose build/load/query durations, build count, hits/misses, dataset version, asset/event counts, hydrated-record count, last successful build/error, and approximate model size through historical coverage and directory contracts.

---

## Previous release: v1.7.6 — Historical Asset Graph & Connected Dossiers

DTOS v1.7.6 makes verified Day Traders history a connected application contract instead of an isolated report. The new Historical Asset Graph supplies stable player, pick, transaction, trade, event, and franchise identities to dossier pages, search, historical APIs, Team Headquarters, Front Office Intelligence, and the canonical Brain.

Historical ingestion now archives traded-pick snapshots and attaches source league, season, record identity, retrieval time, schema/importer versions, source hashes, provenance, and availability to normalized payloads. Completed movements can produce ownership intervals; failed and pending movements remain visible evidence but cannot change ownership.

Player season summaries retain the matching season's scoring-settings version and distinguish missing observations from zero. The active 2026 season is explicitly in progress. Historical value-at-event remains unavailable unless DTOS has a timestamped valuation snapshot; current values are never silently backdated.

New contracts include `/api/history/assets`, asset event and ownership endpoints, player historical endpoints, `/api/picks/{pick_id}`, historical Trade Dossiers, franchise history, coverage reporting, and unified `/api/search`. HTML Pick and Trade Dossiers provide corresponding connected navigation.

Known honest limitations:

- Sleeper matchup history supplies league-scored points but not lossless raw NFL stat components or historical advanced usage.
- Historical matchup payloads do not distinguish taxi and reserve assignments; those states remain explicitly unavailable unless independently sourced.
- Older or retired Sleeper IDs without verified metadata remain searchable as unresolved IDs and are never assigned guessed names.
- Value at trade remains unavailable without a contemporaneous valuation observation.

---

## Previous release: v1.7.5 — League Payload Memory Safety

This corrective release keeps `/api/league` focused on league data and a compact Brain summary. Full canonical asset intelligence and timelines remain available through `/api/brain`. The change prevents a 35 MB compatibility response from materializing the full Brain and its duplicated timeline during every request, eliminating the production memory-pressure path observed during v1.7.4 verification.

---

# DTOS v1.7.4 — Brain Integration & Unified Decision Engine

DTOS now has one public Brain boundary. Every major intelligence consumer receives the same cached asset values, evidence scores, explanations, and histories through the Intelligence Orchestrator. The release adds a distinct, explainable Decision Confidence metric, a Brain dashboard, migration diagnostics, health APIs, and DINS coverage. Existing valuation contracts remain compatible; provider calls and valuation recalculation remain outside request rendering.

## Canonical endpoints

- `/brain`
- `/api/brain`
- `/api/brain/health`
- `/api/brain/migration`
- `/api/brain/assets/{asset_id}`
- `/api/brain/timeline/{asset_id}`

---

# DTOS v1.7.3 — Valuation Intelligence Engine (DTOS Brain Phase I)

DTOS now reasons over cached multi-source evidence instead of treating provider consensus as an answer. Every canonical player and pick receives separate Coverage, Confidence, and Agreement scores, a provider/category breakdown, five independent valuation layers, a readable explanation, a bounded evidence timeline, and transparent diagnostics.

The engine is generated during background synchronization and performs no external request during page or API handling. Provider reliability, freshness, identity quality, agreement, sample size, and evidence-family lineage determine each contribution. Missing or conflicting evidence lowers confidence explicitly rather than creating false certainty.

New APIs expose evidence, per-asset reports, confidence, coverage, agreement, explanations, timelines, and diagnostics. The valuation dashboard and DINS contract now inspect the same cached intelligence model used by downstream DTOS systems.

## Previous release: v1.7.2

### Multi-Source Market Intelligence Provider Network

DTOS now treats each provider as measured evidence rather than truth. Approved FantasyCalc and DynastyProcess feeds, completed Sleeper trades, league-local behavior, nflverse historical evidence, and the independent DTOS historical model are registered with explicit purpose, lineage, licensing, freshness, coverage, and dynamic reliability. FantasyPros remains credential- and license-gated; KeepTradeCut remains unavailable because no approved integration exists.

Weighted consensus groups correlated sources into evidence families, so a derivative source cannot receive an extra independent vote. Missing, stale, unmatched, ambiguous, conflicting, or restricted evidence lowers confidence and remains visible. Ordinary application requests use a cached read model and never refresh providers. Automatic calibration remains bounded, reversible, model-level only, and now also requires sufficient multi-family coverage and a conflict-free provider network.

## Previous release

### DTOS v1.6.7 — GitHub DINS Artifact Publication Completion

DTOS v1.6.7 closes the inspection-publication gap without adding a paid service or
changing the inspected application commit. Production discovers immutable DINS
ZIP, manifest, and checksum assets directly from the matching public GitHub
Release, validates version/build/commit/schema/capture identity, and reports an
explicit publication state through the inspection API.

Generated browser artifacts remain outside Git history. The post-deployment worker
captures the exact Render commit, packages deterministic sanitized assets, uploads
them to its existing release, and production becomes complete after public identity
and checksum verification.

## Previous release

### DTOS v1.6.6 — Team Headquarters Mobile Overflow Correction

DTOS v1.6.6 is a focused production correction for a responsive defect discovered
during the complete v1.6.5 DINS audit. The Team Headquarters Core Intelligence
grid now collapses within tablet and mobile widths instead of extending beyond the
viewport. No intelligence formulas, provider behavior, or application workflows
changed.

## Previous release

### DTOS v1.6.5 — Product Design System, Navigation & Consistency

DTOS v1.6.5 unifies every major Front Office surface around a shared visual and
interaction language. Pages now state what decision they support, show fresh data
context, and lead to a clear next action. Recommendations use one explainable
contract, league-relative grades state what they mean, and mobile and keyboard
behavior share permanent primitives.

The Commissioner Desk now follows the executive sequence: what changed, what to
do, my team, league opportunities, league context, then the compact snapshot.
Preseason team cards present projections and odds instead of empty standings.

DINS records deployed commit and timestamp provenance and treats missing product
contracts, generic dynamic names, exposed internal identifiers, local artifact
URLs, and critical accessibility regressions as release failures.

No intelligence formulas, provider behavior, or cached-state semantics changed.

## Previous release

### DTOS v1.6.4 — Team Identity Normalization & Team Headquarters Polish

DTOS now presents every franchise by its canonical identity throughout Team Headquarters, Commissioner Desk, intelligence summaries, and DINS. Team Headquarters has a cleaner executive hierarchy with one competitive-window classification and one primary recommendation, while detailed evidence remains available in a collapsed disclosure.

Preseason pages now emphasize projections instead of empty results, unknown bye weeks are omitted, and unfinished controls have been removed. The tracked HTTP release validator permanently rejects rendered generic numbered team and roster fallbacks when canonical league identity is available.

---

# DTOS v1.5.5 — Production Request Latency

The Commissioner Desk now avoids repeated valuation of the same trade package
combinations. Eligible packages are valued once per proposal shape, balance
filtering occurs before guardrail evaluation, and guardrails reuse the same
canonical package values.

For the populated production-scale league fixture, cold homepage model generation
fell from approximately 4.49 seconds to 1.04 seconds locally. Proposal counts,
selection, ordering, and serialized output remain identical to v1.5.4 across all
nine trade partners.

The earlier 18.397-second production matchup observation was transient deployment
contention rather than persistent matchup behavior. Repeated v1.5.4 production
requests measured 2.636–3.003 seconds, consistent with the hosting platform's
slower CPU allocation. Matchup intelligence and caching behavior are unchanged.

---

# DTOS v1.4.5 — League Intelligence & Team Grading

Team strength is now evaluated relative to the selected league. Every franchise receives the same reusable Team Intelligence Card with overall, current, dynasty, lineup, depth, position, draft, youth, future, flexibility, and liquidity grades.

Commissioner Desk, Team Headquarters, Front Office Intelligence, League Intelligence, and public crawl APIs now share the same competitive-window vocabulary and contender totals. Before Week 1, projected order replaces misleading 0–0 standings.

See `docs/TEAM_INTELLIGENCE.md` for weighting, percentile thresholds, API fields, and limitations.

---

# DTOS v1.4.4 — Valuation Calibration and Trade Safety

DTOS now compares all player, pick, market, and package values on one documented 0–1000 scale. FantasyCalc and DynastyProcess retain their raw values but are normalized independently before consensus. Internal DTOS values and draft picks are converted through explicit deterministic methods.

Trade Intelligence now applies package diminishing returns and rejects low-value aggregation that lacks a premium centerpiece, including inappropriate superflex quarterback offers. Calibration state, provider agreement, confidence, and warnings are exposed in player intelligence and public crawl contracts.

Full methodology and current limits are documented in `docs/VALUATION_CALIBRATION.md`.

---

# DTOS v1.4.3 — Public Crawl API

DTOS now exposes the synchronized public league state through fast, cached, read-only JSON endpoints designed for ChatGPT and other standards-compliant crawlers.

## Highlights

- `/api/crawl` publishes version, league, sync, page, endpoint, and cache discovery metadata.
- `/api/crawl/snapshot` consolidates public league, roster, standings, picks, matchup, transaction, Front Office, trade, ranking, recommendation, alert, and sync data.
- Section endpoints provide teams, Front Offices, trades, transactions, matchups, picks, and standings without triggering Sleeper synchronization.
- Crawl artifacts use the shared intelligence cache, are isolated by league and sync generation, and invalidate after successful synchronization.
- Public serialization excludes credentials, environment variables, internal paths, and administrator-only state.
- `robots.txt` and `sitemap.xml` make the public site discoverable while excluding mutation and administrative paths.
- FantasyCalc and DynastyProcess public values now refresh into the canonical market cache with visible attribution.
- Sleeper player metadata, depth-chart fields, ownership, transactions, and trending activity reach player pages end to end.
- Provider failures preserve prior data only as a disclosed cached fallback; unsupported sources state the exact limitation.
- Bijan Robinson resolves to Sleeper ID `9509`; FantasyCalc value `10213` remains a value, never an identity.
- Canonical DTOS player identities reconcile Sleeper, FantasyCalc, KeepTradeCut, FantasyPros, Underdog, and Dynasty Daddy identifiers when supplied.
- Normalization covers names, teams, position eligibility, free agents, rookies, values, rankings, ADP, timestamps, confidence, and metadata.
- Invalid values, broken IDs, provider mismatches, and conflicting metadata are blocked before entering consensus.
- Provider reliability tracks success, failure, schema stability, and latency.
- Consensus 2.1 weights confidence, reliability, freshness, agreement, coverage, and missing sources without using a simple average.
- Sleeper trending adds and drops use the documented public API and remain cached for offline operation.
- Player dossiers display normalized identity, consensus, provider values, freshness, confidence, availability, licensing, and unavailable reasons.
- `/api/players/{player_id}/intelligence` exposes the full normalized player contract.
- Settings provides a Provider Activation Dashboard.

## Metadata

- Version: 1.4.3
- Build: 1430
- Codename: Public Crawl API

## Provider boundaries

- Sleeper league, player, roster, transaction, trade, matchup, metadata, and trending endpoints are active through its official read-only API.
- Cached provider values are normalized and attributed when legitimately supplied to DTOS.
- FantasyCalc remains subject to its attribution, caching, and commercial-use terms.
- Providers without approved public or licensed access remain explicitly disabled; no scraping or fabricated data is introduced.

## Non-goals preserved

No championship probability, Decision Engine change, trade recommendation change, machine learning, or scouting feature was added.

# DTOS v1.5.0 — Historical League Memory & Player Performance Intelligence

DTOS now preserves league and player evidence longitudinally instead of treating synchronized current state as history. A versioned SQLite store retains league-season configuration, franchise identity changes, weekly roster and matchup evidence, standings, playoff brackets, drafts, transactions, trades, player points, values, predictions, and Team Intelligence snapshots with provider provenance.

Historical import is resumable and idempotent. Missing raw NFL statistics and advanced usage are never converted to zero: Sleeper-scored fantasy points are retained as observed evidence, while unsupported components carry explicit availability reasons.

Public historical APIs are paginated and filterable by league, season, week, franchise, and player. Minimal League, Team, and Player History views expose available trends without drawing misleading lines through missing weeks.

See `docs/HISTORICAL_MEMORY.md` for schemas, import behavior, provenance, storage, performance, and current source limitations.

---
# DTOS v1.5.1 — Historical Data Reliability & Player Data Enrichment

Historical imports now persist durable jobs, granular checkpoints, worker leases,
retry classification, and step-based progress. A deployment or provider interruption
can resume without discarding completed categories or blocking ordinary requests.

DTOS also adds a free, attributed nflverse adapter for weekly raw player statistics.
Stable GSIS-to-Sleeper identity mappings are required; ambiguous or unresolved
players are excluded. League-season scoring settings produce separately versioned
fantasy scoring records, with incomplete components and confidence reported.

Advanced snaps, routes, and injury designations remain unavailable unless a future
approved provider supplies them. Missing metrics remain null and never become zero.

---

# DTOS v1.5.2 — Initial Backfill Performance

Fresh deployments now persist each bounded historical batch in one SQLite
transaction. The importer still yields between batches, renews its durable lease,
persists granular checkpoints, and uses immutable record keys for safe replay.

In a production-scale empty-database profile, the 30,051-record backfill fell from
468.162 seconds to 28.673 seconds. Batch persistence fell from 445.074 seconds to
6.987 seconds, while the longest transaction fell from 5.889 seconds to 0.046
seconds. Existing historical and enrichment behavior is unchanged.

---
# DTOS v1.5.6 — Deployment Readiness

DTOS now exposes separate liveness and readiness probes, keeps empty-data
instances out of service until synchronization succeeds, and delays cached
deployment maintenance for 30 seconds so initial user traffic does not compete
with synchronization and historical backfill startup.

Deployment diagnostics are opt-in through `X-DTOS-Diagnostics: 1` and expose
application request timing and process uptime without changing ordinary
responses. Local deployment-transition profiling kept liveness below 3 ms
during a concurrent matchup request and produced cached matchup medians of
approximately 0.58 seconds with graceful process cleanup.

---
# DTOS v1.5.7 — Historical Recovery

The production v1.5.6 foundation import encountered an `httpx.ReadError` while
reading a Sleeper response during 2025 weekly history retrieval. That transport
exception was outside the existing retry classification and stopped the import
after 23,595 records.

DTOS now treats all HTTPX transport failures as bounded retry candidates, logs
the exact Sleeper path and attempt, and preserves the original exception after
four unsuccessful attempts. Recovery skips complete 2021–2024 checkpoints and
replays incomplete 2025 records through the existing immutable record keys.

A fresh real-provider proof produced the canonical 30,051 records in 23.00
seconds. Consecutive reruns added zero rows, with zero duplicate record keys,
duplicate provider identities, or orphaned checkpoints. Seasons 2021–2025 are
complete. The preseason 2026 foundation is present while weekly rosters,
matchups, transactions, trades, and player-week data remain explicitly pending.

---
# DTOS v1.5.8 - Matchup Performance

Matchup market normalization now prepares each provider's value distribution once
per evaluation and reuses it for every player. Percentile ranks use binary-search
counts over the same sorted population, preserving the existing 70% provider-range
and 30% percentile formula exactly.

Production-scale local profiling reduced calls in the matchup fast path from about
2.89 million to 0.77 million. Median direct evaluation fell from approximately
0.84 seconds to 0.44 seconds, and five repeated local HTTP requests completed in
0.41-0.62 seconds. Trade Intelligence and package generation remain excluded from
the matchup route, and no shared matchup cache or historical behavior changed.

See `docs/MATCHUP_PERFORMANCE.md` for the measured pipeline and invariants.

---
# DTOS v1.5.9 - Valuation Calibration

DTOS now distinguishes its independent intrinsic player value from a separate
calibrated value that incorporates normalized public market evidence. Roster
grades, positional tiers, contender and rebuild profiles, and Trade Intelligence
consume that shared result, with confidence and blend weights remaining
explainable.

Draft-pick values now preserve a steeper round curve. A permanent 50-asset golden
test set covers elite players through developmental assets and representative
first- through fourth-round picks to detect future drift.

See `docs/VALUATION_CALIBRATION_V159.md` for methodology and limitations.

---
# DTOS v1.5.10 - Intelligence Quality Audit

DTOS intelligence was audited across all ten franchises, 120 prioritized trade
recommendations, the full player tier range, every supported rookie-pick round,
and competitive-window edge cases.

The audit found that the selected Front Office received calibrated market-backed
player cards while comparison teams received intrinsic-only cards. That made
league ranks and classifications depend on which franchise was selected. All
teams now use one neutral, cached, calibrated comparison contract. Team
Intelligence also consumes the canonical pick evaluator instead of a stale
duplicate round table.

The permanent golden benchmark now contains 82 representative player, pick,
archetype, team-window, and trade-package scenarios. See
`docs/INTELLIGENCE_QUALITY_AUDIT.md` for the league table and remaining limits.

---
# DTOS v1.5.11 — Competitive Window Contract

DTOS now computes each franchise's competitive window exactly once from calibrated
league-relative Team Intelligence. Decision, Front Office, Trade Intelligence,
recommendations, team pages, and APIs consume the same immutable contract.

The contract exposes the classification, confidence, championship/playoff/rebuild
scores, explainable reasons, strengths, weaknesses, generation timestamp, and
contract version. Valuation and Team Intelligence now complete before any trade
or recommendation can use the window, eliminating stale pre-calibration labels.

See `docs/COMPETITIVE_WINDOW_CONTRACT.md` for the dependency flow, consumer
boundaries, serialization behavior, and extension contract.

---
# DTOS v1.6.0 — Front Office Intelligence System Foundation

DTOS now has a parallel foundation for evaluating long-horizon franchise
management without replacing existing roster, valuation, historical,
competitive-window, or intelligence systems.

FOIS defines versioned contracts for scores, categories, metrics, evidence,
confidence, completeness, owner and franchise identity, model configuration, and
future cross-category traits. The initial weights are Results 35%, Trading and
Asset Management 25%, Roster Construction 20%, and Drafting and Talent
Evaluation 20%.

The subsystem is disabled by default with `DTOS_FOIS_ENABLED`. When enabled,
explicit cached facts are evaluated off the event loop and saved idempotently.
Unsupported evidence is disclosed as unavailable or insufficient and never
converted to zero. Advanced metrics remain provisional pending deeper historical
valuation, lineup, transaction, draft, and probability evidence.

See `docs/FOIS_FOUNDATION.md`.

---
# DTOS v1.6.1 — FOIS Results and Competitive Cycle Engine

Results is now the first production-scored FOIS category. DTOS evaluates observed
championships, championship games, Final Fours, playoff appearances, winning
seasons, actual-matchup win rate, league-size-normalized finishes, sustained
excellence, rebuild duration, reload efficiency, contention windows, competitive
longevity, and peak performance.

A reusable `CompetitiveCycleAnalyzer` produces explainable season timelines,
contention and rebuild cycles, peak seasons, reload timing, and full-history,
trailing-ten, trailing-five, trailing-three, and current-cycle windows. Missing
history and ownership changes reduce confidence and completeness without reducing
the outcome score.

The engine reads only immutable cached Historical Memory records. It performs no
provider I/O, runs through the existing worker-thread boundary, and persists its
timeline and cycle detail inside idempotent FOIS snapshots. Trading, Roster
Construction, and Drafting remain unchanged and out of scope.

---
# DTOS v1.6.3 — Complete Visual Inspection & Release Verification System

DINS 2.0 makes DTOS externally auditable as both a semantic product and a rendered web application. Public inspection APIs automatically inventory registered HTML pages, expose lightweight versioned artifact bundles, and report whether the bundle matches the deployed build. A separate bounded Playwright worker captures desktop, tablet, and mobile viewport/full-page screenshots plus sanitized DOM, accessibility, geometry, style, network, performance, and interaction evidence without adding browser work to user requests.

The capture job sends the deterministic inspection header, which bypasses freshness synchronization only for that request context. It never invokes providers or writes league state. Route validation now rejects unsupported public dynamic routes and version mismatches.

Known limitation: accessibility checks use a deterministic built-in WCAG-oriented audit rather than shipping axe-core into the web process. The capture contract is designed so axe findings can be added without a schema break.

# DTOS v1.6.2 — AI Inspection System Foundation

DTOS now exposes deterministic, machine-readable descriptions of major page
structures through the AI Inspection System (DINS). These endpoints describe
what pages contain—sections, cards, tables, charts, actions, navigation, links,
empty states, warnings, and element counts—without returning raw HTML.

DINS reads the already-cached DTOS state directly. It never synchronizes Sleeper,
calls a provider, executes intelligence engines, renders page services, performs
expensive recalculation, or changes application state. Missing cached information
is represented with explicit empty states and warnings.

Initial coverage includes the inspection catalog, Team Headquarters, Player
Dossier, Front Office Intelligence, and Trade Intelligence. The inspection schema
is independently versioned as `1.0`.

See `docs/DINS_INSPECTION.md`.

---
# DTOS v1.7.0 — Market Calibration Foundation

DTOS now enumerates every cached Sleeper player and canonical future pick once, exposes each valuation layer independently, records provider evidence and freshness, and exports the live universe as JSON or CSV. Existing value and recommendation behavior remains unchanged. Unsupported or missing evidence is explicit rather than inferred.

## Previous release
# DTOS v1.7.1 - Automated Market Calibration Dashboard

DTOS now audits every canonical player and draft pick whenever market providers refresh. The new calibration dashboard summarizes integrity, freshness, provider coverage, category health, high-impact differences, and explainable recommendations. Automatic changes are limited to small category-level model adjustments and require fresh evidence from multiple providers, sufficient sample size, high confidence, and a complete asset universe. No individual player or pick can be manually overridden by this system.
# DTOS v1.8.5 — Bounded Historical Identity Context

DTOS v1.8.5 removes the historical-enrichment OOM path identified in production. Player-week enrichment now creates its diagnosable job and lease, evaluates durable season checkpoints, and constructs identity state only when eligible provider work remains.

The identity context uses a compact, streamed current-identity projection backed by the existing primary key. It no longer loads or decodes the complete version history. Normal Sleeper synchronization is idempotent for unchanged identities, while material identity and mapping changes advance separate durable generations.

The release intentionally does not delete or compact existing identity history. Migration 7 adds only small metadata structures, validates free space before applying changes, and preserves historical records, provenance, checkpoints, leases, and the canonical `5/6` enrichment state.

Validation covers checkpoint-first startup, semantic generation stability, bounded projection, recoverable preparation, disk safety, full regression behavior, and the Linux 2 GiB cgroup contract. Historical duplicate compaction remains a separately approved future migration.

---
# DTOS v1.8.7 - Canonical Historical Progress Selection

DTOS v1.8.7 makes durable season checkpoints the source of truth for league-wide historical progress. A narrow current-season refresh remains visible as job-specific `0/1` progress but can no longer replace the configured 2021-2026 league contract of `5/6` with 2026 honestly pending.

The same canonical serializer now supplies history APIs, the History page, readiness, inspection, DINS, and Asset Market historical metadata. Foundation progress and active maintenance remain separately labeled. Smoke validation also recognizes the exact bounded Asset Market warming state during registered heavy lifecycle phases, then requires eligibility, exactly one background generation, and eventual HTTP 200.

No historical evidence, checkpoints, leases, market ranking, player universe, infrastructure, storage, or pricing changed.

---
# DTOS v1.8.8 - Season-Scoped Historical Checkpoint Compatibility

DTOS v1.8.8 corrects over-broad historical checkpoint invalidation. Each completed player-week season now stores a deterministic digest of only the canonical mappings referenced by that season. Unrelated current-player synchronization no longer invalidates immutable seasons.

Legacy checkpoints migrate only after evidence presence, identity resolution, uniqueness, provenance, and record-key validation. Migration updates checkpoint and audit metadata only; importer version 1.2 event identities remain unchanged. Compatibility diagnostics expose precise sanitized reason codes, and committed material identity remaps are recorded in a durable audit ledger.

The canonical state remains five completed seasons (2021-2025) with 2026 honestly pending.
# DTOS v1.8.9 — Semantic Asset Market Artifact Identity

DTOS v1.8.9 narrows durable Asset Market compatibility to the semantic inputs that can change compact market rows and canonical decisions. Repeated synchronization timestamps, Brain generation timestamps, unrelated historical observations, checkpoints, audits, and global archive generations no longer force a market reconstruction when the consumed content is unchanged.

The durable manifest records deterministic digests for the canonical asset universe, Brain and valuation output, ownership and identity dependencies, and provider evidence. Artifact discovery now inspects final candidates through the configured storage contract, rejects incompatible manifests before row hydration, and reports precise sanitized reason codes without exposing paths or database identities.

Asset detail history continues reading the current HistoricalStore, so compatible directory reuse never hides newly captured evidence. Historical capture, immutable record identities, importer 1.2, checkpoint compatibility, canonical `5/6` progress, lifecycle warming, single-flight construction, and atomic publication remain unchanged.

---
# DTOS v1.10.4 — Durable Projection & Asset Market Restoration

DTOS now restores its normalized Sleeper state, last valid Sleeper projection
evidence, canonical Projection Intelligence snapshot, and compatible Asset
Market artifact from the configured durable production mount before optional
background refresh. Original projection timestamps and semantic identities are
preserved across restart.

Asset Market publication now records an atomic checksum manifest. Startup uses
bounded discovery with explicit pending, compatible, corrupt, incomplete, and
incompatible outcomes. Health reports restore, construction, candidate, and
publication counters without exposing private storage paths.

Projection formulas, provider parsing, Brain valuation, FOIS, Matchups, and
Historical Memory evidence remain unchanged.

## Previous release
# DTOS v1.10.8 - Asset Market No-Op Invalidation Correction

DTOS v1.10.8 prevents semantically unchanged synchronization cycles from
starting Asset Market work. Scheduler identity now follows the retained Brain
and bounded market dependencies rather than the identity of a newly allocated
cache dictionary. A final semantic-generation guard also suppresses stale or
duplicate requests before artifact loading or construction.

Health metrics distinguish rebuild requests, no-op admission skips, and actual
constructions while preserving existing counters and durable behavior.

## Previous release
