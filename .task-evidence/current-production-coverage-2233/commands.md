# Exact-source validation commands

Source candidate and baseline: source.json. Complete binary patch: candidate-production.patch; independent Git-index reconstruction: source-integrity.json.

- Focused (real 2 GiB, no swap, two CPUs, network none, UID1000, source read-only): `DTOS_PRODUCTION_COVERAGE_EVIDENCE=/evidence/browser-final DTOS_EXPECTED_HEAD=0a9bb07dbda9d8d9f742b55328fdd68a7d234364 python /workspace/2233-release/run-constrained.py -m unittest -v tests.test_current_production_coverage tests.test_current_production_browser`.
- Full mandatory entry point: `python /workspace/2233-release/run-clean.py`. Unchanged recorded runner invokes `python -m tools.validation.validate_release`; Python3.14.3,2GiB/no swap/twoCPUs/networknone/UID1000. Scratch prerequisite unchanged; source writable exact clean checkout. Full original console and test/gate events retained.
- All-source Ruff: existing canonical gate and `python /workspace/current-season-production/run-constrained.py -m ruff check --no-cache .`. Initial host .venv path was absent; no elevated tests or permission changes. Initial read-only Ruff cache write refused; final no-cache invocation passed without source edits.
- `git diff --check` and exact source/patch inventory.
- Separate publisher: `DTOS_RESOURCE_SOURCE=/workspace/dtos-publisher-2233 python /workspace/2233-release/run-constrained.py -m unittest -v tests.test_release_publisher`; Ruff uses byte-identical repository ruff.toml via `/evidence/ruff.toml` because sparse tooling checkout omits root config.

Original earlier/intermediate fixture setup failures and baseline assertions remain in investigation and Prior-attempts.zip. They are not final-source gate completions. Public source configuration/schema reads are not authenticated production data. No owner-browser/Render Shell capability is attached; no repeated inspection credential request or force sync.
