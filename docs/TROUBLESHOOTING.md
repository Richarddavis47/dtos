# Troubleshooting Guide

## Startup has no league data

Check `/health`, `SLEEPER_LEAGUE_ID`, network access, and `DTOS_CACHE_FILE`. A missing live connection is non-blocking only when a valid cached snapshot exists.

## Sleeper synchronization fails

Use the request ID and structured error log. Confirm `SLEEPER_BASE_URL`, timeout, DNS, and Sleeper availability. Do not delete a valid cache while diagnosing.

## Market data is unavailable

Inspect `/api/platform/health` provider status, retrieval mode, freshness, and cache age. Offline execution does not inherit online consensus unless explicit cached fallback is configured in the market payload.

## Validation server remains running

Run `.\.venv\Scripts\python.exe -m tools.validation.process_check`. The lifecycle utility terminates only its tracked PID tree. Do not kill unrelated Python processes by executable name.

## Route validation fails

Run `python -m tools.validation.validate_routes`. Resolve duplicate method/path pairs or restore required endpoints; do not suppress automatic HEAD reporting.

## Configuration fails fast

Read the named variable in the exception and correct its numeric value, log level, or log format. See `CONFIGURATION.md`.
