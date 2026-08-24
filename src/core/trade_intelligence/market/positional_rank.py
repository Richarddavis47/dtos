"""Generation-local neutral-market positional ranks for Trade Intelligence."""
from __future__ import annotations

from dataclasses import replace

from src.core.trade_intelligence.models import TradeAsset


def apply_positional_ranks(
    pools: dict[int, tuple[TradeAsset, ...]],
) -> dict[int, tuple[TradeAsset, ...]]:
    """Apply one deterministic league-wide rank contract without persistence."""
    players = [asset for pool in pools.values() for asset in pool if asset.kind == "player"]
    ranked: dict[str, str] = {}
    for position in ("QB", "RB", "WR", "TE"):
        rows = sorted(
            (asset for asset in players if asset.position == position),
            key=lambda asset: (-asset.trade_value, asset.label.casefold(), asset.asset_id),
        )
        ranked.update({asset.asset_id: f"{position}{index}" for index, asset in enumerate(rows, 1)})
    return {
        roster_id: tuple(replace(asset, positional_rank=ranked.get(asset.asset_id)) for asset in pool)
        for roster_id, pool in pools.items()
    }
