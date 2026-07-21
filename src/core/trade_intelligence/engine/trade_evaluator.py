"""Trade dossier evaluation and classification."""
from __future__ import annotations

from src.core.asset_intelligence import Evidence
from src.core.decision_engine import TeamDecision, TeamWindow
from src.core.trade_intelligence.analysis import evaluate_trade_impact
from src.core.trade_intelligence.engine.negotiation_engine import build_negotiation_plan
from src.core.trade_intelligence.models import (
    PartnerReport,
    TradeDossier,
    TradePriority,
    TradeProposal,
    TradeRecommendation,
    TradeType,
)


def _package_value(assets) -> float:
    return sum((asset.dynasty_value + asset.team_fit_value) / 2 for asset in assets)


def _trade_type(proposal: TradeProposal, active: TeamDecision, current: int, future: int, depth: int) -> TradeType:
    if active.window in {TeamWindow.CHAMPIONSHIP, TeamWindow.PLAYOFF} and current > 0:
        return TradeType.CHAMPIONSHIP_PUSH
    if active.window in {TeamWindow.REBUILD, TeamWindow.ASCENSION} and future > 0:
        return TradeType.REBUILD
    if any(asset.kind == "pick" for asset in proposal.assets_received):
        return TradeType.PICK_ACQUISITION
    if len(proposal.assets_sent) > len(proposal.assets_received):
        return TradeType.ELITE_CONSOLIDATION
    if depth > 0:
        return TradeType.DEPTH_UPGRADE
    if current * future < 0:
        return TradeType.AGE_SWAP
    return TradeType.ROSTER_BALANCE


def evaluate_proposal(
    proposal: TradeProposal,
    active: TeamDecision,
    partner: PartnerReport,
    alternatives: tuple[str, ...],
) -> TradeDossier:
    impact = evaluate_trade_impact(proposal, active)
    expected = round(impact.current_outlook * 0.30 + impact.future_outlook * 0.30 + impact.positional_depth * 0.20 + impact.asset_value * 0.20)
    trade_type = _trade_type(proposal, active, impact.current_outlook, impact.future_outlook, impact.positional_depth)
    if expected >= 12 and partner.compatibility_score >= 70:
        priority = TradePriority.HIGH
    elif expected >= 5:
        priority = TradePriority.MEDIUM
    elif expected >= 0:
        priority = TradePriority.LOW
    else:
        priority = TradePriority.FUTURE_WATCH
    sent_value, received_value = _package_value(proposal.assets_sent), _package_value(proposal.assets_received)
    gap = abs(received_value - sent_value) / max(sent_value, received_value, 1)
    confidence = max(35, min(92, round(50 + partner.compatibility_score * 0.30 - gap * 30)))
    evidence = impact.evidence + partner.evidence + (
        Evidence("Package balance", f"{sent_value:.1f} offered / {received_value:.1f} requested", (1 - gap) * 20, "Packages are generated only inside a 20% to 25% blended Asset Intelligence boundary.", "Trade Generator package boundary"),
    )
    sent_labels = " + ".join(asset.label for asset in proposal.assets_sent)
    received_labels = " + ".join(asset.label for asset in proposal.assets_received)
    recommendation = TradeRecommendation(
        f"Explore {received_labels} with {partner.team_name}",
        f"Send {sent_labels} in a {proposal.package_type} framework; review evidence before contacting the partner.",
        trade_type,
        priority,
        confidence,
        expected,
        None,
        evidence,
    )
    return TradeDossier(
        proposal,
        partner,
        recommendation,
        impact,
        build_negotiation_plan(proposal, alternatives),
        f"A {trade_type.value} opportunity with {partner.owner_name}, generated from complementary roster context and balanced Asset Intelligence values.",
        tuple(item.explanation for item in impact.evidence if item.impact > 0) or ("Package balance is within the v1 realism boundary.",),
        tuple(item.explanation for item in impact.evidence if item.impact < 0) or ("No measured horizon has a negative delta above the v1 threshold.",),
        ("Acceptance likelihood is unavailable without validated GM behavior data.", "Player news and market movement may change values after the cached snapshot."),
        f"The incoming package has {received_value:.1f} blended dynasty/fit value in the Active Front Office context.",
        f"The offered package has {sent_value:.1f} blended dynasty/fit value in {partner.team_name}'s context.",
        f"The package ratio is {(received_value / max(sent_value, 1)):.2f}, inside the generator's documented balance boundary; this does not predict acceptance.",
        f"The Active Front Office is classified in the {active.window.value}, so current and future impacts are evaluated separately now.",
    )
