# Deployment Guide

## Production command

```text
python -m uvicorn dtos_app:app --host 0.0.0.0 --port ${PORT:-8000}
```

Install from `requirements.txt`, configure environment variables, provide a writable location for `DTOS_CACHE_FILE`, and run the complete validator before deployment. Deploy one process unless cache storage and synchronization coordination are externalized; the v1 cache and background sync state are process-local.

## Health checks

- `/health` is the lightweight liveness/readiness surface.
- `/api/platform/health` reports engine, provider, cache, Sleeper, runtime, timing, and configuration-mode health.

Use graceful termination so FastAPI lifespan cleanup cancels the background synchronization task. Do not embed secrets in build artifacts or logs. Roll back by deploying the preceding signed/reviewed tag; the cache schema remains backward compatible through v1.0.0.

## Render

Set the start command above, configure `SLEEPER_LEAGUE_ID`, and use a persistent writable cache path only when the hosting plan supplies persistent storage. Render branch/commit variables are automatically surfaced on Settings.
