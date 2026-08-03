# DTOS

DTOS is a FastAPI-based fantasy football Front Office Operating System. It turns synchronized Sleeper league data into objective briefings, explainable franchise evaluations, transaction context, matchup views, and decision-support foundations.

## Current release

DTOS v1.7.0 adds the [canonical valuation universe](docs/VALUATION.md): every cached Sleeper player and future pick has one identity, independent valuation layers, explicit provider/freshness evidence, deterministic JSON/CSV exports, and DINS audit coverage. Existing values are not recalibrated in this foundation release.

DTOS v1.6.7 publishes immutable production DINS bundles through GitHub Releases and
validates them dynamically without changing the inspected commit. DTOS v1.6.6 corrected Team Headquarters mobile overflow while preserving Product
Design System 1.0. DTOS v1.6.5 introduced shared page hierarchy, navigation,
explainable recommendations, league-relative grade context, truthful offseason
states, responsive behavior, and permanent DINS product-contract validation.
DTOS v1.6.4 normalized franchise identity across the application and polished Team Headquarters into a concise executive workflow. DTOS v1.6.3 expanded the read-only AI Inspection System into a complete semantic,
rendered-visual, DOM, accessibility, geometry, interaction, and release-verification
surface under `/api/inspect`. See
the [DINS inspection contract](docs/DINS_INSPECTION.md).

DTOS v1.6.1 makes Results the first production FOIS category using canonical
historical standings, matchups, playoff results, and owner history. See the
[FOIS Foundation](docs/FOIS_FOUNDATION.md).

DTOS v1.6.0 established the parallel, feature-flagged Front Office Intelligence
System foundation.

DTOS v1.5.11 gives every intelligence subsystem one authoritative,
league-relative competitive-window contract. See the
[Competitive Window Contract](docs/COMPETITIVE_WINDOW_CONTRACT.md).

DTOS v1.5.10 verifies league-wide intelligence quality and makes every
league-relative comparison independent of the selected Front Office. See the
[Intelligence Quality Audit](docs/INTELLIGENCE_QUALITY_AUDIT.md).

The Commissioner Desk remains the application homepage and answers three questions in order:

1. What changed?
2. What matters?
3. What should I do?

The Desk supports an Active League and Active Front Office context, personalized deterministic summaries, evidence-backed headlines, prioritized recommendations, league intelligence, compact snapshots, and persistent browser selections.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn dtos_app:app --reload
```

Open `http://127.0.0.1:8000/`.

Run the complete supported validation workflow with:

```powershell
.\.venv\Scripts\python.exe -m tools.validation.validate_release
```

Runtime configuration uses environment variables such as `SLEEPER_LEAGUE_ID`,
`DTOS_CACHE_FILE`, `DTOS_HISTORY_DB_FILE`, `DTOS_FOIS_ENABLED`,
`DTOS_FOIS_DB_FILE`, `SYNC_MINUTES`, and `SLEEPER_TIMEOUT`. Existing environment
overrides are preserved.

## Architecture

- `dtos_app.py` — application setup, shared lifecycle, page chrome, and router registration
- `routes/` — modular FastAPI route definitions
- `services/` — data retrieval and deterministic business logic
- `models/` — typed domain contracts
- `components/` — reusable server-rendered presentation components
- `tests/` — focused deterministic and regression tests
- `docs/` — feature architecture and developer documentation

Start with the [installation guide](docs/INSTALLATION.md), [architecture guide](docs/ARCHITECTURE.md), [developer guide](docs/DEVELOPER_GUIDE.md), [configuration reference](docs/CONFIGURATION.md), [API reference](docs/API_REFERENCE.md), and [production-readiness assessment](docs/PRODUCTION_READINESS.md).

The shared intelligence implementation lives in `src/core/decision_engine/`.

Individual asset evaluation lives in `src/core/asset_intelligence/` and is consumed by the Decision Engine.

Trade opportunity generation lives in `src/core/trade_intelligence/` and consumes both foundational engines without duplicating their formulas.

External market evidence lives in `src/core/market_intelligence/`. It enhances—but never replaces—DTOS intrinsic evaluation and is consumed only through the Intelligence Orchestrator.

League-wide synthesis lives in `src/core/league_intelligence/`. It consumes orchestrated engine outputs and never replaces or duplicates their evaluation formulas.

Immutable longitudinal evidence lives in `src/core/historical_memory/`. SQLite indexes isolate league, season, week, franchise, player, provider, and model-version dimensions while current-state JSON caching remains unchanged.

All external provider access flows through `src/core/data_platform/`. Market Intelligence and Sleeper transport consume this boundary rather than provider implementations directly.

See [Data Normalization](docs/DATA_NORMALIZATION.md), [Provider Activation](docs/PROVIDER_ACTIVATION.md), [Live Data Platform](docs/LIVE_DATA_PLATFORM.md), [League Intelligence](docs/LEAGUE_INTELLIGENCE.md), [Market Intelligence](docs/MARKET_INTELLIGENCE.md), [Intelligence Platform](docs/INTELLIGENCE_PLATFORM.md), [Trade Intelligence](docs/TRADE_INTELLIGENCE.md), [Asset Intelligence](docs/ASSET_INTELLIGENCE.md), [Decision Philosophy](docs/DTOS_DECISION_PHILOSOPHY.md), [Commissioner Desk architecture](docs/CommissionerDesk.md), [DTOS philosophy](DTOS_PHILOSOPHY.md), [roadmap](ROADMAP.md), and [release notes](RELEASE_NOTES.md).
