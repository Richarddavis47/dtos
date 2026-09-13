"""Asset pools evaluated exclusively through Asset Intelligence."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence import AssetContext, evaluate_pick, evaluate_player
from src.core.trade_intelligence.models import TradeAsset
from src.core.valuation import CalibrationStatus


def _team_strength(team: dict[str, Any]) -> float | None:
    """Return a bounded neutral strength signal from already-synchronized facts."""
    values = []
    for key in ("points_for", "max_points"):
        try:
            value = float(team.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            values.append(value)
    wins = team.get("wins")
    losses = team.get("losses")
    try:
        games = float(wins or 0) + float(losses or 0) + float(team.get("ties") or 0)
        if games:
            # Put win rate on the same broad scale as season points without
            # pretending it predicts an exact future draft slot.
            values.append((float(wins or 0) / games) * 1500)
    except (TypeError, ValueError):
        pass
    return sum(values) / len(values) if values else None


def _pick_context(pick: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Consume prepared range evidence; the Trade adapter cannot forecast it."""
    from src.core.intelligence.pick_context import assess_pick_range
    result = assess_pick_range(pick, league_id=str((data.get('league') or {}).get('league_id') or ''))
    if result.get("exact_slot_established") is not True:
        result.pop("exact_slot", None)
    return result


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
    return TradeAsset(
        player_id,
        "player",
        report.profile.name,
        report.profile.position,
        None,  # No validated long-term player intrinsic scalar.
        None,
        market_value,
        None,
        report.risk.score,
        source_roster_id,
        market_value,
        55,
        confidence,
        calibration_status=status.value,
        age=report.profile.age,
    )


def _pick_asset(pick: dict[str, Any], context: AssetContext, source_roster_id: int,
                market_data: dict[str, Any] | None = None) -> TradeAsset:
    report = evaluate_pick(pick, context)
    asset_id = f"{report.season}-R{report.round}-{pick.get('original_roster_id') or pick.get('roster_id') or 'unknown'}"
    from src.core.data_platform.pick_quotes import canonical_pick_market
    evidence = canonical_pick_market({**pick, 'year': report.season, 'round': report.round}, market_data or {})
    neutral_value = evidence['normalized_market_price']
    return TradeAsset(
        asset_id,
        "pick",
        f"{report.season} Round {report.round} ({report.original_owner})",
        None,
        None,  # No supported independent long-term pick utility scalar.
        None,  # A future pick is not current weekly production.
        neutral_value,
        None,  # Team-specific fit is not the legacy option score.
        report.risk.score,
        source_roster_id,
        trade_value=neutral_value,
        liquidity_score=65 if report.round == 1 else 45,
        confidence_score=int((evidence.get('quote') or {}).get('confidence', 0)) if neutral_value is not None else 0,
        calibration_status=(CalibrationStatus.PARTIALLY_CALIBRATED if neutral_value is not None else CalibrationStatus.INSUFFICIENT_DATA).value,
        pick_market_evidence=evidence,
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
    picks = tuple(
        _pick_asset(_pick_context(pick, data), recipient_context, roster_id, data.get('market_data'))
        for pick in team.get("picks_owned") or []
    )
    return players + picks
