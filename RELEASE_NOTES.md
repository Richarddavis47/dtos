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
