"""DTOS configuration module.

Configuration is intentionally kept compatible with the existing deployment.
As services are migrated out of ``dtos_app.py``, shared settings will move here.
"""
import os
from pathlib import Path

LEAGUE_ID = os.getenv("SLEEPER_LEAGUE_ID", "1313066632158924800")
SLEEPER_BASE = "https://api.sleeper.app/v1"
SYNC_MINUTES = max(5, int(os.getenv("SYNC_MINUTES", "15")))
CACHE_FILE = Path(os.getenv("DTOS_CACHE_FILE", "/tmp/dtos_cache.json"))
REQUEST_TIMEOUT = float(os.getenv("SLEEPER_TIMEOUT", "30"))
