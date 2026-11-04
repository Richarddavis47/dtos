"""Dormant legacy history algorithms and compatibility types.

Importing this package must never open or initialize the retired provider
archive.  The exported ``historical_store`` name is a compatibility alias for
the canonical Sleeper-backed context during the v1.10.23 shadow period.
"""
from src.core.historical_memory.aggregation import aggregate_production
from src.core.historical_memory.models import (
    DATABASE_MIGRATION_VERSION,
    HISTORICAL_SCHEMA_VERSION,
    PLAYER_HISTORY_SCHEMA_VERSION,
    PREDICTION_MODEL_VERSION,
    Availability,
)
from src.core.historical_memory.store import HistoricalStore
from src.core.historical_memory.graph import (
    HistoricalAssetGraph,
    canonical_event_id,
    canonical_pick_id,
    canonical_player_id,
    canonical_trade_id,
    canonical_transaction_id,
)
from src.core.historical_memory.read_model import (
    HistoricalReadModelCache,
    historical_graph,
    historical_read_model_cache,
)

from src.core.history_context.store import canonical_history_store

historical_store = canonical_history_store
historical_storage_status = {
    "status": "retired",
    "mode": "retired",
    "opened": False,
}

__all__ = [
    "Availability", "DATABASE_MIGRATION_VERSION", "HISTORICAL_SCHEMA_VERSION",
    "PLAYER_HISTORY_SCHEMA_VERSION", "PREDICTION_MODEL_VERSION",
    "HistoricalAssetGraph", "HistoricalStore", "aggregate_production",
    "canonical_event_id", "canonical_pick_id", "canonical_player_id",
    "canonical_trade_id", "canonical_transaction_id", "historical_store",
    "HistoricalReadModelCache", "historical_graph", "historical_read_model_cache",
    "historical_storage_status",
]
