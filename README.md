# DTOS

DTOS is a FastAPI-based fantasy football Front Office Operating System. It turns synchronized Sleeper league data into objective briefings, explainable franchise evaluations, transaction context, matchup views, and decision-support foundations.

## Current release

DTOS v1.4.2 activates approved FantasyCalc and DynastyProcess market feeds alongside official Sleeper player, league, transaction, and trending data. Player pages show attributed consensus, provider values, metadata, depth-chart context, and specific explanations for sources that are not supported.

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

Runtime configuration uses environment variables such as `SLEEPER_LEAGUE_ID`, `DTOS_CACHE_FILE`, `SYNC_MINUTES`, and `SLEEPER_TIMEOUT`. Existing environment overrides are preserved.

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

All external provider access flows through `src/core/data_platform/`. Market Intelligence and Sleeper transport consume this boundary rather than provider implementations directly.

See [Data Normalization](docs/DATA_NORMALIZATION.md), [Provider Activation](docs/PROVIDER_ACTIVATION.md), [Live Data Platform](docs/LIVE_DATA_PLATFORM.md), [League Intelligence](docs/LEAGUE_INTELLIGENCE.md), [Market Intelligence](docs/MARKET_INTELLIGENCE.md), [Intelligence Platform](docs/INTELLIGENCE_PLATFORM.md), [Trade Intelligence](docs/TRADE_INTELLIGENCE.md), [Asset Intelligence](docs/ASSET_INTELLIGENCE.md), [Decision Philosophy](docs/DTOS_DECISION_PHILOSOPHY.md), [Commissioner Desk architecture](docs/CommissionerDesk.md), [DTOS philosophy](DTOS_PHILOSOPHY.md), [roadmap](ROADMAP.md), and [release notes](RELEASE_NOTES.md).
