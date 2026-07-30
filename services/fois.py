"""Application boundary for the feature-flagged FOIS foundation."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir

from src.core.fois.repository import FOISRepository
from src.core.fois.history import load_results_history
from src.core.fois.service import FOISService
from src.core.historical_memory import historical_store


def _database_path() -> Path:
    return Path(
        os.getenv(
            "DTOS_FOIS_DB_FILE",
            str(Path(gettempdir()) / "dtos_fois.sqlite3"),
        )
    )


fois_service = FOISService(
    repository_factory=lambda: FOISRepository(_database_path()),
    history_loader=lambda league_id: load_results_history(
        historical_store,
        league_id,
    ),
)
