"""Application boundary for the feature-flagged FOIS foundation."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir

from src.core.fois.repository import FOISRepository
from src.core.fois.history import load_results_history
from src.core.fois.service import FOISService
from src.core.history_context import canonical_history_store


def _database_path() -> Path:
    storage_root = os.getenv("DTOS_HISTORY_STORAGE_ROOT")
    default = Path(storage_root) / "dtos_fois.sqlite3" if storage_root else Path(gettempdir()) / "dtos_fois.sqlite3"
    return Path(
        os.getenv(
            "DTOS_FOIS_DB_FILE",
            str(default),
        )
    )


fois_service = FOISService(
    repository_factory=lambda: FOISRepository(_database_path()),
    history_loader=lambda league_id: load_results_history(
        canonical_history_store,
        league_id,
    ),
)
