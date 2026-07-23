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
