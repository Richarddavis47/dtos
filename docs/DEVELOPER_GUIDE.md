# Developer Guide

## Repository map

- `routes/`: dependency-injected FastAPI routers
- `services/`: retrieval and presentation-independent application logic
- `components/`: server-rendered reusable HTML
- `src/core/`: intelligence providers and shared orchestration contracts
- `src/platform/`: observability and validation
- `tests/`: deterministic unit, contract, reliability, lifecycle, and integration tests
- `tools/validation/`: executable release tooling

## Change workflow

Read `AGENTS.md`, start from current clean `main`, create one release branch, inspect existing contracts before editing, preserve environment overrides, and keep changes focused. Use the Intelligence Orchestrator from application services. Add domain logic behind a provider or existing engine interface; never create a second application recommendation path.

Run `.\.venv\Scripts\python.exe -m tools.validation.validate_release`. A failure is a release blocker and must not be hidden or bypassed.

## Code standards

Use typed immutable contracts where practical, deterministic calculations, evidence-backed output, explicit missing-data states, dependency injection for routers, and structured logs without secrets. Explain confidence reductions and fallback behavior. Maintain Windows and Linux compatibility.
