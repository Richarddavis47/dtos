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
