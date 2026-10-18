"""Read comparison evidence already captured with a canonical selected price.

No provider selection, conversion, fetching or historical persistence happens here.
The prepared asset and its price must belong to the same captured handoff.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
import json
import re
from typing import Any

from .compatibility import comparison_identity, comparison_reasons
from src.core.valuation.consensus import MARKET_SELECTION_VERSION
from src.core.valuation.observation_identity import OBSERVATION_IDENTITY_VERSION


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def current_comparison(data: dict[str, Any], asset_id: str, value: Any) -> dict[str, Any]:
    """Fail closed for bare prices, raw provider units and unbound identities."""
    asset = ((data.get("valuation_intelligence") or {}).get("assets") or {}).get(asset_id) or {}
    layer = ((asset.get("valuation_layers") or {}).get("market_value") or {})
    accepted = asset.get("market_observation_evidence") or {}
    if (asset.get("asset_id") != asset_id or not layer.get("generation") or isinstance(value, bool)
            or not isinstance(value, (int, float)) or not isfinite(value)
            or not 0 <= value <= 1000 or value != layer.get("value")
            or accepted.get("canonical_value") != value):
        return {}
    observations = accepted.get("observations") or ()
    if not observations:
        return {}
    rows, clocks, providers, generations = [], [], [], {}
    now = datetime.now(timezone.utc)
    for observation in observations:
        metadata = observation.get("metadata") or {}
        provider = observation.get("provider")
        generation = observation.get("source_identity")
        stamp = _time(observation.get("observed_at"))
        if (not provider or provider in providers or not generation or stamp is None
                or stamp > now or not observation.get("normalization_version")):
            return {}
        # A retained old quote cannot acquire a later effective source clock.
        for name in ("source_updated_at", "published_at"):
            if metadata.get(name) is not None:
                source_stamp = _time(metadata[name])
                if source_stamp is None or source_stamp > stamp:
                    return {}
        semantic = metadata.get("comparison_semantics") or {}
        if (semantic.get("value_concept") != "external_market_normalized_index"
                or semantic.get("value_scale") != "0-1000"
                or semantic.get("methodology") != MARKET_SELECTION_VERSION + ":" + OBSERVATION_IDENTITY_VERSION):
            return {}
        rows.append({"comparison_semantics": semantic,
                     "providers": (provider,),
                     # This is the provider-price normalization version, not
                     # the sparse-memory record schema's normalization version.
                     "provider_normalization_version": observation["normalization_version"]})
        clocks.append((stamp, observation["observed_at"]))
        providers.append(provider)
        generations[provider] = generation
    # Membership is one combined selected-price identity, not cross-provider
    # agreement about raw units. Each selected leg must carry the same semantics.
    for row in rows:
        row["providers"] = tuple(sorted(providers))
    if (comparison_reasons(rows) or comparison_identity(rows[0]) is None
            or len({row["provider_normalization_version"] for row in rows}) != 1):
        return {}
    try:
        identities = json.loads(rows[0]["comparison_semantics"]["format_key"])
    except (TypeError, ValueError):
        return {}
    if (not isinstance(identities, list) or len(identities) != len(providers)
            or any(not isinstance(item, dict) for item in identities)
            or {item.get("provider") for item in identities} != set(providers)
            or any(item.get("normalization") != rows[0]["provider_normalization_version"]
                   or item.get("method") not in {"provider_range_linear", "provider_range_70_percentile_30"}
                   or not isinstance(item.get("format"), str)
                   or item["format"].casefold() in {"", "unknown", "unavailable"}
                   for item in identities)):
        return {}
    return {**rows[0], "asset_id": asset_id,
            "observed_at": max(clocks)[1], "oldest_observed_at": min(clocks)[1],
            "source_generations": generations, "market_generation": layer.get("generation"),
            "freshness": layer.get("freshness", "unknown"),
            "observation_clock": "canonical_selected_price_observation",
            "source_times": tuple({"provider": row["provider"],
                "observed_at": row.get("observed_at"),
                "source_updated_at": (row.get("metadata") or {}).get("source_updated_at"),
                "retrieved_at": (row.get("metadata") or {}).get("retrieved_at")}
                for row in observations)}
