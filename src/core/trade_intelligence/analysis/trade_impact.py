"""Contextual impacts derived from Decision and Asset Intelligence outputs."""
from __future__ import annotations

from src.core.asset_intelligence import Evidence
from src.core.decision_engine import TeamDecision
from src.core.trade_intelligence.models import TradeImpact, TradeProposal


def _average(assets, attribute: str) -> float:
    return sum(getattr(asset, attribute) for asset in assets) / max(1, len(assets))


def evaluate_trade_impact(proposal: TradeProposal, active: TeamDecision) -> TradeImpact:
    sent = proposal.assets_sent
    received = proposal.assets_received
    current = round(_average(received, "redraft_value") - _average(sent, "redraft_value"))
    future = round(_average(received, "dynasty_value") - _average(sent, "dynasty_value"))
    asset_value = round(sum(asset.dynasty_value for asset in received) - sum(asset.dynasty_value for asset in sent))
    risk = round(_average(sent, "risk") - _average(received, "risk"))
    fit = round(_average(received, "team_fit_value") - _average(sent, "team_fit_value"))
    positions_in = {asset.position for asset in received if asset.position}
    weak_positions = {position for position, evaluation in active.position_evaluations.items() if evaluation.score < 55}
    depth = len(positions_in & weak_positions) * 8
    balance = depth - max(0, len(sent) - len(received)) * 3
    opportunity = max(0, -asset_value)
    market = round(_average(received, "market_value") - _average(sent, "market_value"))
    championship = round(current * 0.60 + fit * 0.40)
    evidence = (
        Evidence("Current value delta", f"{current:+d}", current, "Redraft values from Asset Intelligence compare received and sent assets.", "Asset Intelligence Redraft Value"),
        Evidence("Future value delta", f"{future:+d}", future, "Dynasty values remain separate from the current horizon.", "Asset Intelligence Dynasty Value"),
        Evidence("Team Fit delta", f"{fit:+d}", fit, "Front Office-specific Team Fit compares the package in the active context.", "Asset Intelligence Team Fit Value"),
        Evidence("Decision Engine need coverage", ", ".join(sorted(positions_in & weak_positions)) or "None", depth, "Incoming positions are compared with Decision Engine weaknesses.", "Decision Engine position evaluations"),
    )
    return TradeImpact(current, future, balance, depth, asset_value, risk, opportunity, market, championship, evidence, ("Championship Outlook Impact is a transparent current-value proxy, not a probability change.", "Acceptance probability is unavailable without a validated GM behavior model."))
