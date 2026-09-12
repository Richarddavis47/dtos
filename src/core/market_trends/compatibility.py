"""Fail-closed comparison identity for sparse Market observations.

An opaque context hash or a matching legacy normalization version alone is not
evidence that two numbers have the same meaning. Never infer units from prices.
"""
from __future__ import annotations

from typing import Any

FIELDS = ("value_concept", "value_scale", "format_key", "methodology")


def comparison_identity(row: dict[str, Any]) -> tuple[str, ...] | None:
    semantic = row.get("comparison_semantics") or {}
    if not isinstance(semantic, dict):
        return None
    values = tuple(semantic.get(name) for name in FIELDS)
    if not all(isinstance(value, str) and value.strip() and value.casefold() not in
               {"unknown", "unavailable"} for value in values):
        return None
    # Provider membership is part of the measured market, not evidence of
    # independent consensus. This also prevents raw cross-provider comparisons.
    providers = tuple(sorted(set(row.get("providers") or ())))
    if not providers:
        return None
    return (*values, *providers)


def comparison_reasons(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    if not rows:
        return ()
    reasons = []
    methods = {row.get("model_version") for row in rows if row.get("model_version")}
    explicit_methods = {(row.get("comparison_semantics") or {}).get("methodology")
                        for row in rows}
    if len(methods) > 1 or len(explicit_methods - {None}) > 1:
        reasons.append("METHODOLOGY_VERSION_CHANGED")
    identities = [comparison_identity(row) for row in rows]
    if any(identity is None for identity in identities):
        reasons.append("COMPARABLE_HISTORY_UNAVAILABLE")
    elif len(set(identities)) > 1:
        reasons.append("INCOMPATIBLE_OBSERVATION_BOUNDARY")
    contexts = {row.get("market_context_id") for row in rows if row.get("market_context_id")}
    normalizations = {row.get("normalization_version") for row in rows if row.get("normalization_version")}
    if len(contexts) > 1 or len(normalizations) > 1:
        reasons.append("INCOMPATIBLE_OBSERVATION_BOUNDARY")
    return tuple(dict.fromkeys(reasons))
