"""Provider-format normalization with explicit reconciliation metadata."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.data_platform.normalization.identity import PlayerIdentityResolver
from src.core.data_platform.normalization.models import NormalizedValue


class ProviderNormalizer:
    def __init__(self, resolver: PlayerIdentityResolver) -> None:
        self.resolver = resolver

    def value(self, provider: str, identifier: str, row: Any, *, name: str | None = None) -> NormalizedValue:
        mapping = row if isinstance(row, dict) else {"value": row}
        player = self.resolver.resolve(identifier, provider, name) or self.resolver.resolve(identifier, "Sleeper", name)
        warnings: list[str] = []
        if player is None:
            warnings.append("Provider player identifier did not resolve to a canonical DTOS player.")
        raw = mapping.get("value", mapping.get("trade_value"))
        try:
            value = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            value = None
            warnings.append("Provider value is not numeric.")
        if value is not None and not 0 <= value <= 1_000_000:
            value = None
            warnings.append("Provider value is outside accepted bounds.")
        timestamp = normalize_timestamp(mapping.get("updated_at") or mapping.get("timestamp"))
        confidence = normalize_confidence(mapping.get("confidence", 70))
        return NormalizedValue(player.dtos_id if player else identifier, provider, value, _integer(mapping.get("rank")), _integer(mapping.get("position_rank")), str(mapping["tier"]) if mapping.get("tier") is not None else None, _float(mapping.get("adp")), timestamp, confidence, "value", tuple(warnings))


def normalize_timestamp(value: Any) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def normalize_confidence(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if 0 <= number <= 1:
        number *= 100
    return max(0, min(100, round(number)))


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
