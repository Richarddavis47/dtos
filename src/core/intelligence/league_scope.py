"""Fail-closed league identity checks for private derived intelligence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ScopedEvidence:
    """A bounded, league-validated view of one roster-keyed evidence mapping."""

    rows: dict[str, dict[str, Any]]
    rejected: int = 0


def league_id_from_data(data: Mapping[str, Any]) -> str:
    """Resolve the canonical league identity carried by a hydrated data set."""
    league = data.get("league") or {}
    return str(league.get("league_id") or data.get("league_id") or "")


def scoped_evidence(
    data: Mapping[str, Any], field: str, *, expected_league_id: str | None = None,
) -> ScopedEvidence:
    """Return only private evidence whose source league matches the consumer."""
    expected = str(expected_league_id or league_id_from_data(data))
    source = data.get(field) or {}
    if not isinstance(source, Mapping) or not expected:
        return ScopedEvidence({}, len(source) if isinstance(source, Mapping) else 0)
    rows: dict[str, dict[str, Any]] = {}
    rejected = 0
    for key, value in source.items():
        if not isinstance(value, Mapping):
            rejected += 1
            continue
        row = dict(value)
        if str(row.get("league_id") or "") != expected:
            rejected += 1
            continue
        rows[str(key)] = row
    return ScopedEvidence(rows, rejected)


def scoped_market_trends(
    data: Mapping[str, Any], asset_ids: tuple[str, ...], *, league_id: str,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Preserve global trend data while rejecting wrong-league liquidity."""
    source = data.get("market_trend_summaries") or {}
    if not isinstance(source, Mapping):
        return {}, 0
    trends: dict[str, dict[str, Any]] = {}
    rejected = 0
    for asset_id in asset_ids:
        value = source.get(asset_id) or {}
        if not isinstance(value, Mapping):
            continue
        row = dict(value)
        liquidity = row.get("league_liquidity")
        if isinstance(liquidity, Mapping):
            if str(liquidity.get("league_id") or "") != league_id:
                row.pop("league_liquidity", None)
                rejected += 1
            else:
                row["league_liquidity"] = dict(liquidity)
        trends[asset_id] = row
    return trends, rejected
