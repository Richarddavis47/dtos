# Validation Guide

The canonical complete-release command is:

```powershell
.\.venv\Scripts\python.exe -m tools.validation.validate_release
```

It executes exactly these gates in order: committed, working-tree, and staged whitespace; Python compilation; Ruff; dependency integrity; all unit/regression tests; route and OpenAPI validation; tracked HTTP smoke tests; deterministic process cleanup. Documentation completeness and application-to-provider architecture boundaries are checked before subprocess gates.

The runner stops on the first failure and prints elapsed time for every completed gate. `run_http_validation.py` allocates a port, tracks the spawned PID, verifies port ownership, runs smoke tests, and cleans up in `finally`. `process_check.py` confirms no genuine DTOS Python/Uvicorn host remains.

Individual supported entry points also use module execution: `python -m tools.validation.validate_routes`, `python -m tools.validation.smoke_http --base-url <url>`, `python -m tools.validation.run_http_validation`, and `python -m tools.validation.process_check`. Direct execution by file path is not a supported contract.

Release-specific tests belong in `tests/`; do not weaken shared validation to accommodate a feature. See `VALIDATION_REPORT.md` for the v1.0.0 results.

## Cloud development setup

The saved Cloud environment uses Python 3.12 and system Chromium. From the
repository root, run this idempotent setup command in the environment setup hook
or after a fresh checkout:

```sh
python3.12 -m tools.validation.setup_cloud
```

It creates `.venv` if absent, installs product and validation dependencies,
checks dependency integrity, and actually launches a headless browser. An
alternate disposable environment is supported with `--venv /tmp/dtos-fresh-venv`.
The setup uses inherited proxy/CA settings. It starts no application service.
Use the resulting virtual environment interpreter for all following commands.

Browser tests share `tools.validation.browser_runtime.launch_chromium`.
Selection is deterministic: `DTOS_CHROMIUM_EXECUTABLE` (explicit executable
path), then the installed Playwright Chromium, then Linux `chromium` or
`chromium-browser` on PATH. Every launch prints executable and browser version.
Launch errors fail validation without retrying another browser. Cloud reuses its
system Chromium without a redundant download; CI continues installing the
version-matched Playwright browser. Setup installs Playwright Chromium when no
system browser or explicit override exists. A bare Linux image without browser
libraries needs `python -m playwright install --with-deps chromium` during image
provisioning. A system-browser upgrade requires rerunning the browser contracts.

For tooling-only changes, the focused Cloud checks are:

```sh
.venv/bin/python -m unittest tests.test_cloud_tooling tests.test_server_lifecycle tests.test_process_check tests.test_validation_progress tests.test_market_warming_validation
.venv/bin/python -m tools.validation.run_http_validation
.venv/bin/python -m unittest tests.test_product_browser_journey tests.test_matchup_browser_contract tests.test_trade_center_browser tests.test_trade_center_accessibility tests.test_trade_workspace_browser tests.test_trade_workspace_batch1 tests.test_live_inspection tests.test_browser_fixture_images tests.test_visual_retirement
.venv/bin/python -m ruff check .
.venv/bin/python -m compileall -q src tools tests
git diff --check
```

HTTP validation binds only loopback and uses `psutil.net_connections(kind="tcp")`
for IPv4/IPv6 listener ownership on Windows and Linux. Run-tag matching, teardown,
port-release verification, watchdogs and smoke assertions remain required.
Permission failures and listeners with unknown PIDs fail closed. Run in a worker
with visibility of its own process/socket inventory. Use disposable local cache
and storage paths for smoke tests; preserve any explicitly supplied environment
overrides. Never aim these checks at a production origin.

For the Linux 2 GiB lifecycle scenarios, use the generator commands, archive
flags and limits in `.github/workflows/linux-market-lifecycle.yml`, with
disk-backed fixture/output directories under `.validation/`, as CI does. Check
the backing filesystem with `stat -f -c %T .validation` after creating the
directory. On the managed Cloud worker, `/workspace` is disk-backed and `/tmp`
is tmpfs. A tmpfs fixture charges database and WAL bytes to the container as
nonreclaimable file memory; this changes the archive/page-cache workload and can
kill fixture generation before the application starts. It can also force repeated
Market memory-admission deferrals. Use disposable disk-backed directories for
these production-shaped fixtures and run scenarios independently, matching the
CI matrix. Keep the complete fixture scale, 2 GiB memory/swap limits, two CPUs,
one-semantic-child assertion, zero-OOM checks and cleanup requirements unchanged.

The 2026-10-01 verification used a separate source checkout and a newly created
virtual environment on the saved Cloud worker (not a newly provisioned Cloud
image). Setup and dependency integrity passed with Python 3.12.14; GitHub and
the public Sleeper NFL state API returned HTTP 200 with valid JSON from Sleeper.
The 69 focused tooling tests and 77 browser/related contract tests passed with
system Chromium 151.0.7922.173. Canonical HTTP validation passed 114 requests,
startup, graceful cleanup and final process inventory. Its disposable cache
used the existing sanitized market fixture generator with 250 players, isolated
storage paths, and an unavailable loopback Sleeper source to exercise retained
fixture startup without changing a live league. Repository lint, compilation of
all Python in the separate checkout, and whitespace checks passed. Windows
behavior is covered by focused mocks here and by the Windows/Linux tooling CI
matrix; a native Windows run was not performed in the Cloud worker.

## Authoritative Ruff scope and legacy diagnostics

The canonical release command still runs `python -m ruff check .` against the
entire repository. `ruff.toml` explicitly selects the historical Ruff defaults
`E4`, `E7`, `E9`, `F`, with Python 3.12 as the target. There are no path exclusions,
per-file suppressions or historical error allowances. This scope passes with zero
findings and applies equally to existing, changed and new code. Validation-only
Ruff and Playwright versions are pinned in `requirements-validation.txt`; the
product dependencies and complete release gate ordering are unchanged.

The October 2026 Cloud audit used Ruff 0.16.9. Its expanded defaults, rather than
a release-path exemption, produced 1,060 findings without repository configuration.
The v1.0.0 report reflects the historical default scope. Most expanded-rule debt
is import sorting (`I001`: 514), deprecated typing imports (`UP035`: 96), nested
context managers (`SIM117`: 79), loop captures (`B023`: 67), collection style
(`C408`: 67), and broad exception catches (`BLE001`: 43). It spans application,
services, core, tools and tests, including storage tooling. It is not a reason to
mass-edit unrelated work or to claim the expanded audit passes.

Reproduce the advisory audit with the pinned version:

```sh
.venv/bin/python -m ruff check . --isolated --statistics
```

This expanded audit is legacy debt, not the release gate. Do not replace the
zero-finding authoritative gate with an error-count budget: that would allow new
errors to offset fixes. Any future expansion of the required rules needs its own
reviewed scope and cleanup. Complete product releases still use the canonical
release command (on Linux: `.venv/bin/python -m tools.validation.validate_release`).

## Trade discovery and repair acceptance

`python -m unittest tests.test_trade_discovery_repair` runs deterministic real
Market/legal-lineup fixtures for progressive search, diverse recommendation pages,
Shop anchors, Trade For ownership/package diversity, cheaper previews, exact locks,
younger returns, limited history, bad counterparty terms and evaluated near misses.
Existing Batch 5, capital/strategy, authenticated workspace and browser contracts
remain release gates. See [Scout handoff and release evidence](TRADE_DISCOVERY_REPAIR_RELEASE.md).
