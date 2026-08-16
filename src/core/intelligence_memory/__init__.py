"""Sleeper-backed cache and compact permanent DTOS intelligence memory."""
from __future__ import annotations

from config import (
    INTELLIGENCE_CHECKPOINT_FILE, SLEEPER_SEASON_CACHE_ROOT,
)

from .chain import SeasonChain, SeasonReference, discover_season_chain
from .confidence import temporal_confidence
from .fois import fois_process_evidence
from .models import (
    CheckpointTrigger, EvidenceCompleteness, EvidencePersistenceDecision, GlobalMarketObservation,
    HistoricalResolutionState,
    HistoricalTradeAssessment, IntelligenceCheckpoint, MarketObservationDecision,
    MarketObservationReference, PickLineage, ProvenanceType, SourceObservation,
)
from .market_memory import MarketObservationMaterialityPolicy, market_context_id
from .historical_resolver import (
    HistoricalMarketProvider, HistoricalMarketResolver, HistoricalProviderCache,
    HistoricalProviderRateLimitError, HistoricalResolution, PersistenceContext,
    persistence_decision,
)
from .historical_providers import DynastyProcessHistoricalProvider
from .trade_resolution import HistoricalTradeResolutionService, TradeResolutionSummary
from .ownership import DATA_OWNERSHIP
from .market import HistoricalMarketSelection, current_market_value, select_historical_market
from .season_cache import CachedSeason, SleeperSeasonCache
from .service import IntelligenceMemoryService
from .pipeline import CheckpointPipeline
from .store import IntelligenceCheckpointStore

intelligence_checkpoint_store = IntelligenceCheckpointStore(INTELLIGENCE_CHECKPOINT_FILE)
sleeper_season_cache = SleeperSeasonCache(SLEEPER_SEASON_CACHE_ROOT)
intelligence_memory_service = IntelligenceMemoryService(intelligence_checkpoint_store)
checkpoint_pipeline = CheckpointPipeline(intelligence_memory_service)
historical_market_provider = DynastyProcessHistoricalProvider()
historical_market_resolver = HistoricalMarketResolver(
    intelligence_checkpoint_store, (historical_market_provider,),
)
historical_trade_resolution_service = HistoricalTradeResolutionService(
    historical_market_resolver,
)

__all__ = [
    "CachedSeason", "CheckpointTrigger", "DATA_OWNERSHIP", "EvidenceCompleteness",
    "EvidencePersistenceDecision", "GlobalMarketObservation", "HistoricalMarketSelection", "HistoricalResolutionState", "HistoricalTradeAssessment", "IntelligenceCheckpoint",
    "HistoricalMarketProvider", "HistoricalMarketResolver", "HistoricalProviderCache",
    "HistoricalProviderRateLimitError", "HistoricalResolution", "PersistenceContext", "persistence_decision",
    "DynastyProcessHistoricalProvider", "HistoricalTradeResolutionService",
    "TradeResolutionSummary", "historical_market_provider",
    "historical_market_resolver", "historical_trade_resolution_service",
    "IntelligenceCheckpointStore", "IntelligenceMemoryService", "CheckpointPipeline",
    "MarketObservationDecision", "MarketObservationMaterialityPolicy",
    "MarketObservationReference", "PickLineage", "ProvenanceType", "SeasonChain", "SeasonReference",
    "SleeperSeasonCache", "SourceObservation", "discover_season_chain",
    "current_market_value", "fois_process_evidence", "intelligence_checkpoint_store",
    "intelligence_memory_service", "checkpoint_pipeline", "select_historical_market",
    "market_context_id", "sleeper_season_cache", "temporal_confidence",
]
