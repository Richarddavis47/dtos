"""Central DTOS runtime configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir


def _integer(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(minimum, int(raw))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, received {raw!r}.") from exc


def _number(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return max(minimum, float(raw))
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric, received {raw!r}.") from exc


def _boolean(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, received {raw!r}.")


@dataclass(frozen=True)
class Settings:
    league_id: str
    sleeper_base: str
    sync_minutes: int
    cache_file: Path
    request_timeout: float
    log_level: str
    log_format: str
    intelligence_cache_ttl: float
    market_cache_ttl: float
    data_warehouse_file: Path
    history_database_file: Path
    history_storage_root: Path
    projection_database_file: Path
    durable_history_required: bool
    enrichment_batch_size: int
    historical_start_season: int
    background_start_delay: float
    max_warm_league_runtimes: int

    @classmethod
    def from_environment(cls) -> "Settings":
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(f"LOG_LEVEL must be a standard Python logging level, received {level!r}.")
        log_format = os.getenv("DTOS_LOG_FORMAT", "json").casefold()
        if log_format not in {"json", "text"}:
            raise ValueError("DTOS_LOG_FORMAT must be 'json' or 'text'.")
        history_storage_root = Path(
            os.getenv("DTOS_HISTORY_STORAGE_ROOT", "/var/data/dtos")
        )
        durable_required = _boolean(
            "DTOS_DURABLE_HISTORY_REQUIRED",
            default=bool(os.getenv("RENDER")),
        )
        default_cache = (
            history_storage_root / "dtos_cache.json"
            if durable_required else Path(gettempdir()) / "dtos_cache.json"
        )
        cache_file = Path(os.getenv("DTOS_CACHE_FILE", str(default_cache)))
        return cls(
            league_id=os.getenv("SLEEPER_LEAGUE_ID", "1313066632158924800"),
            sleeper_base=os.getenv("SLEEPER_BASE_URL", "https://api.sleeper.app/v1").rstrip("/"),
            sync_minutes=_integer("SYNC_MINUTES", 15, 5),
            cache_file=cache_file,
            request_timeout=_number("SLEEPER_TIMEOUT", 30, 1),
            log_level=level,
            log_format=log_format,
            intelligence_cache_ttl=_number("DTOS_INTELLIGENCE_CACHE_TTL", 60, 0),
            market_cache_ttl=_number("DTOS_MARKET_CACHE_TTL", 3600, 0),
            data_warehouse_file=Path(os.getenv("DTOS_DATA_WAREHOUSE_FILE", str(Path(gettempdir()) / "dtos_data_history.json"))),
            history_database_file=Path(os.getenv("DTOS_HISTORY_DB_FILE", str(Path(gettempdir()) / "dtos_history.sqlite3"))),
            history_storage_root=history_storage_root,
            projection_database_file=Path(os.getenv(
                "DTOS_PROJECTION_DB_FILE",
                str(
                    history_storage_root / "dtos_projections.sqlite3"
                    if durable_required
                    else cache_file.with_name("dtos_projections.sqlite3")
                ),
            )),
            durable_history_required=durable_required,
            enrichment_batch_size=min(
                1000, _integer("DTOS_ENRICHMENT_BATCH_SIZE", 250, 25),
            ),
            historical_start_season=_integer(
                "DTOS_HISTORICAL_START_SEASON", 2021, 2000,
            ),
            background_start_delay=_number(
                "DTOS_BACKGROUND_START_DELAY",
                30,
                0,
            ),
            max_warm_league_runtimes=min(
                3, _integer("DTOS_MAX_WARM_LEAGUE_RUNTIMES", 2, 1),
            ),
        )


SETTINGS = Settings.from_environment()
LEAGUE_ID = SETTINGS.league_id
SLEEPER_BASE = SETTINGS.sleeper_base
SYNC_MINUTES = SETTINGS.sync_minutes
CACHE_FILE = SETTINGS.cache_file
REQUEST_TIMEOUT = SETTINGS.request_timeout
LOG_LEVEL = SETTINGS.log_level
LOG_FORMAT = SETTINGS.log_format
INTELLIGENCE_CACHE_TTL = SETTINGS.intelligence_cache_ttl
MARKET_CACHE_TTL = SETTINGS.market_cache_ttl
DATA_WAREHOUSE_FILE = SETTINGS.data_warehouse_file
HISTORY_DATABASE_FILE = SETTINGS.history_database_file
HISTORY_STORAGE_ROOT = SETTINGS.history_storage_root
PROJECTION_DATABASE_FILE = SETTINGS.projection_database_file
DURABLE_HISTORY_REQUIRED = SETTINGS.durable_history_required
ENRICHMENT_BATCH_SIZE = SETTINGS.enrichment_batch_size
HISTORICAL_START_SEASON = SETTINGS.historical_start_season
BACKGROUND_START_DELAY = SETTINGS.background_start_delay
MAX_WARM_LEAGUE_RUNTIMES = SETTINGS.max_warm_league_runtimes
