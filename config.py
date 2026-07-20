"""Central DTOS runtime configuration."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir

LEAGUE_ID = os.getenv("SLEEPER_LEAGUE_ID", "1313066632158924800")
SLEEPER_BASE = "https://api.sleeper.app/v1"
SYNC_MINUTES = max(5, int(os.getenv("SYNC_MINUTES", "15")))
CACHE_FILE = Path(
    os.getenv("DTOS_CACHE_FILE", str(Path(gettempdir()) / "dtos_cache.json"))
)
REQUEST_TIMEOUT = float(os.getenv("SLEEPER_TIMEOUT", "30"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
