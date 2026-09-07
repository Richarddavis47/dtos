"""Application boundary for the feature-flagged FOIS foundation."""
from __future__ import annotations

import os
from contextlib import closing
from pathlib import Path
from tempfile import gettempdir

from src.core.fois.repository import FOISRepository
from src.core.fois.history import load_results_history
from src.core.fois.service import FOISService
from src.core.fois.process_execution import generate_fois_isolated
from src.core.history_context import canonical_history_store
from src.core.front_office_evidence import publish_front_office_evidence
from src.core.gm_behavioral_intelligence import publish_gm_behavioral_intelligence
from src.platform.storage_gate import connect


def _database_path() -> Path:
    storage_root = os.getenv("DTOS_HISTORY_STORAGE_ROOT")
    default = Path(storage_root) / "dtos_fois.sqlite3" if storage_root else Path(gettempdir()) / "dtos_fois.sqlite3"
    return Path(
        os.getenv(
            "DTOS_FOIS_DB_FILE",
            str(default),
        )
    )


def storage_summary() -> dict[str, int]:
    """Aggregate operational counts only; no identities or private payloads."""
    path = _database_path()
    if not path.exists():
        return {"database_bytes": 0, "semantic_states": 0, "observations": 0}
    with closing(connect(path, readonly=True)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            "database_bytes": path.stat().st_size,
            "semantic_states": connection.execute("SELECT COUNT(*) FROM fois_semantic_states").fetchone()[0] if 'fois_semantic_states' in tables else 0,
            "observations": connection.execute("SELECT COUNT(*) FROM fois_snapshot_history").fetchone()[0] if 'fois_snapshot_history' in tables else 0,
        }


fois_service = FOISService(
    repository_factory=lambda: FOISRepository(_database_path()),
    history_loader=lambda league_id: load_results_history(
        canonical_history_store,
        league_id,
    ),
    isolated_executor=generate_fois_isolated,
)
fois_service.add_generation_listener(publish_front_office_evidence)
fois_service.add_generation_listener(publish_gm_behavioral_intelligence)
