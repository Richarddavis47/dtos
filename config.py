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

    @classmethod
    def from_environment(cls) -> "Settings":
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(f"LOG_LEVEL must be a standard Python logging level, received {level!r}.")
        log_format = os.getenv("DTOS_LOG_FORMAT", "json").casefold()
        if log_format not in {"json", "text"}:
            raise ValueError("DTOS_LOG_FORMAT must be 'json' or 'text'.")
        return cls(
            league_id=os.getenv("SLEEPER_LEAGUE_ID", "1313066632158924800"),
            sleeper_base=os.getenv("SLEEPER_BASE_URL", "https://api.sleeper.app/v1").rstrip("/"),
            sync_minutes=_integer("SYNC_MINUTES", 15, 5),
            cache_file=Path(os.getenv("DTOS_CACHE_FILE", str(Path(gettempdir()) / "dtos_cache.json"))),
            request_timeout=_number("SLEEPER_TIMEOUT", 30, 1),
            log_level=level,
            log_format=log_format,
            intelligence_cache_ttl=_number("DTOS_INTELLIGENCE_CACHE_TTL", 60, 0),
            market_cache_ttl=_number("DTOS_MARKET_CACHE_TTL", 3600, 0),
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
