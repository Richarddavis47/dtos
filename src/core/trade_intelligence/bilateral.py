"""Canonical bilateral trade evaluation shared by every Trade Center workflow."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from src.core.trade_intelligence.lineup import optimal_legal_lineup
from src.core.trade_intelligence.models import TradeAsset, TradeProposal
from src.core.trade_intelligence.market_balance import market_balance, package_market
from src.core.valuation.packages import neutral_trade_value
from src.core.trade_intelligence.evidence_context import (
    TradeEvidenceContext, assess_historical_fit,
)


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
    value = package_market(assets)['total']
    if value is None:
        raise ValueError('Complete Market price unavailable')
    return value


def _package_quality(received: tuple[TradeAsset, ...], outgoing: tuple[TradeAsset, ...]) -> EvaluationDimension:
    received_value = _value(received)
    centerpiece = max((neutral_trade_value(asset) for asset in outgoing), default=0)
    best_incoming = max((neutral_trade_value(asset) for asset in received), default=0)
    useful = sum(1 for asset in received if neutral_trade_value(asset) >= max(20, centerpiece * 0.35))
    roster_spots = max(0, len(received) - len(outgoing))
    if centerpiece and len(received) >= 3 and best_incoming < centerpiece * 0.60 and useful <= 1:
        return EvaluationDimension("Package Quality", "POOR", "Fair on paper, but the package relies on secondary pieces rather than a credible centerpiece.")
    if roster_spots >= 3 and received_value:
        return EvaluationDimension("Package Quality", "QUESTIONABLE", "The receiving roster must have capacity for the additional assets; displaced-player cost matters.")
    if useful >= 2:
        return EvaluationDimension("Package Quality", "USEFUL DEPTH", "Multiple incoming assets carry meaningful roster or lineup utility, so no automatic multi-asset penalty applies.")
    return EvaluationDimension("Package Quality", "COHERENT", "The package has a usable centerpiece and bounded roster-capacity cost.")


def evaluate_package_quality(
    received: tuple[TradeAsset, ...], outgoing: tuple[TradeAsset, ...],
) -> EvaluationDimension:
    """Input-driven package-quality contract shared with temporal consumers."""
    if any(asset.trade_value is None for asset in (*received, *outgoing)):
        return EvaluationDimension("Package Quality", "UNAVAILABLE", "Acquisition-price evidence is missing; package quality cannot be established.")
    return _package_quality(received, outgoing)


def _qualitative_confidence(assets: tuple[TradeAsset, ...]) -> tuple[str, str]:
    if any(
        asset.kind == "pick"
        and not asset.exact_slot
        and str(asset.projected_range or "UNKNOWN").upper() == "UNKNOWN"
        and str(asset.projected_range_confidence or "LOW").upper() == "LOW"
        for asset in assets
    ):
        return "LOW", "At least one future pick has an unresolved range with low confidence; no premium outcome is assumed."
    score = min((asset.confidence_score for asset in assets), default=0)
    if score >= 75:
        return "HIGH", "Current market and asset evidence is strong."
    if score >= 50:
        return "MEDIUM", "Some market, projection, or future-pick uncertainty remains."
    return "LOW", "Material evidence is unavailable or weak; treat the conclusion cautiously."


def _team_players(team: dict[str, Any], assets_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**assets_by_id.get(str(p.get("id") or p.get("player_id")), {}), **p} for p in team.get("players") or ()]


def _required_positions(positions: tuple[str, ...]) -> dict[str, int]:
    required = {position: positions.count(position) for position in {"QB", "RB", "WR", "TE"}}
    if "SUPER_FLEX" in positions:
        required["QB"] += 1
    return required


def _strategic_reasons(
    *,
    incoming: tuple[TradeAsset, ...],
    outgoing: tuple[TradeAsset, ...],
    incoming_value: float,
    outgoing_value: float,
    lineup_delta: float | None,
    team_players: list[dict[str, Any]],
    positions: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if lineup_delta is not None and lineup_delta > 0.25:
        reasons.append(f"Optimal Legal Lineup improves by {lineup_delta:.2f} projected points.")
    if incoming_value >= outgoing_value * 1.05:
        reasons.append(f"Receives {incoming_value - outgoing_value:.0f} more neutral market value.")
    required = _required_positions(positions)
    counts = {
        position: sum(str(player.get("position") or "") == position for player in team_players)
        for position in required
    }
    incoming_positions = {asset.position for asset in incoming if asset.kind == "player"}
    for position in sorted(incoming_positions):
        added = sum(asset.kind == 'player' and asset.position == position for asset in incoming)
        removed = sum(asset.kind == 'player' and asset.position == position for asset in outgoing)
        if position and added > removed and counts.get(position, 0) <= required.get(position, 0):
            reasons.append(f"Adds needed {position} depth at or below the configured starting requirement.")
    incoming_picks = sum(asset.trade_value for asset in incoming if asset.kind == "pick")
    outgoing_picks = sum(asset.trade_value for asset in outgoing if asset.kind == "pick")
    if incoming_picks > outgoing_picks and incoming_picks >= 250:
        reasons.append("Adds meaningful draft-capital liquidity and future optionality.")
    incoming_liquidity = sum(asset.liquidity_score for asset in incoming)
    outgoing_liquidity = sum(asset.liquidity_score for asset in outgoing)
    if incoming_liquidity >= outgoing_liquidity + 25:
        reasons.append("Improves package liquidity and future trade flexibility.")
    return tuple(dict.fromkeys(reasons))


def _elite_qb_downgrade(
    outgoing: tuple[TradeAsset, ...], incoming: tuple[TradeAsset, ...], incoming_value: float,
) -> bool:
    elite = max((asset.trade_value for asset in outgoing if asset.position == "QB"), default=0)
    replacement = max((asset.trade_value for asset in incoming if asset.position == "QB"), default=0)
    return elite >= 650 and replacement < elite * .85 and incoming_value < elite * 1.15


def evaluate_bilateral(
    proposal: TradeProposal,
    *,
    active_team: dict[str, Any],
    partner_team: dict[str, Any],
    league: dict[str, Any],
    player_database: dict[str, dict[str, Any]] | None = None,
    ownership: dict[str, int] | None = None,
    evidence_context: TradeEvidenceContext | None = None,
    horizon_impact: dict[str, Any] | None = None,
    team_windows: dict[str, Any] | None = None,
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

    market = market_balance(proposal.assets_sent, proposal.assets_received)
    if horizon_impact is not None:
        # Prepared canonical evidence is authoritative. Do not execute the legacy
        # roster optimizer, price-based package heuristics or liquidity defaults
        # merely to overwrite their conclusions afterward.
        from src.core.trade_intelligence.strategy_dimensions import reconcile_result
        league_id = str(league.get('league_id') or '')
        rejected_context = evidence_context is not None and (
            not league_id or evidence_context.league_id != league_id
        )
        context = None if rejected_context else evidence_context
        historical = assess_historical_fit(
            context, partner_roster_id=proposal.partner_roster_id,
            active_roster_id=proposal.active_roster_id,
            partner_receives=proposal.assets_sent, active_receives=proposal.assets_received,
        )
        lineup_output = {'comparison': 'optimal_legal_lineup_before_vs_after'}
        for side in ('active', 'partner'):
            evidence = (horizon_impact.get('sides') or {}).get(side) or {}
            weeks = evidence.get('horizons', {}).get('current_week', {}).get('weeks_requested') or []
            weekly_rows = evidence.get('weekly') or {}
            weekly = (weekly_rows.get(weeks[0]) or weekly_rows.get(str(weeks[0]))) if weeks else None
            unavailable = {'available': False, 'projected_points': None, 'entries': [],
                           'reason': 'Compatible canonical projection evidence unavailable'}
            lineup_output[side] = {
                'pre': weekly['pre']['optimal'] if weekly else unavailable,
                'post': weekly['post']['optimal'] if weekly else unavailable,
                'delta': weekly['delta'] if weekly else None,
            }
        result = {
            'legal': not errors, 'legality_reasons': sorted(set(errors)),
            'market_evidence': market,
            'values': {'sent': market['sent']['total'], 'received': market['received']['total'],
                       'ratio': round(market['ratio'], 3) if market['ratio'] is not None else None},
            'lineup_impact': lineup_output, 'multi_horizon_impact': horizon_impact,
            'dimensions': {
                'historical_counterparty_evidence': historical,
                'value_fairness': {'label': 'Market Balance', 'assessment': market['availability'].upper(),
                                  'explanation': 'Canonical acquisition prices only; strategic effects remain separate.'},
            },
            'provenance': {
                'evaluator': 'bilateral_trade_v3', 'workflow_independent': True,
                'historical_context_schema': getattr(context, 'schema_version', None),
                'historical_context_generation': getattr(context, 'generation', None),
                'wrong_league_evidence_rejected': int(rejected_context) + getattr(context, 'wrong_league_evidence_rejected', 0),
                'wrong_league_evidence_consumed': 0,
                'provider_requests': 0, 'raw_history_scans': 0,
                'profile_rebuilds': 0, 'trend_rebuilds': 0,
            },
        }
        result = reconcile_result(result, proposal, horizon_impact, historical, team_windows=team_windows)
        result['dimensions']['package_evidence'] = result['dimensions']['package_quality']
        return result
    if market['availability'] != 'full':
        from src.core.trade_intelligence.package_quality import package_profile
        sides = (horizon_impact or {}).get('sides') or {}
        partial_packages = {
            'active': package_profile(proposal.assets_received, proposal.assets_sent, sides.get('active')),
            'partner': package_profile(proposal.assets_sent, proposal.assets_received, sides.get('partner')),
        }
        result = {
            'recommendation': None, 'recommendation_availability': 'unavailable',
            'dominant_reason': 'Complete Market balance is unavailable; supported lineup impacts remain separate.',
            'legal': not errors, 'legality_reasons': sorted(set(errors)),
            'generated_trade_eligible': False,
            'market_evidence': market,
            'values': {'sent': market['sent']['total'], 'received': market['received']['total'], 'ratio': None},
            'multi_horizon_impact': horizon_impact,
            'dimensions': {
                'package_quality': partial_packages,
                'value_fairness': {'label': 'Value Fairness', 'assessment': market['availability'].upper(),
                                  'explanation': 'Known subtotals are not complete package prices.'},
                'confidence': {'assessment': 'LIMITED', 'explanation': 'Missing price limits Market conclusions, not player quality.'},
            },
            'reason_codes': ['PARTIAL_MARKET_EVIDENCE' if market['availability'] == 'partial' else 'MARKET_EVIDENCE_UNAVAILABLE'],
            'provenance': {'evaluator': 'bilateral_trade_v3', 'provider_requests': 0, 'raw_history_scans': 0},
        }
        if horizon_impact is not None:
            from src.core.trade_intelligence.strategy_dimensions import reconcile_result
            return reconcile_result(result, proposal, horizon_impact, team_windows=team_windows)
        return result
    sent_value, received_value = market['sent']['total'], market['received']['total']
    ratio = received_value / sent_value if sent_value else 1.0 if not received_value else float('inf')
    fairness = "FAIR" if 0.80 <= ratio <= 1.25 else "ACTIVE ADVANTAGE" if ratio > 1.25 else "PARTNER ADVANTAGE"
    active_package = _package_quality(proposal.assets_received, proposal.assets_sent)
    partner_package = _package_quality(proposal.assets_sent, proposal.assets_received)
    package_clear = active_package.assessment != "POOR" and partner_package.assessment != "POOR"

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

    active_delta = delta(active_pre, active_post)
    partner_delta = delta(partner_pre, partner_post)
    # The manual candidate path supplies pinned canonical multi-week evidence.
    # Missing compatible evidence cannot fall back to generic roster projections.
    if horizon_impact is not None:
        sides = horizon_impact.get('sides') or {}
        active_delta = sides.get('active', {}).get('horizons', {}).get('current_week', {}).get('delta')
        partner_delta = sides.get('partner', {}).get('horizons', {}).get('current_week', {}).get('delta')
        from src.core.trade_intelligence.package_quality import package_profile
        package_evidence = {
            'active': package_profile(proposal.assets_received, proposal.assets_sent, sides.get('active')),
            'partner': package_profile(proposal.assets_sent, proposal.assets_received, sides.get('partner')),
        }
        active_package = EvaluationDimension(**{k: package_evidence['active'][k] for k in ('label', 'assessment', 'explanation')})
        partner_package = EvaluationDimension(**{k: package_evidence['partner'][k] for k in ('label', 'assessment', 'explanation')})
        package_clear = active_package.assessment != 'POOR' and partner_package.assessment != 'POOR'
    else:
        package_evidence = None
    active_reasons = _strategic_reasons(
        incoming=proposal.assets_received, outgoing=proposal.assets_sent,
        incoming_value=received_value, outgoing_value=sent_value,
        lineup_delta=active_delta, team_players=active_players, positions=positions,
    )
    partner_reasons = _strategic_reasons(
        incoming=proposal.assets_sent, outgoing=proposal.assets_received,
        incoming_value=sent_value, outgoing_value=received_value,
        lineup_delta=partner_delta, team_players=partner_players, positions=positions,
    )
    superflex = "SUPER_FLEX" in positions
    active_scarcity_veto = superflex and _elite_qb_downgrade(
        proposal.assets_sent, proposal.assets_received, received_value,
    )
    partner_scarcity_veto = superflex and _elite_qb_downgrade(
        proposal.assets_received, proposal.assets_sent, sent_value,
    )
    scarcity_veto = active_scarcity_veto or partner_scarcity_veto
    plausible = bool(
        not errors and fairness == "FAIR" and package_clear
        and active_reasons and partner_reasons and not scarcity_veto
    )
    confidence, confidence_reason = _qualitative_confidence(all_assets)
    historical = assess_historical_fit(
        evidence_context, partner_roster_id=proposal.partner_roster_id,
        active_roster_id=proposal.active_roster_id,
        partner_receives=proposal.assets_sent,
        active_receives=proposal.assets_received,
    )
    if errors:
        recommendation = ManagerRecommendation.REJECT
        dominant = "The construction is not currently executable."
    elif fairness != "FAIR":
        recommendation = ManagerRecommendation.REJECT
        dominant = "Neutral market value is materially uneven before strategic fit is considered."
    elif not package_clear:
        recommendation = ManagerRecommendation.NOT_WORTH_IT
        dominant = "The package composition does not provide a credible centerpiece or usable roster structure."
    elif scarcity_veto:
        recommendation = ManagerRecommendation.REJECT
        dominant = "The elite Superflex quarterback seller does not receive adequate replacement value or compensation."
    elif not active_reasons or not partner_reasons:
        recommendation = ManagerRecommendation.NOT_WORTH_IT
        dominant = "The numbers are close, but both managers do not have a concrete roster or strategic reason to proceed."
    elif 0.92 <= ratio <= 1.12:
        recommendation = ManagerRecommendation.WORTH_PURSUING
        dominant = "Both managers receive a concrete market, lineup, roster, or liquidity benefit worth discussing."
    else:
        recommendation = ManagerRecommendation.FAIR_OPTIONAL
        dominant = "The construction is plausible, but neither side has a compelling reason to force it."

    lineup_output = {
        'active': {'pre': asdict(active_pre), 'post': asdict(active_post), 'delta': active_delta},
        'partner': {'pre': asdict(partner_pre), 'post': asdict(partner_post), 'delta': partner_delta},
        'comparison': 'optimal_legal_lineup_before_vs_after',
    }
    if horizon_impact is not None:
        for side in ('active', 'partner'):
            evidence = (horizon_impact.get('sides') or {}).get(side) or {}
            weeks = evidence.get('horizons', {}).get('current_week', {}).get('weeks_requested') or []
            weekly = evidence.get('weekly', {}).get(weeks[0]) if weeks else None
            unavailable = {'available': False, 'projected_points': None, 'entries': [],
                           'reason': 'Compatible canonical projection evidence unavailable'}
            lineup_output[side] = {
                'pre': weekly['pre']['optimal'] if weekly else unavailable,
                'post': weekly['post']['optimal'] if weekly else unavailable,
                'delta': weekly['delta'] if weekly else None,
            }
    result = {
        "recommendation": recommendation.value,
        "market_evidence": market,
        "dominant_reason": dominant,
        "legal": not errors,
        "legality_reasons": sorted(set(errors)),
        "generated_trade_eligible": plausible,
        "dimensions": {
            "value_fairness": asdict(EvaluationDimension("Value Fairness", fairness, f"Neutral canonical market values are {sent_value:.1f} sent and {received_value:.1f} received; team fit does not rewrite them.")),
            "strategic_fit": {
                "label": "Strategic Fit",
                "assessment": "CLEAR" if active_reasons else "NOT ESTABLISHED",
                "active_reasons": list(active_reasons),
                "partner_reasons": list(partner_reasons),
                "explanation": " ".join(active_reasons) if active_reasons else "No concrete controlled-team lineup, roster, liquidity, or value benefit was established.",
            },
            "counterparty_plausibility": asdict(EvaluationDimension(
                "Counterparty Plausibility", "PLAUSIBLE" if plausible else "DOES NOT CLEAR",
                " ".join(partner_reasons) if partner_reasons and not scarcity_veto else
                "Elite Superflex quarterback replacement cost is not satisfied." if scarcity_veto else
                "No concrete counterparty lineup, roster, liquidity, or value benefit was established.",
            )),
            "historical_counterparty_evidence": historical,
            "package_quality": {"active": asdict(active_package), "partner": asdict(partner_package)},
            "package_evidence": package_evidence,
            "best_for": {
                "active": "CONTENDING" if plausible and active_delta is not None and active_delta > .25 else "RETOOLING" if plausible and any(asset.kind == "pick" for asset in proposal.assets_received) else "BOTH" if plausible else "NEITHER",
                "partner": "CONTENDING" if plausible and partner_delta is not None and partner_delta > .25 else "RETOOLING" if plausible and any(asset.kind == "pick" for asset in proposal.assets_sent) else "BOTH" if plausible else "NEITHER",
            },
            "confidence": {"assessment": confidence, "explanation": confidence_reason},
        },
        "why_you_would_do_it": " ".join(active_reasons) if active_reasons else "No sufficiently concrete controlled-team reason was established.",
        "why_they_would_do_it": " ".join(partner_reasons) if partner_reasons and not scarcity_veto else "No sufficiently credible counterparty reason was established.",
        "perspectives": {
            "for_your_team": "FAVORABLE" if ratio > 1.12 else "REASONABLE" if ratio >= .92 else "UNFAVORABLE",
            "bilateral_reality": "REALISTIC" if plausible else "NOT REALISTIC",
        },
        "values": {"sent": sent_value, "received": received_value, "ratio": round(market['ratio'], 3) if market['ratio'] is not None else None},
        "lineup_impact": lineup_output,
        "multi_horizon_impact": horizon_impact,
        "why_now": (
            "Supported market movement informs timing, but does not alter canonical value."
            if historical["trend_signals"] else
            "No evidence-supported market-timing signal is required; current roster fit remains primary."
        ),
        "provenance": {
            "evaluator": "bilateral_trade_v3", "workflow_independent": True,
            "historical_context_schema": getattr(evidence_context, "schema_version", None),
            "historical_context_generation": getattr(evidence_context, "generation", None),
            "wrong_league_evidence_rejected": getattr(
                evidence_context, "wrong_league_evidence_rejected", 0,
            ),
            "wrong_league_evidence_consumed": getattr(
                evidence_context, "wrong_league_evidence_consumed", 0,
            ),
            "provider_requests": 0, "raw_history_scans": 0,
            "profile_rebuilds": 0, "trend_rebuilds": 0,
        },
    }
    if horizon_impact is not None:
        from src.core.trade_intelligence.strategy_dimensions import reconcile_result
        return reconcile_result(result, proposal, horizon_impact, historical, team_windows=team_windows)
    return result
