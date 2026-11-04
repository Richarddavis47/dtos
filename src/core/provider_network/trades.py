"""League-isolated, quality-weighted observed trade evidence."""
from __future__ import annotations

from typing import Any

from src.core.provider_network.contracts import TradeObservation


def observed_trades(data: dict[str, Any]) -> tuple[tuple[TradeObservation, ...], dict[str, int]]:
    league_id = str((data.get("league") or {}).get("league_id") or "active-league")
    seen: set[str] = set()
    included: list[TradeObservation] = []
    excluded = {"duplicate": 0, "not_completed_trade": 0, "incomplete": 0, "administrative": 0, "outlier": 0}
    for raw in data.get("transactions") or []:
        transaction_id = str(raw.get("transaction_id") or "")
        if not transaction_id or transaction_id in seen:
            excluded["duplicate"] += 1
            continue
        seen.add(transaction_id)
        if raw.get("type") != "trade" or str(raw.get("status") or "").casefold() not in {"complete", "completed"}:
            excluded["not_completed_trade"] += 1
            continue
        roster_ids = tuple(sorted({str(item) for item in raw.get("roster_ids") or []}))
        if len(roster_ids) != 2:
            excluded["incomplete"] += 1
            continue
        adds = {str(key): str(value) for key, value in (raw.get("adds") or {}).items()}
        picks = raw.get("draft_picks") or []
        sides: dict[str, list[str]] = {roster_ids[0]: [], roster_ids[1]: []}
        for player_id, owner in adds.items():
            if owner in sides:
                sides[owner].append(f"player:{player_id}")
        for pick in picks:
            owner = str(pick.get("owner_id") or "")
            if owner in sides:
                sides[owner].append(f"pick:{pick.get('season')}:{pick.get('round')}:{pick.get('roster_id')}")
        if not all(sides.values()):
            excluded["incomplete"] += 1
            continue
        asset_count = sum(len(row) for row in sides.values())
        quality = max(25, 100 - max(0, asset_count - 6) * 8)
        outlier = "review" if asset_count >= 10 else "normal"
        included.append(TradeObservation(transaction_id, league_id, str(raw.get("created") or "") or None, tuple(sorted(sides[roster_ids[0]])), tuple(sorted(sides[roster_ids[1]])), "active league", quality, outlier, round(max(len(sides[roster_ids[0]]), len(sides[roster_ids[1]])) / min(len(sides[roster_ids[0]]), len(sides[roster_ids[1]])), 2)))
    return tuple(included), excluded
