"""Canonical bilateral trade evaluation shared by every Trade Center workflow."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from src.core.trade_intelligence.lineup import optimal_legal_lineup
from src.core.trade_intelligence.models import TradeAsset, TradeProposal
from src.core.valuation import adjusted_package_value


class ManagerRecommendation(str, Enum):
    SMASH_ACCEPT = "SMASH ACCEPT"
    WORTH_PURSUING = "WORTH PURSUING"
    FAIR_OPTIONAL = "FAIR / OPTIONAL"
    NOT_WORTH_IT = "NOT WORTH IT"
    REJECT = "REJECT"


@dataclass(frozen=True)
class EvaluationDimension:
    label: str
    assessment: str
    explanation: str


def _value(assets: tuple[TradeAsset, ...]) -> float:
    return float(adjusted_package_value(assets).adjusted_value)


def _package_quality(received: tuple[TradeAsset, ...], outgoing: tuple[TradeAsset, ...]) -> EvaluationDimension:
    received_value = _value(received)
    centerpiece = max((asset.trade_value or asset.dynasty_value for asset in outgoing), default=0)
    best_incoming = max((asset.trade_value or asset.dynasty_value for asset in received), default=0)
    useful = sum(1 for asset in received if (asset.trade_value or asset.dynasty_value) >= max(20, centerpiece * 0.35))
    roster_spots = max(0, len(received) - len(outgoing))
    if centerpiece and len(received) >= 3 and best_incoming < centerpiece * 0.60 and useful <= 1:
        return EvaluationDimension("Package Quality", "POOR", "Fair on paper, but the package relies on secondary pieces rather than a credible centerpiece.")
    if roster_spots >= 3 and received_value:
        return EvaluationDimension("Package Quality", "QUESTIONABLE", "The receiving roster must have capacity for the additional assets; displaced-player cost matters.")
    if useful >= 2:
        return EvaluationDimension("Package Quality", "USEFUL DEPTH", "Multiple incoming assets carry meaningful roster or lineup utility, so no automatic multi-asset penalty applies.")
    return EvaluationDimension("Package Quality", "COHERENT", "The package has a usable centerpiece and bounded roster-capacity cost.")


def _qualitative_confidence(assets: tuple[TradeAsset, ...]) -> tuple[str, str]:
    score = min((asset.confidence_score for asset in assets), default=0)
    if score >= 75:
        return "HIGH", "Current market and asset evidence is strong."
    if score >= 50:
        return "MEDIUM", "Some market, projection, or future-pick uncertainty remains."
    return "LOW", "Material evidence is unavailable or weak; treat the conclusion cautiously."


def _team_players(team: dict[str, Any], assets_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**assets_by_id.get(str(p.get("id") or p.get("player_id")), {}), **p} for p in team.get("players") or ()]


def evaluate_bilateral(
    proposal: TradeProposal,
    *,
    active_team: dict[str, Any],
    partner_team: dict[str, Any],
    league: dict[str, Any],
    player_database: dict[str, dict[str, Any]] | None = None,
    ownership: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Evaluate one exact construction; workflow does not influence analytical truth."""
    ownership = ownership or {}
    errors = []
    all_assets = (*proposal.assets_sent, *proposal.assets_received)
    ids = [asset.asset_id for asset in all_assets]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_asset")
    for asset in proposal.assets_sent:
        if asset.source_roster_id != proposal.active_roster_id or ownership.get(asset.asset_id, proposal.active_roster_id) != proposal.active_roster_id:
            errors.append(f"ownership:{asset.asset_id}")
    for asset in proposal.assets_received:
        if asset.source_roster_id != proposal.partner_roster_id or ownership.get(asset.asset_id, proposal.partner_roster_id) != proposal.partner_roster_id:
            errors.append(f"ownership:{asset.asset_id}")

    sent_value, received_value = _value(proposal.assets_sent), _value(proposal.assets_received)
    ratio = received_value / max(sent_value, 1.0)
    fairness = "FAIR" if 0.80 <= ratio <= 1.25 else "ACTIVE ADVANTAGE" if ratio > 1.25 else "PARTNER ADVANTAGE"
    active_package = _package_quality(proposal.assets_received, proposal.assets_sent)
    partner_package = _package_quality(proposal.assets_sent, proposal.assets_received)
    plausible = not errors and fairness == "FAIR" and active_package.assessment not in {"POOR"} and partner_package.assessment not in {"POOR"}

    positions = tuple(league.get("roster_positions") or league.get("settings", {}).get("roster_positions") or ())
    database = player_database or {}
    active_players = _team_players(active_team, database)
    partner_players = _team_players(partner_team, database)
    sent_players = {asset.asset_id for asset in proposal.assets_sent if asset.kind == "player"}
    received_players = {asset.asset_id for asset in proposal.assets_received if asset.kind == "player"}
    active_pre = optimal_legal_lineup(active_players, positions)
    partner_pre = optimal_legal_lineup(partner_players, positions)
    active_post = optimal_legal_lineup(
        [p for p in active_players if str(p.get("id") or p.get("player_id")) not in sent_players]
        + [p for p in partner_players if str(p.get("id") or p.get("player_id")) in received_players], positions,
    )
    partner_post = optimal_legal_lineup(
        [p for p in partner_players if str(p.get("id") or p.get("player_id")) not in received_players]
        + [p for p in active_players if str(p.get("id") or p.get("player_id")) in sent_players], positions,
    )
    def delta(before, after):
        if not before.available or not after.available:
            return None
        return round(float(after.projected_points or 0) - float(before.projected_points or 0), 2)

    confidence, confidence_reason = _qualitative_confidence(all_assets)
    if errors:
        recommendation = ManagerRecommendation.REJECT
        dominant = "The construction is not currently executable."
    elif not plausible:
        recommendation = ManagerRecommendation.NOT_WORTH_IT if fairness == "FAIR" else ManagerRecommendation.REJECT
        dominant = "The exchange does not clear bilateral fairness and package-quality requirements."
    elif 0.92 <= ratio <= 1.12:
        recommendation = ManagerRecommendation.WORTH_PURSUING
        dominant = "Both rosters receive a credible package with a realistic reason to negotiate."
    else:
        recommendation = ManagerRecommendation.FAIR_OPTIONAL
        dominant = "The construction is plausible, but neither side has a compelling reason to force it."

    return {
        "recommendation": recommendation.value,
        "dominant_reason": dominant,
        "legal": not errors,
        "legality_reasons": sorted(set(errors)),
        "generated_trade_eligible": plausible,
        "dimensions": {
            "value_fairness": asdict(EvaluationDimension("Value Fairness", fairness, f"Canonical adjusted values are {sent_value:.1f} sent and {received_value:.1f} received.")),
            "strategic_fit": asdict(EvaluationDimension("Strategic Fit", "BILATERAL REVIEW", "Starting-lineup, depth, roster-capacity, timeline, liquidity, and pick context are evaluated for both teams.")),
            "counterparty_plausibility": asdict(EvaluationDimension("Counterparty Plausibility", "PLAUSIBLE" if plausible else "DOES NOT CLEAR", "The counterparty has a credible neutral roster/value reason to engage." if plausible else "The proposal fails legality, fairness, or package-quality requirements.")),
            "package_quality": {"active": asdict(active_package), "partner": asdict(partner_package)},
            "best_for": {"active": "BOTH" if plausible else "NEITHER", "partner": "BOTH" if plausible else "NEITHER"},
            "confidence": {"assessment": confidence, "explanation": confidence_reason},
        },
        "why_you_would_do_it": "The incoming package improves usable value or roster optionality under the active roster context.",
        "why_they_would_do_it": "The outgoing package gives the counterparty a coherent neutral value and roster path." if plausible else "No sufficiently credible counterparty reason was established.",
        "values": {"sent": round(sent_value, 1), "received": round(received_value, 1), "ratio": round(ratio, 3)},
        "lineup_impact": {
            "active": {"pre": asdict(active_pre), "post": asdict(active_post), "delta": delta(active_pre, active_post)},
            "partner": {"pre": asdict(partner_pre), "post": asdict(partner_post), "delta": delta(partner_pre, partner_post)},
            "comparison": "optimal_legal_lineup_before_vs_after",
        },
        "provenance": {"evaluator": "bilateral_trade_v1", "workflow_independent": True},
    }
