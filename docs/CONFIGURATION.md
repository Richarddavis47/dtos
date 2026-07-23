# Configuration Guide

DTOS reads configuration once at import/startup. Invalid numeric or logging settings fail fast with a clear `ValueError`. Secrets are not required by the current read-only Sleeper integration.

| Variable | Default | Purpose |
|---|---:|---|
| `SLEEPER_LEAGUE_ID` | bundled league ID | Active Sleeper league |
| `SLEEPER_BASE_URL` | `https://api.sleeper.app/v1` | Sleeper API base URL |
| `SYNC_MINUTES` | `15` (minimum 5) | Background synchronization interval |
| `DTOS_CACHE_FILE` | OS temp `dtos_cache.json` | Normalized Sleeper cache; override is always preserved |
| `SLEEPER_TIMEOUT` | `30` (minimum 1) | HTTP timeout in seconds |
| `LOG_LEVEL` | `INFO` | Python log level |
| `DTOS_LOG_FORMAT` | `json` | `json` structured output or `text` |
| `DTOS_INTELLIGENCE_CACHE_TTL` | `60` | Orchestrator cache TTL seconds |
| `DTOS_MARKET_CACHE_TTL` | `3600` | Market quote cache TTL seconds |
| `DTOS_DATA_WAREHOUSE_FILE` | OS temp `dtos_data_history.json` | Durable attributed external-data snapshots |
| `DTOS_HISTORY_DB_FILE` | OS temp `dtos_history.sqlite3` | Indexed Historical League Memory database; use a persistent writable mount in production |
| `DTOS_PROVIDER_<NAME>` | provider-specific | Enable or disable a provider permitted by deployment licensing |
| `DTOS_GIT_BRANCH` | detected | Deployment branch override |
| `DTOS_GIT_COMMIT` | detected | Deployment commit override |

`RENDER_GIT_BRANCH`, `RENDER_GIT_COMMIT`, and `RENDER_SERVICE_NAME` are supported deployment metadata. Never commit environment files containing future provider credentials.
