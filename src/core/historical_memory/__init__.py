"""Historical League Memory and Player Performance Intelligence."""
from config import HISTORY_DATABASE_FILE
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

historical_store = HistoricalStore(HISTORY_DATABASE_FILE)

__all__ = [
    "Availability", "DATABASE_MIGRATION_VERSION", "HISTORICAL_SCHEMA_VERSION",
    "PLAYER_HISTORY_SCHEMA_VERSION", "PREDICTION_MODEL_VERSION",
    "HistoricalAssetGraph", "HistoricalStore", "aggregate_production",
    "canonical_event_id", "canonical_pick_id", "canonical_player_id",
    "canonical_trade_id", "canonical_transaction_id", "historical_store",
    "HistoricalReadModelCache", "historical_graph", "historical_read_model_cache",
]
