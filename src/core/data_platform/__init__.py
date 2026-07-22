"""Public Live Data Platform contracts and singleton boundary."""
from src.core.data_platform.aggregation import consensus, trend
from src.core.data_platform.defaults import data_platform
from src.core.data_platform.models import ConsensusResult, DataEnvelope, DataQuality, LicensingTier, ProviderHealth, ProviderMetadata, ProviderStatus, RefreshResult, TrendResult
from src.core.data_platform.news import NewsIntelligence, interpret_news
from src.core.data_platform.platform import DataPlatform
from src.core.data_platform.provider import DataProvider, UnavailableProvider
from src.core.data_platform.registry import ProviderRegistry
from src.core.data_platform.scheduler import RefreshSchedule, RefreshScheduler
from src.core.data_platform.storage import SnapshotWarehouse

__all__ = ["ConsensusResult", "DataEnvelope", "DataPlatform", "DataProvider", "DataQuality", "LicensingTier", "NewsIntelligence", "ProviderHealth", "ProviderMetadata", "ProviderRegistry", "ProviderStatus", "RefreshResult", "RefreshSchedule", "RefreshScheduler", "SnapshotWarehouse", "TrendResult", "UnavailableProvider", "consensus", "data_platform", "interpret_news", "trend"]
