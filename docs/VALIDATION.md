# Validation Guide

The canonical complete-release command is:

```powershell
.\.venv\Scripts\python.exe -m tools.validation.validate_release
```

It executes exactly these gates in order: committed, working-tree, and staged whitespace; Python compilation; Ruff; dependency integrity; all unit/regression tests; route and OpenAPI validation; tracked HTTP smoke tests; deterministic process cleanup. Documentation completeness and application-to-provider architecture boundaries are checked before subprocess gates.

The runner stops on the first failure and prints elapsed time for every completed gate. `run_http_validation.py` allocates a port, tracks the spawned PID, verifies port ownership, runs smoke tests, and cleans up in `finally`. `process_check.py` confirms no genuine DTOS Python/Uvicorn host remains.

Individual supported entry points also use module execution: `python -m tools.validation.validate_routes`, `python -m tools.validation.smoke_http --base-url <url>`, `python -m tools.validation.run_http_validation`, and `python -m tools.validation.process_check`. Direct execution by file path is not a supported contract.

Release-specific tests belong in `tests/`; do not weaken shared validation to accommodate a feature. See `VALIDATION_REPORT.md` for the v1.0.0 results.
