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

historical_store = HistoricalStore(HISTORY_DATABASE_FILE)

__all__ = [
    "Availability", "DATABASE_MIGRATION_VERSION", "HISTORICAL_SCHEMA_VERSION",
    "PLAYER_HISTORY_SCHEMA_VERSION", "PREDICTION_MODEL_VERSION",
    "HistoricalStore", "aggregate_production", "historical_store",
]
