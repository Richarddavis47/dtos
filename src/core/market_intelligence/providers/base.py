"""Provider protocol and cache-aware base implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from src.core.market_intelligence.models import ProviderQuote
from src.core.valuation.normalization import normalize_cached_value
from src.core.valuation.source_time import market_times


class MarketProvider(ABC):
    name: str
    field: str

    @abstractmethod
    def _extract(self, asset: dict[str, Any], market_data: dict[str, Any]) -> tuple[float | None, int, str | None, str]:
        """Return value, confidence, observed timestamp, and detail."""

    def quote(self, asset_id: str, asset: dict[str, Any], market_data: dict[str, Any]) -> ProviderQuote:
        started = perf_counter()
        try:
            value, confidence, observed_at, detail = self._extract(asset, market_data)
            available = value is not None
            row = ((market_data.get('providers') or {}).get(self.name) or {}).get(asset_id)
            row = row if isinstance(row, dict) else {}
            clocks = market_times(row, observed_at)
            normalized = normalize_cached_value(self.name, {**row, 'value': value},
                updated_at=observed_at, provider_confidence=confidence) if available else None
            return ProviderQuote(
                self.name, asset_id, value, normalized.confidence_score if normalized and normalized.method != 'unsupported_provider' else confidence if available else 0, clocks['retrieved_at'], self.name,
                available, detail, round((perf_counter() - started) * 1000, 3), False,
                "live" if available else "unavailable", clocks['retrieved_at'], 0.0,
                normalized.freshness if normalized else "unavailable", 0,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ProviderQuote(
                self.name, asset_id, None, 0, None, self.name, False,
                f"Provider data could not be parsed: {exc}", round((perf_counter() - started) * 1000, 3),
                False, "unavailable", datetime.now(timezone.utc).isoformat(), None, "unavailable", 0,
            )


class FieldMarketProvider(MarketProvider):
    aliases: tuple[str, ...] = ()

    def _extract(self, asset: dict[str, Any], market_data: dict[str, Any]) -> tuple[float | None, int, str | None, str]:
        provider_rows = market_data.get("providers") or {}
        row = (provider_rows.get(self.name) or {}).get(str(asset.get("player_id") or asset.get("id") or ""))
        if isinstance(row, (int, float)):
            return float(row), 70, None, "Cached provider value"
        if isinstance(row, dict):
            raw = row.get("value")
            return (float(raw) if raw is not None else None, int(row.get("confidence") or 70), row.get("updated_at"), str(row.get("detail") or "Cached provider value"))
        for key in (self.field, *self.aliases):
            raw = asset.get(key)
            if raw is not None:
                return float(raw), int(asset.get(f"{key}_confidence") or 65), asset.get(f"{key}_updated_at"), f"Cached {key} field"
        return None, 0, None, "No cached quote is available"
