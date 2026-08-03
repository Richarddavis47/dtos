# Deployment Guide

## Production command

```text
python -m uvicorn dtos_app:app --host 0.0.0.0 --port ${PORT:-8000}
```

Install from `requirements.txt`, configure environment variables, provide writable locations for `DTOS_CACHE_FILE` and `DTOS_HISTORY_DB_FILE`, and run the complete validator before deployment. Use persistent storage for `DTOS_HISTORY_DB_FILE` when historical evidence must survive instance replacement. Deploy one process unless cache/database storage and synchronization coordination are externalized; background sync and import coordination are process-local.

## Health checks

- `/health/live` is the process-only liveness probe and never calls external providers or intelligence engines.
- `/health/ready` is the readiness probe. It returns HTTP 200 after cached or synchronized league data is available and HTTP 503 otherwise.
- `/health` remains the backward-compatible readiness surface.
- `/api/platform/health` reports engine, provider, cache, Sleeper, runtime, timing, and configuration-mode health.

Configure hosting liveness checks to use `/health/live` and traffic-readiness checks to use `/health/ready`. Cached deployments reserve `DTOS_BACKGROUND_START_DELAY` seconds (30 by default) for initial traffic before synchronization and historical maintenance begin. Empty deployments synchronize immediately and do not become ready until usable league data exists.

For bounded deployment diagnosis, send `X-DTOS-Diagnostics: 1`. The response then includes request-start time, route duration, total application duration, and process uptime. These headers are omitted from ordinary responses.

Use graceful termination so FastAPI lifespan cleanup cancels tracked background tasks. Do not embed secrets in build artifacts or logs. Roll back by deploying the preceding signed/reviewed tag; the cache schema remains backward compatible through v1.0.0.

## Render

Set the start command above, configure `SLEEPER_LEAGUE_ID`, and use a persistent writable cache path only when the hosting plan supplies persistent storage. Render branch/commit variables are automatically surfaced on Settings.

After a tagged Render deployment is ready, capture DINS against the exact production
commit and upload its deterministic ZIP, manifest, and checksum files to the matching
GitHub Release. Render resolves these public assets dynamically; generated inspection
files are never committed or baked into a follow-up deployment. Set
`DTOS_GITHUB_REPOSITORY` only when deploying a fork; the default is
`Richarddavis47/dtos`.
