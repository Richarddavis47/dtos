"""Default provider catalog with explicit licensing-aware enablement."""
from __future__ import annotations

import os

from src.core.data_platform.adapters import CachedMarketAdapter, metadata
from src.core.data_platform.models import LicensingTier
from src.core.data_platform.platform import DataPlatform
from src.core.data_platform.provider import UnavailableProvider
from config import DATA_WAREHOUSE_FILE, MARKET_CACHE_TTL


def _enabled(name: str, default: bool = False) -> bool:
    return os.getenv(f"DTOS_PROVIDER_{name.upper().replace(' ', '_')}", "1" if default else "0").casefold() in {"1", "true", "yes", "on"}


def build_data_platform() -> DataPlatform:
    from src.core.data_platform.storage import SnapshotWarehouse
    platform = DataPlatform(warehouse=SnapshotWarehouse(DATA_WAREHOUSE_FILE), cache_ttl_seconds=MARKET_CACHE_TTL)
    market = (
        ("FantasyCalc", "fantasycalc_value", (), LicensingTier.PUBLIC_API, True),
        ("KeepTradeCut", "ktc_value", ("keeptradecut_value",), LicensingTier.UNSUPPORTED, True),
        ("Sleeper ADP", "sleeper_adp", ("adp",), LicensingTier.PUBLIC_API, True),
        ("DynastyProcess", "dynastyprocess_value", (), LicensingTier.PUBLIC_API, True),
    )
    for name, field, aliases, tier, default in market:
        meta = metadata(name, "market", tier, enabled=_enabled(name, default), live=True, scheduled=True, season=10_800 if name == "FantasyCalc" else 21_600, offseason=43_200)
        platform.register(CachedMarketAdapter(name, field, meta, aliases))

    catalog = (
        ("Sleeper League", "league", LicensingTier.PUBLIC_API, True, 900, 3_600),
        ("Sleeper Transactions", "transactions", LicensingTier.PUBLIC_API, True, 900, 3_600),
        ("Sleeper Trending", "market", LicensingTier.PUBLIC_API, True, 900, 3_600),
        ("Dynasty Daddy", "market", LicensingTier.UNSUPPORTED, False, 86_400, 86_400),
        ("FantasyPros", "rankings", LicensingTier.API_KEY, False, 21_600, 86_400),
        ("Underdog Fantasy ADP", "adp", LicensingTier.UNSUPPORTED, False, 86_400, 86_400),
        ("Sleeper News", "news", LicensingTier.UNSUPPORTED, False, 1_800, 7_200),
        ("Rotowire", "news", LicensingTier.COMMERCIAL, False, 1_800, 7_200),
        ("NBC Sports Edge", "news", LicensingTier.COMMERCIAL, False, 1_800, 7_200),
    )
    for name, category, tier, default, season, offseason in catalog:
        enabled = _enabled(name, default)
        reason = "Live adapter is not configured for this deployment or approved access is unavailable."
        platform.register(UnavailableProvider(metadata(name, category, tier, enabled=enabled, live=enabled, scheduled=enabled, season=season, offseason=offseason), reason))
    return platform


data_platform = build_data_platform()
