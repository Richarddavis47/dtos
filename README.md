# DTOS

DTOS is a FastAPI-based fantasy football Front Office Operating System. It turns synchronized Sleeper league data into objective briefings, explainable franchise evaluations, transaction context, matchup views, and decision-support foundations.

## Current release

DTOS v0.9.7 introduces Front Office Intelligence v1, a neutral, deterministic model of observable organizational behavior that improves trade recommendations without inferring personal characteristics.

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

Runtime configuration uses environment variables such as `SLEEPER_LEAGUE_ID`, `DTOS_CACHE_FILE`, `SYNC_MINUTES`, and `SLEEPER_TIMEOUT`. Existing environment overrides are preserved.

## Architecture

- `dtos_app.py` — application setup, shared lifecycle, page chrome, and router registration
- `routes/` — modular FastAPI route definitions
- `services/` — data retrieval and deterministic business logic
- `models/` — typed domain contracts
- `components/` — reusable server-rendered presentation components
- `tests/` — focused deterministic and regression tests
- `docs/` — feature architecture and developer documentation

The shared intelligence implementation lives in `src/core/decision_engine/`.

Individual asset evaluation lives in `src/core/asset_intelligence/` and is consumed by the Decision Engine.

Trade opportunity generation lives in `src/core/trade_intelligence/` and consumes both foundational engines without duplicating their formulas.

See [Trade Intelligence](docs/TRADE_INTELLIGENCE.md), [Asset Intelligence](docs/ASSET_INTELLIGENCE.md), [Decision Philosophy](docs/DTOS_DECISION_PHILOSOPHY.md), [Commissioner Desk architecture](docs/CommissionerDesk.md), [DTOS philosophy](DTOS_PHILOSOPHY.md), [roadmap](ROADMAP.md), and [release notes](RELEASE_NOTES.md).
