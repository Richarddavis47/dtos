"""Contextual impacts derived from Decision and Asset Intelligence outputs."""
from __future__ import annotations

from src.core.asset_intelligence import Evidence
from src.core.decision_engine import TeamDecision
from src.core.trade_intelligence.models import TradeImpact, TradeProposal


def _sum(assets, attribute: str) -> float:
    return sum(getattr(asset, attribute) for asset in assets)


def _future_value(asset) -> float:
    value = asset.dynasty_value
    if value is None:
        return None
    if (
        asset.kind == "pick" and not asset.exact_slot
        and str(asset.projected_range or "UNKNOWN").upper() == "UNKNOWN"
        and str(asset.projected_range_confidence or "LOW").upper() == "LOW"
    ):
        return value * .75
    return value


def evaluate_trade_impact(proposal: TradeProposal, active: TeamDecision) -> TradeImpact:
    sent = proposal.assets_sent
    received = proposal.assets_received
    current = round(_sum(received, "redraft_value") - _sum(sent, "redraft_value")) if all(a.redraft_value is not None for a in (*sent, *received)) else None
    supported_future = all(asset.dynasty_value is not None for asset in (*sent, *received))
    future = round(sum(_future_value(asset) for asset in received) - sum(_future_value(asset) for asset in sent)) if supported_future else None
    asset_value = round(sum(asset.dynasty_value for asset in received) - sum(asset.dynasty_value for asset in sent)) if supported_future else None
    risk = round(_sum(sent, "risk") - _sum(received, "risk"))
    fit = round(_sum(received, "team_fit_value") - _sum(sent, "team_fit_value")) if all(a.team_fit_value is not None for a in (*sent, *received)) else None
    positions_in = {asset.position for asset in received if asset.position}
    weak_positions = {position for position, evaluation in active.position_evaluations.items() if evaluation.score < 55}
    depth = len(positions_in & weak_positions) * 8
    balance = depth - max(0, len(sent) - len(received)) * 3
    opportunity = max(0, -asset_value) if asset_value is not None else None
    market = round(_sum(received, "market_value") - _sum(sent, "market_value")) if all(asset.market_value is not None for asset in (*sent, *received)) else None
    championship = round(current * 0.60 + fit * 0.40) if current is not None and fit is not None else None
    evidence = (
        Evidence("Current value delta", f"{current:+d}" if current is not None else "Unavailable", current if current is not None else 0, "Unavailable season utility is not weekly expectation or zero.", "Asset Intelligence", current is not None),
        Evidence("Future value delta", f"{future:+d}" if future is not None else "Unavailable", future if future is not None else 0,
            "No validated long-term intrinsic player scalar; do not substitute Market or weekly projection." if future is None else "Dynasty values remain separate from the current horizon.",
            "Intrinsic evidence availability", future is not None),
        Evidence("Team Fit delta", f"{fit:+d}" if fit is not None else "Unavailable", fit if fit is not None else 0, "No unrelated scalar replaces unavailable fit.", "Asset Intelligence", fit is not None),
        Evidence("Decision Engine need coverage", ", ".join(sorted(positions_in & weak_positions)) or "None", depth, "Incoming positions are compared with Decision Engine weaknesses.", "Decision Engine position evaluations"),
    )
    return TradeImpact(current, future, balance, depth, asset_value, risk, opportunity, market, championship, evidence, ("Championship Outlook Impact is a transparent current-value proxy, not a probability change.", "Acceptance probability is unavailable without a validated GM behavior model."))
