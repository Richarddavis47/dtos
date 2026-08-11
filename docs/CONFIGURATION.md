# Configuration Guide

DTOS reads configuration once at import/startup. Invalid numeric or logging settings fail fast with a clear `ValueError`. Secrets are not required by the current read-only Sleeper integration.

| Variable | Default | Purpose |
|---|---:|---|
| `SLEEPER_LEAGUE_ID` | bundled league ID | Active Sleeper league |
| `SLEEPER_BASE_URL` | `https://api.sleeper.app/v1` | Sleeper API base URL |
| `SYNC_MINUTES` | `15` (minimum 5) | Background synchronization interval |
| `DTOS_BACKGROUND_START_DELAY` | `30` | Seconds reserved for initial traffic before cached deployments start synchronization and historical maintenance; set to `0` for immediate startup |
| `DTOS_CACHE_FILE` | Durable root on Render; OS temp otherwise | Normalized Sleeper cache; override is always preserved |
| `DTOS_PROJECTION_DB_FILE` | Durable root on Render; cache sibling otherwise | Last-valid Sleeper evidence and canonical Projection Intelligence snapshots |
| `SLEEPER_TIMEOUT` | `30` (minimum 1) | HTTP timeout in seconds |
| `LOG_LEVEL` | `INFO` | Python log level |
| `DTOS_LOG_FORMAT` | `json` | `json` structured output or `text` |
| `DTOS_INTELLIGENCE_CACHE_TTL` | `60` | Orchestrator cache TTL seconds |
| `DTOS_MARKET_CACHE_TTL` | `3600` | Market quote cache TTL seconds |
| `DTOS_DATA_WAREHOUSE_FILE` | OS temp `dtos_data_history.json` | Durable attributed external-data snapshots |
| `DTOS_HISTORY_DB_FILE` | OS temp `dtos_history.sqlite3` | Indexed Historical League Memory database; use a persistent writable mount in production |
| `DTOS_HISTORY_STORAGE_ROOT` | `/var/data/dtos` | Required persistent mount root when durable history is enabled |
| `DTOS_DURABLE_HISTORY_REQUIRED` | Enabled automatically on Render | Reject absent, unmounted, unwritable, or out-of-root historical storage instead of falling back to ephemeral storage |
| `DTOS_PROVIDER_<NAME>` | provider-specific | Enable or disable a provider permitted by deployment licensing |
| `DTOS_GIT_BRANCH` | detected | Deployment branch override |
| `DTOS_GIT_COMMIT` | detected | Deployment commit override |

`RENDER_GIT_BRANCH`, `RENDER_GIT_COMMIT`, and `RENDER_SERVICE_NAME` are supported deployment metadata. Never commit environment files containing future provider credentials.
