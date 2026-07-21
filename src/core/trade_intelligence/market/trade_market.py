"""Asset pools evaluated exclusively through Asset Intelligence."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence import AssetContext, evaluate_pick, evaluate_player
from src.core.trade_intelligence.models import TradeAsset


def _player_asset(player: dict[str, Any], context: AssetContext, source_roster_id: int) -> TradeAsset:
    report = evaluate_player(player, context)
    return TradeAsset(
        report.profile.player_id,
        "player",
        report.profile.name,
        report.profile.position,
        report.core_values.dynasty.score,
        report.core_values.redraft.score,
        report.core_values.market.score,
        report.core_values.team_fit.score,
        report.risk.score,
        source_roster_id,
    )


def _pick_asset(pick: dict[str, Any], context: AssetContext, source_roster_id: int) -> TradeAsset:
    report = evaluate_pick(pick, context)
    asset_id = f"{report.season}-R{report.round}-{pick.get('original_roster_id') or pick.get('roster_id') or 'unknown'}"
    return TradeAsset(
        asset_id,
        "pick",
        f"{report.season} Round {report.round} ({report.original_owner})",
        None,
        report.dynasty_value.score,
        50,
        report.market_value.score,
        report.dynasty_value.score,
        report.risk.score,
        source_roster_id,
    )


def build_asset_pool(
    data: dict[str, Any],
    team: dict[str, Any],
    recipient_context: AssetContext,
) -> tuple[TradeAsset, ...]:
    roster_id = int(team.get("roster_id") or 0)
    database = data.get("players") or {}
    players = tuple(
        _player_asset({**(database.get(str(player.get("id")), {}) or {}), **player}, recipient_context, roster_id)
        for player in team.get("players") or []
        if str(player.get("position") or "") in {"QB", "RB", "WR", "TE"}
    )
    picks = tuple(_pick_asset(pick, recipient_context, roster_id) for pick in team.get("picks_owned") or [])
    return players + picks
