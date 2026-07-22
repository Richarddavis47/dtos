"""Adapters that place existing approved/cached sources behind the Data Platform."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.data_platform.models import DataEnvelope, DataQuality, LicensingTier, ProviderMetadata
from src.core.data_platform.normalization import PlayerIdentityResolver, ProviderNormalizer
from src.core.data_platform.provider import DataProvider
class CachedMarketAdapter(DataProvider):
    def __init__(self, provider_name: str, field: str, metadata: ProviderMetadata, aliases: tuple[str, ...] = ()) -> None:
        self.provider_name = provider_name
        self.field = field
        self.metadata = metadata
        self.aliases = aliases

    def fetch(self, key: str, context: dict[str, Any]) -> DataEnvelope:
        asset = dict(context.get("asset") or {})
        asset.setdefault("player_id", key)
        market_data = dict(context.get("market_data") or {})
        provider_rows = market_data.get("providers") or {}
        row = (provider_rows.get(self.provider_name) or {}).get(str(asset.get("player_id") or asset.get("id") or key))
        normalized_row: dict[str, Any] = {}
        detail = "No normalized provider value is available"
        if isinstance(row, (int, float)):
            normalized_row, detail = {"value": row, "confidence": 70}, "Cached provider value"
        elif isinstance(row, dict):
            normalized_row = row
            detail = str(row.get("detail") or "Cached provider value")
        else:
            for field in (self.field, *self.aliases):
                raw = asset.get(field)
                if raw is not None:
                    normalized_row = {"value": raw, "confidence": asset.get(f"{field}_confidence") or 65, "updated_at": asset.get(f"{field}_updated_at")}
                    detail = f"Cached {field} field"
                    break
        resolver = PlayerIdentityResolver({key: asset})
        normalized = ProviderNormalizer(resolver).value(self.provider_name, key, normalized_row, name=asset.get("full_name"))
        available = normalized.value is not None and not normalized.warnings
        issues = normalized.warnings or (() if available else (detail,))
        quality = DataQuality("good" if available else "blocked", issues, 100 if available else 0)
        metadata = {"contract": "NormalizedValue", "dtos_id": normalized.dtos_id, "source_field": normalized.source_field}
        return DataEnvelope(normalized.dtos_id, self.metadata.category, normalized.value, self.provider_name, self.provider_name, normalized.timestamp or datetime.now(timezone.utc).isoformat(), "fresh" if available else "unavailable", normalized.confidence if available else 0, "miss", "live" if available else "unavailable", quality, () if available else (detail,), "Live" if available else "Unavailable", 60, metadata)


def metadata(name: str, category: str, tier: LicensingTier, *, enabled: bool, live: bool, scheduled: bool, season: int, offseason: int, version: str = "v1") -> ProviderMetadata:
    return ProviderMetadata(name, category, version, tier, enabled, live, scheduled, season, offseason)
