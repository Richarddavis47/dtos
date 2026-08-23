"""Asset pools evaluated exclusively through Asset Intelligence."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence import AssetContext, evaluate_pick, evaluate_player
from src.core.trade_intelligence.models import TradeAsset
from src.core.valuation import CalibrationStatus, calibrate_asset_value, normalize_internal, normalize_pick


def _player_asset(
    player: dict[str, Any],
    context: AssetContext,
    source_roster_id: int,
    market_values: dict[str, tuple[int | None, int, CalibrationStatus]],
) -> TradeAsset:
    report = evaluate_player(player, context)
    player_id = report.profile.player_id
    market_value, confidence, status = market_values.get(
        player_id, (None, 0, CalibrationStatus.INSUFFICIENT_DATA),
    )
    intrinsic = normalize_internal(report.core_values.dynasty.score)
    calibrated = calibrate_asset_value(
        intrinsic, market_value, confidence, status=status,
    )
    return TradeAsset(
        player_id,
        "player",
        report.profile.name,
        report.profile.position,
        calibrated.calibrated_value,
        normalize_internal(report.core_values.redraft.score),
        market_value if market_value is not None else normalize_internal(report.core_values.market.score),
        normalize_internal(report.core_values.team_fit.score),
        report.risk.score,
        source_roster_id,
        round((calibrated.calibrated_value + normalize_internal(report.core_values.team_fit.score)) / 2),
        55,
        max(report.recommendation.confidence, confidence),
    )


def _pick_asset(pick: dict[str, Any], context: AssetContext, source_roster_id: int) -> TradeAsset:
    report = evaluate_pick(pick, context)
    asset_id = f"{report.season}-R{report.round}-{pick.get('original_roster_id') or pick.get('roster_id') or 'unknown'}"
    return TradeAsset(
        asset_id,
        "pick",
        f"{report.season} Round {report.round} ({report.original_owner})",
        None,
        normalize_pick(report.dynasty_value.score, report.round),
        normalize_internal(50),
        normalize_pick(report.market_value.score, report.round),
        normalize_pick(report.dynasty_value.score, report.round),
        report.risk.score,
        source_roster_id,
        trade_value=normalize_pick(report.dynasty_value.score, report.round),
        liquidity_score=65 if report.round == 1 else 45,
        confidence_score=report.recommendation.confidence,
        original_roster_id=int(pick.get("original_roster_id") or pick.get("roster_id") or 0) or None,
        current_owner_id=int(pick.get("current_owner_id") or source_roster_id),
        season=int(report.season),
        round=int(report.round),
        projected_range=str(pick.get("projected_range") or "UNKNOWN").upper(),
        projected_range_confidence=str(pick.get("projected_range_confidence") or "LOW").upper(),
        exact_slot=str(pick.get("exact_slot")) if pick.get("exact_slot") else None,
    )


def build_asset_pool(
    data: dict[str, Any],
    team: dict[str, Any],
    recipient_context: AssetContext,
    market_values: dict[str, tuple[int | None, int, CalibrationStatus]] | None = None,
) -> tuple[TradeAsset, ...]:
    roster_id = int(team.get("roster_id") or 0)
    database = data.get("players") or {}
    players = tuple(
        _player_asset(
            {**(database.get(str(player.get("id")), {}) or {}), **player},
            recipient_context,
            roster_id,
            market_values or {},
        )
        for player in team.get("players") or []
        if str(player.get("position") or "") in {"QB", "RB", "WR", "TE"}
    )
    picks = tuple(_pick_asset(pick, recipient_context, roster_id) for pick in team.get("picks_owned") or [])
    return players + picks
