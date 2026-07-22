"""Adapters that place existing approved/cached sources behind the Data Platform."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.data_platform.models import DataEnvelope, DataQuality, LicensingTier, ProviderMetadata
from src.core.data_platform.provider import DataProvider
class CachedMarketAdapter(DataProvider):
    def __init__(self, provider_name: str, field: str, metadata: ProviderMetadata, aliases: tuple[str, ...] = ()) -> None:
        self.provider_name = provider_name
        self.field = field
        self.metadata = metadata
        self.aliases = aliases

    def fetch(self, key: str, context: dict[str, Any]) -> DataEnvelope:
        asset = dict(context.get("asset") or {})
        market_data = dict(context.get("market_data") or {})
        provider_rows = market_data.get("providers") or {}
        row = (provider_rows.get(self.provider_name) or {}).get(str(asset.get("player_id") or asset.get("id") or key))
        value: float | None = None
        confidence = 0
        observed_at: str | None = None
        detail = "No cached quote is available"
        if isinstance(row, (int, float)):
            value, confidence, detail = float(row), 70, "Cached provider value"
        elif isinstance(row, dict):
            raw = row.get("value")
            value = float(raw) if raw is not None else None
            confidence = int(row.get("confidence") or 70)
            observed_at = row.get("updated_at")
            detail = str(row.get("detail") or "Cached provider value")
        else:
            for field in (self.field, *self.aliases):
                raw = asset.get(field)
                if raw is not None:
                    value = float(raw)
                    confidence = int(asset.get(f"{field}_confidence") or 65)
                    observed_at = asset.get(f"{field}_updated_at")
                    detail = f"Cached {field} field"
                    break
        available = value is not None
        quality = DataQuality("good" if available else "blocked", () if available else (detail,), 100 if available else 0)
        return DataEnvelope(key, self.metadata.category, value, self.provider_name, self.provider_name, observed_at or datetime.now(timezone.utc).isoformat(), "fresh" if available else "unavailable", confidence if available else 0, "miss", "live" if available else "unavailable", quality, () if available else (detail,))


def metadata(name: str, category: str, tier: LicensingTier, *, enabled: bool, live: bool, scheduled: bool, season: int, offseason: int, version: str = "v1") -> ProviderMetadata:
    return ProviderMetadata(name, category, version, tier, enabled, live, scheduled, season, offseason)
