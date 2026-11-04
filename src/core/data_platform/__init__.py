"""Public Live Data Platform contracts and singleton boundary."""
from src.core.data_platform.aggregation import consensus, trend
from src.core.data_platform.models import ConsensusResult, DataEnvelope, DataQuality, LicensingTier, ProviderHealth, ProviderMetadata, ProviderStatus, RefreshResult, TrendResult
from src.core.data_platform.news import NewsIntelligence, interpret_news
from src.core.data_platform.normalization import NormalizedPlayer, NormalizedValue, PlayerIdentityResolver, ProviderNormalizer
from src.core.data_platform.reliability import ReliabilityTracker
from src.core.data_platform.platform import DataPlatform
from src.core.data_platform.provider import DataProvider, UnavailableProvider
from src.core.data_platform.registry import ProviderRegistry
from src.core.data_platform.scheduler import RefreshSchedule, RefreshScheduler
from src.core.data_platform.storage import SnapshotWarehouse


def __getattr__(name):
    # Public-evidence workers import normalizers without loading the unrelated
    # legacy warehouse into their heap. Existing singleton consumers are unchanged.
    if name == "data_platform":
        from src.core.data_platform.defaults import data_platform
        globals()[name] = data_platform
        return data_platform
    raise AttributeError(name)

__all__ = ["ConsensusResult", "DataEnvelope", "DataPlatform", "DataProvider", "DataQuality", "LicensingTier", "NewsIntelligence", "NormalizedPlayer", "NormalizedValue", "PlayerIdentityResolver", "ProviderHealth", "ProviderMetadata", "ProviderNormalizer", "ProviderRegistry", "ProviderStatus", "RefreshResult", "RefreshSchedule", "RefreshScheduler", "ReliabilityTracker", "SnapshotWarehouse", "TrendResult", "UnavailableProvider", "consensus", "data_platform", "interpret_news", "trend"]
