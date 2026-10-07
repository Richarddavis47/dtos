"""Application-facing Trade Intelligence view assembly."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from hashlib import sha256
import json
from time import perf_counter

from src.core.intelligence import AssetContext, TradeAsset, TradeEvidenceContext, TradeProposal, apply_positional_ranks, build_asset_pool, build_league_model, build_trade_evidence_context, evaluate_bilateral, generate_proposals
from src.core.valuation.calibration import cached_market_facts
from services.trade_cheaper_repair import (
    REPAIR_EVALUATION_BUDGET, REPAIR_OPTION_LIMIT, cheaper_phase,
    market_cost, no_cheaper_reason, repair_family,
)


class RepairMode(StrEnum):
    """Canonical, mutually exclusive Trade Center repair modes."""

    MAKE_THIS_TRADE_WORK = "MAKE_THIS_TRADE_WORK"
    ALTERNATIVE_CONSTRUCTION = "ALTERNATIVE_CONSTRUCTION"
    ALTERNATIVE_TARGET = "ALTERNATIVE_TARGET"


_REPAIR_MODE_ALIASES = {
    "make this trade work": RepairMode.MAKE_THIS_TRADE_WORK,
    "make_this_trade_work": RepairMode.MAKE_THIS_TRADE_WORK,
    "alternative construction": RepairMode.ALTERNATIVE_CONSTRUCTION,
    "alternative_construction": RepairMode.ALTERNATIVE_CONSTRUCTION,
    "alternative target": RepairMode.ALTERNATIVE_TARGET,
    "alternative_target": RepairMode.ALTERNATIVE_TARGET,
}


class ManagerContextRequired(ValueError):
    """Raised when a league is known but the controlled franchise is not."""


class TradeInputError(ValueError):
    """Expected proposal rejection, distinct from an intelligence failure."""

    def __init__(self, code: str, message: str, assets: tuple[str, ...] = ()):
        super().__init__(message)
        self.code, self.assets = code, assets


def validate_trade_ownership(workspace: dict, payload: dict) -> None:
    active, partner = int(payload.get("active_roster_id") or 0), int(payload.get("partner_roster_id") or 0)
    pools = workspace["pools"]
    if active not in pools or partner not in pools or active == partner:
        raise TradeInputError("legality_rejected", "Choose two distinct franchises in this league.")
    for field in ("assets_sent", "assets_received"):
        values = payload.get(field)
        if not isinstance(values, (list, tuple)) or any(not isinstance(value, str) or not value for value in values):
            raise TradeInputError("invalid_proposal", "Select assets using the current trade workspace.")
    sent, received = tuple(payload["assets_sent"]), tuple(payload["assets_received"])
    if not sent or not received:
        raise TradeInputError("legality_rejected", "Select at least one asset on each side.")
    if len(set((*sent, *received))) != len(sent) + len(received):
        raise TradeInputError("duplicate_asset", "An asset cannot appear twice or on both sides.")
    assets = {a.asset_id: a for pool in pools.values() for a in pool}
    missing = tuple(str(i) for i in (*sent, *received) if i not in assets)
    if missing:
        raise TradeInputError("missing_asset", "Trade needs refreshing: selected assets are no longer available in this league.", missing)
    wrong = tuple(i for ids, owner in ((sent, active), (received, partner)) for i in ids if assets[i].source_roster_id != owner)
    if wrong:
        names = ", ".join(assets[i].label for i in wrong)
        raise TradeInputError("ownership_changed", f"Trade needs refreshing: {names} no longer belongs to the selected sending franchise.", wrong)
    from src.core.intelligence import trade_pick_identity_errors
    invalid_picks = tuple(i for i in (*sent, *received) if trade_pick_identity_errors(assets[i]))
    if invalid_picks:
        raise TradeInputError('pick_identity_invalid', 'The exact pick identity or current owner is inconsistent. Refresh the workspace.', invalid_picks)


def _requested_strategy(workspace, payload):
    """Request-local manager intent; search preferences do not change judgment."""
    from src.core.intelligence import resolve_trade_strategy
    explicit = payload.get('strategy')
    if explicit is not None and resolve_trade_strategy(explicit)['strategy'] is None:
        raise TradeInputError('invalid_strategy', 'Choose WIN NOW, RETOOL or REBUILD.')
    if explicit is not None:
        workspace['requested_strategy'] = explicit


@dataclass(frozen=True)
class ControlledManagerContext:
    league_id: str
    roster_id: int
    manager_id: str | None
    source: str


def resolve_controlled_manager_context(
    data: dict[str, Any], active_roster_id: int | None,
) -> ControlledManagerContext:
    """Resolve an explicit, league-scoped manager without guessing a roster."""
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    by_roster = {int(team.get("roster_id") or 0): team for team in teams}
    if active_roster_id is None:
        raise ManagerContextRequired("Choose the franchise you control before using Trade Center.")
    roster_id = int(active_roster_id)
    if roster_id not in by_roster:
        raise ManagerContextRequired("The selected franchise is not part of this league context.")
    team = by_roster[roster_id]
    return ControlledManagerContext(
        league_id=str((data.get("league") or {}).get("league_id") or data.get("league_id") or ""),
        roster_id=roster_id,
        manager_id=str(team.get("owner_id") or team.get("user_id") or team.get("owner") or "") or None,
        source="explicit_front_office",
    )


def _repair_mode(payload: dict[str, Any], instruction: str) -> RepairMode:
    explicit = payload.get("repair_mode")
    value = str(explicit if explicit is not None else instruction).strip().casefold().replace("-", " ")
    normalized = " ".join(value.split())
    mode = _REPAIR_MODE_ALIASES.get(normalized) or _REPAIR_MODE_ALIASES.get(normalized.replace(" ", "_"))
    if mode is not None:
        return mode
    if explicit is not None:
        raise ValueError(f"Unknown trade repair mode: {explicit}")
    return RepairMode.MAKE_THIS_TRADE_WORK


def build_trade_center(data: dict[str, Any], active_roster_id: int | None = None) -> dict[str, Any]:
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    manager = resolve_controlled_manager_context(data, active_roster_id)
    roster_id = manager.roster_id
    active_team = next(team for team in teams if int(team.get("roster_id") or 0) == roster_id)
    # Navigation is not a second legacy recommendation search. The explicit
    # Recommended workflow owns bounded discovery and canonical evaluation.
    return {"active_team": active_team, "teams": teams, "manager_context": manager,
            "canonical_results": [], "dossiers": (), "value_impacts": {}, "search_state": "not_started"}


def build_trade_workflow_context(
    data: dict[str, Any], active_roster_id: int | None = None,
) -> dict[str, Any]:
    """Return only the league identity needed for an initial workflow render."""
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    manager = resolve_controlled_manager_context(data, active_roster_id)
    roster_id = manager.roster_id
    active_team = next(
        team for team in teams if int(team.get("roster_id") or 0) == roster_id
    )
    return {"active_team": active_team, "teams": teams, "manager_context": manager}


WORKFLOWS = (
    {"id": "create", "label": "Create Trade", "description": "Manually build and evaluate any bilateral proposal."},
    {"id": "trade_for", "label": "Trade For", "description": "Choose another team's asset and find realistic acquisition paths."},
    {"id": "shop", "label": "Shop Asset", "description": "Choose an owned asset and find legitimate markets."},
    {"id": "recommended", "label": "Recommended Trades", "description": "Review the few bilateral opportunities DTOS believes deserve attention."},
)


def _context(decision) -> AssetContext:
    needs = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55)
    return AssetContext(
        decision.profile.league_id, decision.profile.roster_id, decision.profile.league_settings,
        decision.competitive_window.classification.value, decision.profile.strategy, needs,
        {position: room.total_players for position, room in decision.profile.position_rooms.items()},
        decision.profile.market_context.get("position_counts") or {},
    )


def build_trade_workspace(data: dict[str, Any], active_roster_id: int | None = None) -> dict[str, Any]:
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    manager = resolve_controlled_manager_context(data, active_roster_id)
    roster_id = manager.roster_id
    model = build_league_model(data)
    decisions = {identifier: report.decision for identifier, report in model.reports.items()}
    player_ids = {str(player.get("id") or player.get("player_id")) for team in teams for player in team.get("players") or ()}
    market_facts = cached_market_facts(data.get("market_data") or {}, player_ids)
    from src.core.valuation import CalibrationStatus
    market_values = {key: (fact.value, fact.confidence, CalibrationStatus(fact.calibration_status))
                     for key, fact in market_facts.items()}
    pools = {}
    for team in teams:
        identifier = int(team.get("roster_id") or 0)
        pools[identifier] = build_asset_pool(data, team, _context(decisions[identifier]), market_values, market_facts=market_facts)
    pools = apply_positional_ranks(pools)
    windows = {str(identifier): {'classification': decision.competitive_window.classification.value,
                                'confidence': decision.competitive_window.confidence,
                                'generation': (decision.competitive_window.production_profile or {}).get('generation')}
               for identifier, decision in decisions.items() if decision.competitive_window is not None}
    return {"active_roster_id": roster_id, "manager_context": manager, "teams": teams, "pools": pools, "workflows": WORKFLOWS,
            'competitive_windows': windows}


def evaluate_trade_request(
    data: dict[str, Any], payload: dict[str, Any], *, workspace: dict[str, Any] | None = None,
    evidence_context: TradeEvidenceContext | None = None, projection_reader=None,
) -> dict[str, Any]:
    active_id = int(payload.get("active_roster_id") or 0)
    partner_id = int(payload.get("partner_roster_id") or 0)
    workspace = workspace or build_trade_workspace(data, active_id)
    if payload.get('strategy') is not None:
        _requested_strategy({}, payload)
    validate_trade_ownership(workspace, payload)
    locked = set(payload.get('protected_assets') or ()) & set(payload['assets_sent'])
    locked |= set(payload.get('excluded_assets') or ()) & set((*payload['assets_sent'], *payload['assets_received']))
    if locked:
        raise TradeInputError('legality_rejected', 'The proposal violates an exact protected or excluded asset constraint.', tuple(sorted(locked)))
    teams = {int(team.get("roster_id") or 0): team for team in workspace["teams"]}
    if active_id not in teams or partner_id not in teams or active_id == partner_id:
        raise ValueError("A valid bilateral pair of distinct teams is required.")
    assets = {asset.asset_id: asset for pool in workspace["pools"].values() for asset in pool}
    sent_ids = tuple(str(item) for item in payload.get("assets_sent") or ())
    received_ids = tuple(str(item) for item in payload.get("assets_received") or ())
    unknown = [item for item in (*sent_ids, *received_ids) if item not in assets]
    if unknown:
        raise ValueError(f"Unknown trade assets: {', '.join(unknown)}")
    proposal = TradeProposal(active_id, partner_id, tuple(assets[item] for item in sent_ids), tuple(assets[item] for item in received_ids), str(payload.get("package_type") or "Manual"))
    ownership = {asset.asset_id: asset.source_roster_id for asset in assets.values()}
    wrong_sent = [item for item in sent_ids if ownership[item] != active_id]
    wrong_received = [item for item in received_ids if ownership[item] != partner_id]
    if wrong_sent or wrong_received:
        raise ValueError("Trade assets no longer match the selected managers' canonical ownership.")
    if str(payload.get('workflow') or 'create') != 'create':
        _require_acquisition_prices(proposal.assets_sent + proposal.assets_received)
    try:
        horizon_impact = None
        if str(payload.get('workflow') or 'create') in {'create', 'trade_for', 'shop', 'recommended', 'adjust', 'create_alternative'}:
            from src.platform.league_context import current_league_context
            from src.core.projection_intelligence import projection_service
            from src.core.intelligence import evaluate_horizon_impact
            runtime = current_league_context()
            league_id = str((data.get('league') or {}).get('league_id') or '')
            projections = projection_reader or (runtime.projection if runtime is not None and runtime.league_id == league_id else projection_service)
            horizon_impact = evaluate_horizon_impact(data, proposal, projections)
        evaluation = evaluate_bilateral(
            proposal, active_team=teams[active_id], partner_team=teams[partner_id], league=data.get("league") or {},
            player_database=data.get("players") or {}, ownership=ownership,
            horizon_impact=horizon_impact,
            team_windows=workspace.get('competitive_windows'),
            manager_strategies={str(active_id): payload.get('strategy') or workspace.get('requested_strategy') or teams[active_id].get('strategy'),
                                str(partner_id): teams[partner_id].get('strategy')},
            evidence_context=evidence_context or build_trade_evidence_context(
                data, (assets[item] for item in (*sent_ids, *received_ids)),
            ),
        )
    except Exception as exc:
        # Once input/ownership checks passed, an evaluator exception is not a
        # stale proposal and must not expose internal exception text to users.
        raise RuntimeError("Canonical trade evaluation unavailable") from exc
    identity_input = {
        "league_id": str((data.get("league") or {}).get("league_id") or data.get("league_id") or ""),
        "active_roster_id": active_id, "partner_roster_id": partner_id,
        "assets_sent": sorted(sent_ids), "assets_received": sorted(received_ids),
        "market_generation": str((data.get("market_data") or {}).get("generation") or (data.get("market_data") or {}).get("generated_at") or "current"),
        "projection_generation": str((data.get("projection_intelligence") or {}).get("generation") or "current"),
        "historical_generation": evaluation.get("provenance", {}).get("historical_context_generation"),
        "result_digest": sha256(json.dumps(evaluation, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest(),
        "evaluator": "bilateral_trade_v3",
    }
    evaluation["provenance"]["evaluation_id"] = sha256(json.dumps(identity_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    evaluation["provenance"]["inputs"] = identity_input
    from services.trade_explanation import render_trade_explanation
    evaluation['explanation_html'] = render_trade_explanation(evaluation, league_id=identity_input['league_id'])
    evaluation["actions"] = ["EDIT TRADE", "ADJUST OFFER"]
    if not evaluation["generated_trade_eligible"]:
        evaluation["repair_paths"] = ["MAKE THIS TRADE WORK", "ALTERNATIVE CONSTRUCTION", "ALTERNATIVE TARGET"]
    def summary(item: TradeAsset) -> dict[str, Any]:
        player_id = item.asset_id.removeprefix("player:") if item.kind == "player" else None
        return {
            "asset_id": item.asset_id, "label": item.label, "kind": item.kind,
            "position": item.position, "positional_rank": item.positional_rank,
            "market_value": item.trade_value, "market_fact": item.market_fact, "projected_range": item.projected_range,
            "year": item.season, "round": item.round,
            "original_franchise": item.original_roster_id, "current_owner": item.current_owner_id,
            "exact_slot": item.exact_slot,
            "range_confidence": item.projected_range_confidence,
            "headshot_url": (
                f"https://sleepercdn.com/content/nfl/players/{player_id}.jpg"
                if player_id else None
            ),
        }

    partner_name = str(teams[partner_id].get("team_name") or teams[partner_id].get("owner") or "Unassigned Franchise")
    return {
        "workflow": str(payload.get("workflow") or "create"),
        "proposal": {"active_roster_id": active_id, "partner_roster_id": partner_id, "assets_sent": sent_ids, "assets_received": received_ids},
        "proposal_presentation": {
            "partner_team_name": partner_name,
            "send": [summary(assets[item]) for item in sent_ids],
            "receive": [summary(assets[item]) for item in received_ids],
            "best_for": evaluation.get("dimensions", {}).get("best_for", {}).get("active", "UNRESOLVED"),
            "confidence": evaluation.get("dimensions", {}).get("confidence", {}).get("assessment", "UNRESOLVED"),
        },
        "evaluation": evaluation,
    }


def _require_acquisition_prices(assets: tuple[TradeAsset, ...]) -> None:
    missing = tuple(asset.asset_id for asset in assets if asset.trade_value is None)
    if missing:
        raise TradeInputError(
            "market_evidence_unavailable",
            "Market Balance is unavailable because selected assets lack acquisition-price evidence.",
            missing,
        )


def _proposal_payload(proposal: TradeProposal, workflow: str = "adjust") -> dict[str, Any]:
    return {
        "workflow": workflow,
        "active_roster_id": proposal.active_roster_id,
        "partner_roster_id": proposal.partner_roster_id,
        "assets_sent": [asset.asset_id for asset in proposal.assets_sent],
        "assets_received": [asset.asset_id for asset in proposal.assets_received],
        "package_type": proposal.package_type,
    }


def _bounded_adjustment_candidates(
    workspace: dict[str, Any], payload: dict[str, Any], *, allow_target_change: bool = False, search_diagnostics=None,
) -> tuple[TradeProposal, ...]:
    """Build deterministic nearby and generated alternatives from cached pools only."""
    active_id = int(payload.get("active_roster_id") or 0)
    partner_id = int(payload.get("partner_roster_id") or 0)
    pools = workspace["pools"]
    if active_id not in pools or partner_id not in pools:
        raise ValueError("A valid bilateral pair is required for trade assistance.")
    sent_ids = tuple(str(item) for item in payload.get("assets_sent") or ())
    received_ids = tuple(str(item) for item in payload.get("assets_received") or ())
    by_id = {asset.asset_id: asset for pool in pools.values() for asset in pool}
    if any(item not in by_id for item in (*sent_ids, *received_ids)):
        raise ValueError("Trade assistance cannot use unknown assets.")
    protected = {str(item) for item in payload.get("protected_assets") or ()}
    excluded = {str(item) for item in payload.get("excluded_assets") or ()}
    sent = tuple(by_id[item] for item in sent_ids if item not in protected | excluded)
    received = tuple(by_id[item] for item in received_ids)
    _require_acquisition_prices(sent + received)
    allowed_active = tuple(a for a in pools[active_id] if a.asset_id not in protected | excluded
                           and (not payload.get('replacement_position') or a.kind == 'pick'
                                or a.position == payload['replacement_position'])
                           and (not payload.get('replacement_kind') or a.kind == payload['replacement_kind']))
    allowed_ids = {a.asset_id for a in allowed_active}
    sent = tuple(a for a in sent if a.asset_id in allowed_ids)
    allowed_partner = tuple(a for a in pools[partner_id] if a.asset_id not in excluded)
    candidates = []
    cheap_count = 0
    targets = allowed_partner if allow_target_change else tuple(a for a in allowed_partner if a.asset_id in received_ids)
    for target in targets[:12]:
        for phase in range(2):
            diagnostics = {}
            candidates.extend(generate_proposals(active_id, partner_id, allowed_active, allowed_partner,
                required_received_asset_id=target.asset_id, construction_only=True, search_phase=phase, search_diagnostics=diagnostics))
            cheap_count += diagnostics.get('cheap_package_pairs_inspected', 0)
    base_count = len(candidates)
    if sent and received:
        candidates.append(TradeProposal(active_id, partner_id, sent, received, 'Constrained Original'))
    active_options = sorted(
        (asset for asset in allowed_active if asset.trade_value is not None and asset.asset_id not in set(sent_ids)
         and (not payload.get('replacement_position') or asset.position == payload['replacement_position'])
         and (not payload.get('addition_kind') or asset.kind == payload['addition_kind'])
         and (not payload.get('replacement_kind') or asset.kind == payload['replacement_kind'])),
        key=lambda asset: (abs(asset.trade_value - max((item.trade_value for item in received), default=0)), -asset.trade_value, asset.asset_id),
    )[:10]
    partner_options = sorted(
        (asset for asset in pools[partner_id] if asset.trade_value is not None and asset.asset_id not in excluded | set(received_ids)),
        key=lambda asset: (abs(asset.trade_value - max((item.trade_value for item in sent), default=0)), -asset.trade_value, asset.asset_id),
    )[:10]
    if received:
        for asset in active_options:
            candidates.append(TradeProposal(active_id, partner_id, (*sent, asset), received, "Assisted Addition"))
            for index in range(len(sent)):
                if sent[index].asset_id not in protected:
                    candidates.append(TradeProposal(active_id, partner_id, sent[:index] + (asset,) + sent[index + 1:], received, "Assisted Replacement"))
        for asset in partner_options:
            if sent:
                candidates.append(TradeProposal(active_id, partner_id, sent, (*received, asset), "Assisted Return"))
            if allow_target_change:
                for index in range(len(received)):
                    candidates.append(TradeProposal(active_id, partner_id, sent, received[:index] + (asset,) + received[index + 1:], "Alternative Target"))
        if len(sent) > 1:
            candidates.extend(TradeProposal(active_id, partner_id, sent[:index] + sent[index + 1:], received, "Assisted Reduction") for index in range(len(sent)) if sent[index].asset_id not in protected)
        if len(received) > 1:
            candidates.extend(TradeProposal(active_id, partner_id, sent, received[:index] + received[index + 1:], "Assisted Reduction") for index in range(len(received)))
    unique: dict[tuple[tuple[str, ...], tuple[str, ...]], TradeProposal] = {}
    required_targets = set(received_ids)
    for proposal in candidates:
        sent_key = tuple(sorted(asset.asset_id for asset in proposal.assets_sent))
        received_key = tuple(sorted(asset.asset_id for asset in proposal.assets_received))
        if (not sent_key or not received_key or protected.intersection(sent_key)
                or excluded.intersection((*sent_key, *received_key))
                or not set(payload.get('required_outgoing_assets') or ()).issubset(sent_key)
                or (not allow_target_change and not required_targets.issubset(received_key))):
            continue
        unique.setdefault((sent_key, received_key), proposal)
    if search_diagnostics is not None:
        search_diagnostics.update(cheap_package_pairs_inspected=cheap_count + len(candidates) - base_count,
            constructed_candidates=min(len(unique), 160), constraint_filtered=len(candidates) - len(unique),
            unique_package_budget=160, target_asset_ids=sorted(required_targets))
    return tuple(sorted(unique.values(), key=lambda p: (
        abs(sum(a.trade_value for a in p.assets_sent) - sum(a.trade_value for a in p.assets_received)),
        sum(a.trade_value for a in p.assets_sent),
        tuple(a.asset_id for a in p.assets_sent), tuple(a.asset_id for a in p.assets_received))))[:160]


def assist_trade_request(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Return calculated repair/adjustment options, never static action labels."""
    started = perf_counter()
    boundary = _trade_search_boundary(data)
    reader = _search_reader(data, payload, boundary)
    active_id = int(payload.get("active_roster_id") or 0)
    workspace = build_trade_workspace(data, active_id)
    _requested_strategy(workspace, payload)
    validate_trade_ownership(workspace, payload)
    evidence_context = build_trade_evidence_context(
        data, (asset for pool in workspace["pools"].values() for asset in pool),
    )
    original_sent = set(str(item) for item in payload.get("assets_sent") or ())
    original_received = set(str(item) for item in payload.get("assets_received") or ())
    instruction = str(payload.get("instruction") or payload.get("action") or "make this trade work").strip()
    lowered = instruction.casefold()
    requested_mode = _repair_mode(payload, instruction)
    cheaper = 'cheaper' in lowered
    younger_target_change = 'younger' in lowered and payload.get('origin_workflow') not in ('shop', 'trade_for')
    target_preservation_required = cheaper or payload.get('origin_workflow') == 'trade_for' or (requested_mode is not RepairMode.ALTERNATIVE_TARGET and not younger_target_change)
    enriched = dict(payload)
    protected = {str(item) for item in payload.get("protected_assets") or ()}
    excluded = {str(item) for item in payload.get("excluded_assets") or ()}
    active_assets = workspace["pools"].get(active_id, ())
    all_assets = tuple(asset for pool in workspace["pools"].values() for asset in pool)
    by_id = {asset.asset_id: asset for asset in all_assets}
    exact_asset = payload.get('constraint_asset_id')
    if exact_asset:
        if exact_asset not in {a.asset_id for a in active_assets}:
            raise ValueError('Select an exact owned asset for this adjustment constraint.')
        if ('this pick' in lowered and by_id[exact_asset].kind != 'pick') or ('this player' in lowered and by_id[exact_asset].kind != 'player'):
            raise ValueError('The selected exact asset does not match the requested player/pick constraint.')
        if any(prefix in lowered for prefix in ('keep', 'protect', 'do not trade', "don't trade")):
            protected.add(exact_asset)
        elif any(prefix in lowered for prefix in ('replace', 'exclude')):
            excluded.add(exact_asset)
    no_picks = not exact_asset and any(text in lowered for text in ('do not trade picks', "don't trade picks", 'no outgoing picks'))
    if no_picks:
        protected.update(a.asset_id for a in active_assets if a.kind == 'pick')
    for asset in active_assets:
        label = asset.label.casefold()
        if any(f'{prefix}{label}' in lowered for prefix in ("don't trade ", "do not trade ", "keep ", "protect ")):
            protected.add(asset.asset_id)
    for asset in all_assets:
        label = asset.label.casefold()
        if any(f'{prefix}{label}' in lowered for prefix in ("replace ", "exclude ", "not this ")):
            excluded.add(asset.asset_id)
    enriched["protected_assets"] = sorted(protected)
    enriched["excluded_assets"] = sorted(excluded)
    unresolved_reference = (
        any(prefix in lowered for prefix in ("don't trade", "do not trade", "keep ", "protect ")) and not protected and not no_picks
    ) or (any(prefix in lowered for prefix in ("replace ", "exclude ", "not this ")) and not excluded)
    if unresolved_reference:
        return {
            "instruction": instruction,
            "requested_mode": requested_mode.value,
            "returned_modes": [],
            "target_preservation_required": target_preservation_required,
            "count": 0,
            "results": [],
            "quiet_state": "Choose or name the specific player or pick so DTOS can apply that constraint safely.",
            "calculated": True,
            "provider_requests": 0,
            "asset_market_constructions": 0,
            "constraints": {"protected_assets": sorted(protected), "excluded_assets": sorted(excluded)},
            "interpretation_error": "specific_asset_required",
            "target_asset_ids": sorted(original_received),
            "target_preserved": None,
            "search_completed": False,
        }
    required_outgoing = set()
    if payload.get('origin_workflow') == 'shop':
        target = str(payload.get('origin_asset_id') or '')
        if target not in original_sent:
            raise ValueError('The original shopped asset must identify an outgoing asset in this proposal.')
        required_outgoing.add(target)
    enriched['required_outgoing_assets'] = sorted(required_outgoing)
    outgoing_pick_required = 'add outgoing pick' in lowered
    if (protected & excluded or (no_picks and outgoing_pick_required)
            or required_outgoing & (protected | excluded)
            or (target_preservation_required and original_received & excluded)):
        blocking_ids = sorted((protected & excluded) | (required_outgoing & (protected | excluded))
                              | (original_received & excluded)
                              | (protected if no_picks and outgoing_pick_required else set()))
        blocking_names = ', '.join(f'{by_id[item].label if item in by_id else item} ({item})' for item in blocking_ids)
        return {'instruction': instruction, 'requested_mode': requested_mode.value, 'returned_modes': [],
                'count': 0, 'results': [], 'state': 'CONSTRAINT_CONFLICT',
                'quiet_state': 'The constraint conflicts with the preserved trade objective. Change the objective explicitly.',
                'search_completed': False, 'target_preserved': None,
                'constraints': {'protected_assets': sorted(protected), 'excluded_assets': sorted(excluded)},
                'blocking_asset_ids': blocking_ids,
                'conflict_explanation': f'Your exact lock on {blocking_names} conflicts with the required trade objective. No package was evaluated for this conflicting request.',
                'smallest_optional_relaxation': f'Remove the conflicting exact lock on {blocking_names}, or explicitly choose a different trade objective.'}
    original_sent_assets = tuple(by_id[item] for item in original_sent if item in by_id)
    original_received_assets = tuple(by_id[item] for item in original_received if item in by_id)
    requested_position = next((position for position in ("WR", "RB", "QB", "TE") if f"{position.casefold()}s instead" in lowered or f"{position.casefold()} instead" in lowered or f"use {position.casefold()}" in lowered), None)
    requested_kind = "pick" if "pick" in lowered and "instead" in lowered else None
    add_pick = "add a pick" in lowered or 'add pick' in lowered or outgoing_pick_required
    another_player = "another player back" in lowered or "get player back" in lowered
    expand = "expand" in lowered or "bigger deal" in lowered
    younger = "younger" in lowered
    win_now = "win-now" in lowered or "win now" in lowered
    enriched['replacement_position'] = requested_position
    enriched['replacement_kind'] = requested_kind
    enriched['addition_kind'] = 'pick' if add_pick else None
    if cheaper:
        # Cost repair keeps the current negotiation objective even if another
        # instruction also asks about target alternatives.
        target_preservation_required = True
        missing_prices = [a.asset_id for a in (*original_sent_assets, *original_received_assets)
                          if market_cost((a,)) is None]
        if missing_prices:
            return {'instruction': instruction, 'requested_mode': requested_mode.value,
                'returned_modes': [], 'count': 0, 'results': [], 'near_misses': [],
                'preview_only': True, 'original_proposal': {k: payload[k] for k in
                    ('active_roster_id', 'partner_roster_id', 'assets_sent', 'assets_received')},
                'state': 'MISSING_REQUIRED_EVIDENCE', 'result_state': 'MISSING REQUIRED EVIDENCE',
                'quiet_state': 'A cheaper comparison is unavailable: required canonical Market prices are missing for '
                    + ', '.join(f'{by_id[i].label} ({i})' for i in missing_prices) + '.',
                'constraints': {'protected_assets': sorted(protected), 'excluded_assets': sorted(excluded)},
                'target_preservation_required': True, 'target_asset_ids': sorted(original_received),
                'target_preserved': None, 'search_completed': False, 'calculated': True,
                'provider_requests': 0, 'asset_market_constructions': 0,
                'search_evidence': {'full_evaluations': 0, 'evaluated': 0,
                    'evaluation_budget': REPAIR_EVALUATION_BUDGET, 'budget_reached': False,
                    'missing_asset_ids': missing_prices, 'repair_stop_reason': 'MISSING_CURRENT_MARKET_PRICE'}}
    original_started = perf_counter()
    assess_original = win_now or requested_mode is RepairMode.ALTERNATIVE_TARGET
    original_result = evaluate_trade_request(data, dict(payload, workflow='adjust', protected_assets=[], excluded_assets=[]), workspace=workspace,
                                            evidence_context=evidence_context, projection_reader=reader) if assess_original else None
    evaluation_count = 1 if assess_original else 0
    evaluation_seconds = perf_counter() - original_started if assess_original else 0.0
    from services.trade_search_policy import SearchFunnel, result_state
    from collections import Counter
    funnel = SearchFunnel(REPAIR_EVALUATION_BUDGET, [int(payload['partner_roster_id'])], workspace['pools'])
    construction_seconds = 0.0
    proposals = []
    repair_prunes, missing_candidates = Counter(), set()
    cheaper_count, credible_families = 0, set()
    repair_stop_reason = 'CONSTRUCTIONS_EXHAUSTED'
    candidates = []

    def proposal_stream():
        nonlocal construction_seconds, cheaper_count, repair_stop_reason
        seen = set()
        for phase in (range(3) if cheaper else range(1)):
            stage = perf_counter()
            diagnostics = {}
            if cheaper:
                batch, diagnostics = cheaper_phase(workspace, enriched, phase, seen)
                repair_prunes.update(diagnostics['prune_reason_counts'])
                cheaper_count += diagnostics['cheaper_by_price_candidates']
                missing_candidates.update(diagnostics['missing_asset_ids'])
            else:
                batch = _bounded_adjustment_candidates(workspace, enriched,
                    allow_target_change=not target_preservation_required, search_diagnostics=diagnostics)
            construction_seconds += perf_counter() - stage
            proposals.extend(batch)
            funnel.construction(int(payload['partner_roster_id']), batch, diagnostics)
            for proposal in batch:
                if cheaper and len(credible_families) >= REPAIR_OPTION_LIMIT:
                    repair_stop_reason = 'SUFFICIENT_USEFUL_ALTERNATIVES'
                    return
                if cheaper and evaluation_count >= funnel.budget:
                    repair_stop_reason = 'EVALUATION_BUDGET_EXHAUSTED'
                    return
                yield proposal
            if cheaper and len(credible_families) >= REPAIR_OPTION_LIMIT:
                repair_stop_reason = 'SUFFICIENT_USEFUL_ALTERNATIVES'
                return

    def prune(reason):
        funnel.counts['constructions_pruned'] += 1
        if cheaper:
            repair_prunes[reason] += 1

    for proposal in proposal_stream():
        # Instruction predicates precede expensive assessment; canonical quality
        # is never patched to satisfy a preference.
        if requested_position and not any(a.position == requested_position for a in proposal.assets_sent):
            prune('REQUESTED_OUTGOING_POSITION_NOT_MET')
            continue
        if requested_kind and not any(a.kind == requested_kind for a in proposal.assets_sent):
            prune('REQUESTED_OUTGOING_KIND_NOT_MET')
            continue
        sent_set = {a.asset_id for a in proposal.assets_sent}
        received_set = {a.asset_id for a in proposal.assets_received}
        if sent_set == original_sent and received_set == original_received:
            prune('UNCHANGED_CURRENT_PROPOSAL')
            continue
        if cheaper:
            invalid_objective = (required_outgoing - sent_set) or (original_received - received_set)
            if invalid_objective:
                prune('REQUIRED_SHOP_ANCHOR_MISSING' if required_outgoing - sent_set else 'REQUIRED_INCOMING_TARGET_MISSING')
                continue
            if protected & sent_set or excluded & (sent_set | received_set):
                prune('EXACT_LOCK_CONFLICT')
                continue
            cost = market_cost(proposal.assets_sent)
            if cost is None or cost >= market_cost(original_sent_assets):
                prune('MISSING_MARKET_PRICE' if cost is None else 'EQUAL_OR_HIGHER_OUTGOING_COST')
                continue
        if add_pick:
            old_picks = {a.asset_id for a in (*original_sent_assets, *original_received_assets) if a.kind == 'pick'}
            new_picks = {a.asset_id for a in (proposal.assets_sent if outgoing_pick_required else
                                             (*proposal.assets_sent, *proposal.assets_received)) if a.kind == 'pick'}
            if not new_picks - old_picks:
                prune('NO_ADDITIONAL_PICK')
                continue
        if another_player and not {a.asset_id for a in proposal.assets_received if a.kind == 'player'} - original_received:
            prune('NO_ADDITIONAL_RETURN_PLAYER')
            continue
        if expand and len(proposal.assets_sent) + len(proposal.assets_received) <= len(original_sent) + len(original_received):
            prune('EXPANDED_PACKAGE_REQUIRED')
            continue
        if younger:
            old_players = [a for a in original_received_assets if a.kind == 'player']
            new_players = [a for a in proposal.assets_received if a.kind == 'player']
            if (not old_players or not new_players or any(a.age is None for a in (*old_players, *new_players))
                    or sum(a.age for a in new_players) / len(new_players) >= sum(a.age for a in old_players) / len(old_players)):
                prune('YOUNGER_RETURN_NOT_SUPPORTED')
                continue
        stage = perf_counter()
        candidate_payload = _proposal_payload(proposal)
        if cheaper:
            candidate_payload.update(strategy=payload.get('strategy'),
                protected_assets=sorted(protected), excluded_assets=sorted(excluded))
        try:
            result = evaluate_trade_request(data, candidate_payload, workspace=workspace,
                evidence_context=evidence_context, projection_reader=reader)
        except TradeInputError as exc:
            if not cheaper:
                raise
            # Input gates are hard reasons, never an accepted cheaper preview.
            evaluation_seconds += perf_counter() - stage
            evaluation_count += 1
            funnel.counts['evaluated'] += 1
            field = 'missing_evidence' if exc.code == 'market_evidence_unavailable' else 'hard_invalid'
            funnel.counts[field] += 1
            funnel.reasons[exc.code] += 1
            continue
        evaluation_seconds += perf_counter() - stage
        evaluation_count += 1
        if not _trade_for_eligible(result['evaluation']):
            funnel.assessed(result)
            continue
        sent = set(result["proposal"]["assets_sent"])
        received = set(result["proposal"]["assets_received"])
        sent_assets = tuple(by_id[item] for item in sent)
        received_assets = tuple(by_id[item] for item in received)
        if requested_kind and not any(asset.kind == requested_kind for asset in sent_assets):
            funnel.assessed(result, filtered=True, filter_reason='REQUESTED_OUTGOING_KIND_NOT_MET')
            continue
        if requested_position and not any(asset.position == requested_position for asset in sent_assets):
            funnel.assessed(result, filtered=True, filter_reason='REQUESTED_OUTGOING_POSITION_NOT_MET')
            continue
        if add_pick and sum(asset.kind == "pick" for asset in (*sent_assets, *received_assets)) <= sum(asset.kind == "pick" for asset in (*original_sent_assets, *original_received_assets)):
            funnel.assessed(result, filtered=True, filter_reason='NO_ADDITIONAL_PICK')
            continue
        if another_player and sum(asset.kind == "player" for asset in received_assets) <= sum(asset.kind == "player" for asset in original_received_assets):
            funnel.assessed(result, filtered=True, filter_reason='NO_ADDITIONAL_RETURN_PLAYER')
            continue
        if expand and len(sent_assets) + len(received_assets) <= len(original_sent_assets) + len(original_received_assets):
            funnel.assessed(result, filtered=True, filter_reason='EXPANDED_PACKAGE_REQUIRED')
            continue
        if cheaper and sum(asset.trade_value for asset in sent_assets) >= sum(asset.trade_value for asset in original_sent_assets):
            funnel.assessed(result, filtered=True, filter_reason='LOWER_MARKET_COST_REQUIRED')
            continue
        if expand:
            packages = (result['evaluation'].get('dimensions') or {}).get('package_quality') or {}
            new_incoming = {a.asset_id.removeprefix('player:') for a in received_assets if a.kind == 'player' and a.asset_id not in original_received}
            new_outgoing = {a.asset_id.removeprefix('player:') for a in sent_assets if a.kind == 'player' and a.asset_id not in original_sent}
            if (not new_incoming and not new_outgoing
                    or not new_incoming.issubset((packages.get('active') or {}).get('incoming_lineup_contributors') or [])
                    or not new_outgoing.issubset((packages.get('partner') or {}).get('incoming_lineup_contributors') or [])):
                funnel.assessed(result, filtered=True, filter_reason='ADDED_PLAYER_HAS_NO_SUPPORTED_LINEUP_CONTRIBUTION')
                continue
        if win_now:
            def near(result):
                return (((result['evaluation'].get('dimensions') or {}).get('strategic_fit') or {}).get('active') or {}).get('horizons') or {}
            current, original = near(result), near(original_result)
            comparable = [(current.get(h) or {}, original.get(h) or {}) for h in ('current_week', 'next_n')]
            if (any(a.get('availability') != 'complete' or b.get('availability') != 'complete'
                    or a.get('delta') is None or b.get('delta') is None for a, b in comparable)
                    or not any(a['delta'] > b['delta'] for a, b in comparable)
                    or any(a['delta'] < b['delta'] for a, b in comparable)):
                funnel.assessed(result, filtered=True, filter_reason='WIN_NOW_NO_SUPPORTED_NEAR_TERM_IMPROVEMENT')
                continue
            longer = [(current.get(h) or {}, original.get(h) or {}) for h in ('rest_of_regular_season', 'playoff_window')]
            if any(a.get('availability') == b.get('availability') == 'complete'
                   and a.get('delta') is not None and b.get('delta') is not None
                   and a['delta'] < b['delta'] for a, b in longer):
                funnel.assessed(result, filtered=True, filter_reason='WIN_NOW_SUPPORTED_LATER_HORIZON_REGRESSION')
                continue
            def depth(row):
                return (((row['evaluation'].get('dimensions') or {}).get('strategic_fit') or {}).get('active') or {}).get('reserve_slot_changes') or {}
            prior_depth, revised_depth = depth(original_result), depth(result)
            if any(revised_depth[w] < prior_depth[w] for w in revised_depth.keys() & prior_depth.keys()):
                funnel.assessed(result, filtered=True, filter_reason='WIN_NOW_RESERVE_COVERAGE_REGRESSION')
                continue
            result['adjustment_evidence'] = {'concept': 'supported_near_term_gain_without_comparable_horizon_or_depth_regression',
                'unavailable_horizons': [name for name in ('rest_of_regular_season', 'playoff_window')
                                        if current.get(name, {}).get('availability') != 'complete'
                                        or original.get(name, {}).get('availability') != 'complete']}
        distance = len(sent ^ original_sent) + len(received ^ original_received)
        target_changed = not original_received.issubset(received)
        if target_changed:
            old_roles = {(a.kind, a.position if a.kind == 'player' else (a.season, a.round)) for a in original_received_assets}
            new_roles = {(a.kind, a.position if a.kind == 'player' else (a.season, a.round)) for a in received_assets}
            if not old_roles.issubset(new_roles):
                funnel.assessed(result, filtered=True, filter_reason='TARGET_ROLE_OR_POSITION_CHANGED')
                continue
            result['objective_evidence'] = {'scope': 'same requested asset role/position or pick year/round',
                                           'target_changed': True, 'quality': 'shared evaluator, not role matching'}
        funnel.assessed(result)
        if cheaper:
            before = market_cost(original_sent_assets)
            after = market_cost(sent_assets)
            result['adjustment_evidence'] = {'concept': 'strictly_lower_canonical_outgoing_market_cost',
                'current_outgoing_cost': before, 'alternative_outgoing_cost': after,
                'market_cost_reduction': before - after, 'strategy_changes_prices': False}
            credible_families.add(repair_family(result['proposal'], by_id))
        candidates.append((distance, target_changed, abs(1 - result["evaluation"]["values"]["ratio"]), result))
    if cheaper:
        from services.trade_search_policy import rank_key
        candidates.sort(key=lambda row: (row[0], market_cost(tuple(by_id[i] for i in row[3]['proposal']['assets_sent'])), rank_key(row[3])))
        distinct = {}
        for row in candidates:
            distinct.setdefault(repair_family(row[3]['proposal'], by_id), row)
        candidates = list(distinct.values())
    else:
        candidates.sort(key=lambda row: (row[0], row[2], row[3]["evaluation"]["provenance"]["evaluation_id"]))
    target_preserving = [row for row in candidates if not row[1]]
    closest_rows = candidates if younger_target_change else target_preserving
    closest = closest_rows[0][3] if closest_rows else None
    def construction_signature(ids):
        return sorted((a.kind, a.asset_id if a.kind == 'player' else
                       str((a.season, a.round, a.projected_range, a.exact_slot))) for a in (by_id[i] for i in ids))
    original_signature = (construction_signature(original_sent), construction_signature(original_received))
    materially_different = next((row[3] for row in target_preserving if row[0] >= 2 and
        (construction_signature(row[3]['proposal']['assets_sent']), construction_signature(row[3]['proposal']['assets_received'])) != original_signature), None)
    original_credible = bool(original_result and _trade_for_eligible(original_result['evaluation'])
                             and not original_sent & (protected | excluded) and not original_received & excluded)
    alternative_target = next((row[3] for row in candidates if row[1]), None) if not target_preserving and not original_credible else None
    options: list[dict[str, Any]] = []
    if requested_mode is RepairMode.MAKE_THIS_TRADE_WORK and closest:
        closest["repair_type"] = "MAKE THIS TRADE WORK"
        for _, _, _, row in closest_rows[:3]:
            row['repair_type'] = 'MAKE THIS TRADE WORK'
            options.append(row)
    if requested_mode is RepairMode.ALTERNATIVE_CONSTRUCTION and materially_different:
        materially_different["repair_type"] = "ALTERNATIVE CONSTRUCTION"
        options.append(materially_different)
    if requested_mode is RepairMode.ALTERNATIVE_TARGET and alternative_target:
        alternative_target["repair_type"] = "ALTERNATIVE TARGET"
        options.append(alternative_target)
    target_preserved = (
        all(original_received.issubset(row["proposal"]["assets_received"]) for row in options)
        if options else None
    )
    no_path = {
        RepairMode.MAKE_THIS_TRADE_WORK: "No realistic target-preserving repair clears the current ownership, market, package-quality, and bilateral gates.",
        RepairMode.ALTERNATIVE_CONSTRUCTION: "No materially different target-preserving construction clears the current quality gates.",
        RepairMode.ALTERNATIVE_TARGET: "No realistic alternative target clears the current quality gates.",
    }[requested_mode]
    if requested_mode is RepairMode.ALTERNATIVE_TARGET and (original_credible or target_preserving):
        no_path = 'A credible original-target construction exists; an alternative target is not needed for repair.'
    repair_diagnostics = {}
    if cheaper:
        repair_diagnostics = {'repair_objective': 'MAKE_IT_CHEAPER',
            'current_outgoing_market_cost': market_cost(original_sent_assets),
            'cheaper_by_price_candidates': cheaper_count, 'prune_reason_counts': dict(repair_prunes),
            'lock_conflict': repair_prunes['EXACT_LOCK_CONFLICT'],
            'missing_market_price_before_evaluation': repair_prunes['MISSING_MARKET_PRICE'],
            'hard_invalid_before_evaluation': sum(repair_prunes[k] for k in
                ('ASSET_NOT_OWNED', 'INVALID_PICK_IDENTITY', 'DUPLICATE_ASSET', 'EMPTY_OUTGOING_PACKAGE')),
            'missing_asset_ids': sorted(missing_candidates), 'credible_cheaper': funnel.counts['eligible'],
            'repair_stop_reason': repair_stop_reason,
            'unevaluated_constructions': max(0, funnel.counts['constructions_generated']
                - funnel.counts['constructions_pruned'] - funnel.counts['evaluated']),
            'additional_current_offer_evaluations': int(assess_original)}
        repair_diagnostics['budget_reached'] = evaluation_count >= funnel.budget
        no_path = no_cheaper_reason(funnel, repair_diagnostics)
        if missing_candidates:
            no_path += ' Missing prices: ' + ', '.join(f'{by_id[i].label} ({i})' for i in sorted(missing_candidates)) + '.'
    if _trade_search_boundary(data) != boundary:
        raise TradeInputError('workspace_context_changed', 'Canonical evidence changed during adjustment. Refresh and try again.')
    return {
        "instruction": instruction,
        "requested_mode": requested_mode.value,
        "returned_modes": [requested_mode.value for _ in options],
        "target_preservation_required": target_preservation_required,
        "count": len(options),
        "results": options,
        "preview_only": True, "original_proposal": {k: payload[k] for k in ('active_roster_id', 'partner_roster_id', 'assets_sent', 'assets_received')},
        "near_misses": funnel.near(), "result_state": result_state(funnel, options),
        "quiet_state": None if options else no_path,
        "search_completed": True,
        "next_valid_actions": (
            ["ALTERNATIVE_CONSTRUCTION", "ALTERNATIVE_TARGET", "RELAX_CONSTRAINTS"]
            if target_preservation_required and not options else []
        ),
        "calculated": True,
        "provider_requests": 0,
        "asset_market_constructions": 0,
        "constraints": {"protected_assets": sorted(protected), "excluded_assets": sorted(excluded)},
        "target_asset_ids": sorted(original_received),
        "target_preserved": target_preserved,
        'state': 'ADJUSTMENT_AVAILABLE' if options else 'NO_CREDIBLE_ADJUSTMENT',
        'search_evidence': {**funnel.result(len(options)), 'stages': funnel.stages, 'constructed': len(proposals), 'full_evaluations': evaluation_count,
            **repair_diagnostics,
            'projection_weeks_read': len(reader.weeks), 'provider_requests': 0, 'durable_writes': 0,
            'reuse': reader.lineup_memo.status(),
            'timings_seconds': {'construction': construction_seconds, 'shared_evaluation': evaluation_seconds,
                               'total': perf_counter() - started}},
    }


def create_trade_alternatives(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Return up to three distinct, editable approaches to the same negotiation goal."""
    boundary = _trade_search_boundary(data)
    reader = _SearchProjectionReader(_trade_projection_service(data))
    active_id = int(payload.get("active_roster_id") or 0)
    workspace = build_trade_workspace(data, active_id)
    _requested_strategy(workspace, payload)
    evidence_context = build_trade_evidence_context(
        data, (asset for pool in workspace["pools"].values() for asset in pool),
    )
    by_id = {asset.asset_id: asset for pool in workspace["pools"].values() for asset in pool}
    sent_ids = tuple(str(item) for item in payload.get("assets_sent") or ())
    received_ids = tuple(str(item) for item in payload.get("assets_received") or ())
    if not sent_ids or not received_ids or any(item not in by_id for item in (*sent_ids, *received_ids)):
        raise ValueError("Create Trade alternatives require one valid asset on each side.")
    validate_trade_ownership(workspace, payload)
    _require_acquisition_prices(tuple(by_id[item] for item in (*sent_ids, *received_ids)))
    key_asset_id = str(payload.get("protected_asset_id") or max((by_id[item] for item in sent_ids), key=lambda asset: (asset.trade_value, asset.asset_id)).asset_id)
    target_id = max((by_id[item] for item in received_ids), key=lambda asset: (asset.trade_value, asset.asset_id)).asset_id
    original = (frozenset(sent_ids), frozenset(received_ids))
    assessed_packages = {}
    from services.trade_search_policy import SearchFunnel, result_state
    funnel = SearchFunnel(160, [int(payload['partner_roster_id'])], workspace['pools'])
    if payload.get('origin_workflow') == 'shop':
        shop_asset = payload.get('origin_asset_id')
        if shop_asset not in sent_ids:
            raise ValueError('Alternative must preserve the exact original Shop asset.')
        payload = dict(payload, required_outgoing_assets=[shop_asset])

    def evaluated(candidate_payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        diagnostics = {}
        proposals = _bounded_adjustment_candidates(workspace, candidate_payload, search_diagnostics=diagnostics)
        funnel.construction(int(payload['partner_roster_id']), proposals, diagnostics)
        for proposal in proposals:
            from copy import deepcopy
            key = (proposal.active_roster_id, proposal.partner_roster_id,
                   tuple(sorted(a.asset_id for a in proposal.assets_sent)),
                   tuple(sorted(a.asset_id for a in proposal.assets_received)))
            if key not in assessed_packages:
                if len(assessed_packages) >= funnel.budget:
                    continue
                assessed_packages[key] = evaluate_trade_request(
                    data, _proposal_payload(proposal, "create_alternative"),
                    workspace=workspace, evidence_context=evidence_context, projection_reader=reader,
                )
                funnel.assessed(assessed_packages[key])
            result = deepcopy(assessed_packages[key])
            if _trade_for_eligible(result['evaluation']):
                rows.append(result)
        rows.sort(key=lambda row: (abs(1 - row["evaluation"]["values"]["ratio"]), row["evaluation"]["provenance"]["evaluation_id"]))
        return rows

    all_rows = evaluated(payload)
    protected_payload = {**payload, "protected_assets": sorted({*payload.get("protected_assets", ()), key_asset_id})}
    protected_rows = evaluated(protected_payload)
    chosen: list[dict[str, Any]] = []
    seen: set[tuple[frozenset[str], frozenset[str]]] = set()

    def choose(rows: list[dict[str, Any]], label: str, predicate) -> None:
        for row in rows:
            sent = frozenset(row["proposal"]["assets_sent"])
            received = frozenset(row["proposal"]["assets_received"])
            identity = (sent, received)
            if identity == original or identity in seen or not predicate(sent, received):
                continue
            row["alternative_type"] = label
            row["protected_asset_id"] = key_asset_id
            row["target_asset_id"] = target_id
            chosen.append(row)
            seen.add(identity)
            return

    choose(protected_rows, f"KEEP {by_id[key_asset_id].label.upper()}", lambda sent, received: key_asset_id not in sent and target_id in received)
    choose(all_rows, "SAME TARGET, DIFFERENT PACKAGE", lambda sent, received: target_id in received and len(sent ^ original[0]) + len(received ^ original[1]) >= 2)
    choose(all_rows, "EXPAND THE DEAL", lambda sent, received: len(sent) + len(received) > len(sent_ids) + len(received_ids))
    if _trade_search_boundary(data) != boundary:
        raise TradeInputError('workspace_context_changed', 'Canonical evidence changed during alternative construction. Refresh and try again.')
    return {
        "count": len(chosen[:3]), "results": chosen[:3], "protected_asset_id": key_asset_id,
        "preview_only": True, "original_proposal": {k: payload[k] for k in ('active_roster_id', 'partner_roster_id', 'assets_sent', 'assets_received')},
        "near_misses": funnel.near(), "result_state": result_state(funnel, chosen[:3]),
        "search_evidence": {**funnel.result(len(chosen[:3])), 'full_evaluations': len(assessed_packages)},
        "target_asset_id": target_id, "calculated": True, "provider_requests": 0,
        "asset_market_constructions": 0,
        "quiet_state": None if chosen else "No credible alternative within the bounded search. Review the evaluated packages and their blockers.",
    }


def _distinct_trade_for_offers(rows, by_id):
    """Keep distinct player theses, not nominal substitutions of equivalent picks.

    Identity remains intact in each offer. This groups presentation choices only;
    it does not rewrite pick prices, ranges, ownership or evaluator conclusions.
    """
    def signature(ids):
        parts = []
        for asset_id in ids:
            asset = by_id[asset_id]
            parts.append(('player', asset_id) if asset.kind == 'player' else
                         ('pick', str(asset.season), str(asset.round), str(asset.projected_range), str(asset.exact_slot)))
        return tuple(sorted(parts))
    seen, distinct = set(), []
    for row in rows:
        proposal = row['proposal']
        key = (signature(proposal['assets_sent']), signature(proposal['assets_received']))
        if key not in seen:
            seen.add(key)
            distinct.append(row)
    return distinct


def _trade_for_eligible(evaluation: dict[str, Any]) -> bool:
    """Target acquisition may be optional; never reinterpret the shared judgment."""
    if evaluation.get('generated_trade_eligible'):
        return True
    if evaluation.get('recommendation') != 'FAIR / OPTIONAL':
        return False
    dimensions = evaluation.get('dimensions') or {}
    return bool(
        evaluation.get('legal')
        and (evaluation.get('legality') or {}).get('execution_status') == 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER'
        and (dimensions.get('counterparty_plausibility') or {}).get('assessment') in ('STRONG', 'PLAUSIBLE')
        and (dimensions.get('confidence') or {}).get('assessment') in ('MEDIUM', 'HIGH')
    )


def _trade_projection_service(data):
    from src.platform.league_context import current_league_context
    from src.core.projection_intelligence import projection_service
    runtime = current_league_context()
    league_id = str((data.get('league') or {}).get('league_id') or '')
    if runtime is not None and runtime.league_id != league_id:
        raise TradeInputError('workspace_context_changed', 'Trade search league context changed. Refresh and try again.')
    return runtime.projection if runtime is not None else projection_service


class _SearchProjectionReader:
    """Request-local immutable-generation reads; no cross-search cache/storage."""
    def __init__(self, service, *, reuse_scope=None):
        from src.core.intelligence import SearchLineupMemo
        self.service = service
        self.pinned = service.snapshot()
        self.weeks = {}
        self.lineup_memo = SearchLineupMemo(reuse_scope if reuse_scope is not None else object())
        self.lineup_solver = self.lineup_memo.solve

    def snapshot(self):
        return self.pinned

    def week_snapshot(self, week, *, generation_snapshot):
        if generation_snapshot is not self.pinned:
            raise ValueError('Projection search generation mismatch')
        if week not in self.weeks:
            self.weeks[week] = self.service.week_snapshot(week, generation_snapshot=self.pinned)
        return self.weeks[week]


def _search_reader(data, payload, boundary):
    from services.trade_workspace_context import workspace_context
    binding = workspace_context(data, int(payload.get('active_roster_id') or 0))['binding']
    return _SearchProjectionReader(_trade_projection_service(data), reuse_scope=(binding, boundary))


def _trade_search_boundary(data: dict[str, Any]) -> str:
    """Ephemeral consistency guard; never persist source payloads or this digest.

    The request already owns a canonical league read. Include all its inputs so
    an in-place update cannot silently escape a hand-maintained generation list.
    Projection publication is separate from the league data object.
    """
    service = _trade_projection_service(data)
    snapshot = service.snapshot() or {}
    identity = {key: snapshot.get(key) for key in (
        'league_id', 'projection_snapshot_id', 'horizon_generation', 'schema_version',
        'model_version', 'contract_version', 'semantic_policy_version', 'scoring_profile_id')}
    return sha256(json.dumps((data, identity), sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def generate_trade_workflow(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Bounded generation adapter; manual analysis remains available for any construction."""
    started = perf_counter()
    active_id = int(payload.get("active_roster_id") or 0)
    workflow = str(payload.get("workflow") or "recommended")
    if workflow == 'recommended':
        return _generate_recommended(data, payload)
    targeted_search = workflow in {'trade_for', 'shop'}
    if workflow not in {"trade_for", "shop", "recommended"}:
        raise ValueError("Generated workflow must be trade_for, shop, or recommended.")
    target = str(payload.get("asset_id") or "")
    if targeted_search and not target:
        raise ValueError('Targeted trade search requires a specific canonical asset.')
    protected = {str(item) for item in payload.get("protected_assets") or ()}
    excluded = {str(item) for item in payload.get("excluded_assets") or ()}
    boundary = _trade_search_boundary(data) if targeted_search else None
    projection_reader = _search_reader(data, payload, boundary) if targeted_search else None
    workspace = build_trade_workspace(data, active_id)
    _requested_strategy(workspace, payload)
    teams = {int(team.get("roster_id") or 0): team for team in workspace["teams"]}
    ownership = {asset.asset_id: roster_id for roster_id, pool in workspace["pools"].items() for asset in pool}
    if target and target not in ownership:
        raise ValueError("The selected trade asset is no longer available in the canonical league context.")
    if workflow == "shop" and target and ownership[target] != active_id:
        raise ValueError("Shop Asset requires an asset currently owned by the active Front Office.")
    if workflow == "trade_for" and target and ownership[target] == active_id:
        raise ValueError("Trade For requires an asset currently owned by another franchise.")
    partner_ids = [ownership[target]] if workflow == "trade_for" and target else [identifier for identifier in sorted(teams) if identifier != active_id]
    requested_partner = int(payload.get("partner_roster_id") or 0)
    if requested_partner:
        if requested_partner not in partner_ids:
            raise TradeInputError("legality_rejected", "The selected counterparty does not own the requested target or is not a valid trade partner.")
        partner_ids = [requested_partner]
    target_asset = next(a for a in workspace['pools'][ownership[target]] if a.asset_id == target)
    if (workflow == 'shop' and target in protected | excluded) or (workflow == 'trade_for' and target in excluded):
        objective = 'required outgoing Shop asset' if workflow == 'shop' else 'required incoming Trade For target'
        explanation = f'Your exact lock on {target_asset.label} ({target}) conflicts with the {objective}. No package was evaluated for this conflicting request.'
        return {'workflow': workflow, 'target_asset_id': target, 'count': 0, 'results': [],
                'state': 'CONSTRAINT_CONFLICT', 'result_state': 'CONSTRAINT CONFLICT',
                'quiet_state': explanation, 'conflict_explanation': explanation,
                'blocking_asset_ids': [target],
                'smallest_optional_relaxation': f'Remove the conflicting exact lock on {target_asset.label} ({target}), or explicitly choose a different trade objective.',
                'constraints': {'protected_assets': sorted(protected), 'excluded_assets': sorted(excluded)},
                'search_completed': False, 'search_evidence': {'full_evaluations': 0, 'bounded': True},
                **({'markets': []} if workflow == 'shop' else {}), 'provider_requests': 0}
    if target_asset.trade_value is None:
        return {'workflow': workflow, 'target_asset_id': target, 'count': 0, 'results': [],
                'result_state': 'MISSING REQUIRED EVIDENCE', 'quiet_state': 'Canonical Market price is unavailable for the selected exact asset.',
                'search_evidence': {'full_evaluations': 0, 'missing_asset_ids': [target], 'bounded': True,
                    'stages': [{'partner_id': ownership[target], 'stage': 'required_target_market_evidence',
                                'unavailable_target_price': True, 'constructed_candidates': 0}]},
                'constraints': {'protected_assets': sorted(protected), 'excluded_assets': sorted(excluded)},
                **({'markets': []} if workflow == 'shop' else {}), 'provider_requests': 0}
    eligible_partner_ids = tuple(partner_ids)
    shop_preference = None
    shop_discovery = []
    shop_markets = []
    if workflow == 'shop':
        from services.shop_asset_search import preference, discover, unsupported_requirement
        shop_preference = preference(payload)
        unsupported = unsupported_requirement(workspace, partner_ids, shop_preference, excluded)
        if unsupported:
            return {'workflow': 'shop', 'count': 0, 'results': [], 'markets': [], 'shop_preference': shop_preference,
                    'result_state': 'UNSUPPORTED GOAL', 'quiet_state': unsupported,
                    'search_evidence': {'full_evaluations': 0, 'bounded': True}, 'provider_requests': 0}
        target_asset = next(a for a in workspace['pools'][active_id] if a.asset_id == target)
        shop_discovery = discover(workspace, partner_ids, target_asset, shop_preference, excluded)
        if target in protected | excluded:
            for row in shop_discovery:
                row['discovered'] = False
                row['reasons'].append('SHOPPED_ASSET_PROTECTED_OR_EXCLUDED')
        partner_ids = [row['roster_id'] for row in shop_discovery if row['discovered']]
    generated = []
    evidence_context = build_trade_evidence_context(
        data, (asset for pool in workspace["pools"].values() for asset in pool),
    )
    proposals_considered = 0
    proposals_rejected = 0
    full_evaluations = 0
    generation_seconds = evaluation_seconds = 0.0
    stage_counts, rejection_reasons = [], {}
    from services.trade_search_policy import SearchFunnel, diverse_rows, result_state
    funnel = SearchFunnel(240, eligible_partner_ids, workspace['pools'])
    assessed = set()
    for phase in range(3):
        for partner_id in partner_ids:
            generation_started = perf_counter()
            diagnostics = {}
            outgoing = tuple(a for a in workspace['pools'][active_id] if a.asset_id not in protected | excluded) if targeted_search else workspace['pools'][active_id]
            incoming = tuple(a for a in workspace['pools'][partner_id] if a.asset_id not in excluded) if targeted_search else workspace['pools'][partner_id]
            proposals = generate_proposals(
                active_id, partner_id,
                outgoing, incoming,
                required_sent_asset_id=target if workflow == "shop" else None,
                required_received_asset_id=target if workflow == "trade_for" else None,
                construction_only=targeted_search,
                search_diagnostics=diagnostics,
                search_phase=phase,
                **({'return_preference': shop_preference} if workflow == 'shop' else {}),
            )
            generation_seconds += perf_counter() - generation_started
            stage_counts.append({'partner_id': partner_id, 'initial_league_asset_universe': sum(len(p) for p in workspace['pools'].values()),
                                 'after_ownership': {'sent': len(workspace['pools'][active_id]), 'received': len(workspace['pools'][partner_id])},
                                 'after_constraints': {'sent': len(outgoing), 'received': len(incoming)}, **diagnostics})
            proposals_considered += len(proposals)
            funnel.construction(partner_id, proposals, diagnostics)
            for proposal in proposals:
                sent = tuple(asset.asset_id for asset in proposal.assets_sent)
                received = tuple(asset.asset_id for asset in proposal.assets_received)
                if protected.intersection(sent) or excluded.intersection((*sent, *received)):
                    continue
                if workflow == "trade_for" and target not in received:
                    continue
                if workflow == "shop" and target not in sent:
                    continue
                signature = (partner_id, tuple(sorted(sent)), tuple(sorted(received)))
                if signature in assessed or full_evaluations >= funnel.budget:
                    continue
                assessed.add(signature)
                evaluation_started = perf_counter()
                result = evaluate_trade_request(
                    data, _proposal_payload(proposal, workflow), workspace=workspace,
                    evidence_context=evidence_context,
                    **({'projection_reader': projection_reader} if targeted_search else {}),
                )
                evaluation_seconds += perf_counter() - evaluation_started
                full_evaluations += 1
                qualifies = funnel.assessed(result)
                result['workflow_eligibility'] = {'workflow': workflow, 'eligible': qualifies}
                if qualifies:
                    result["partner_team_name"] = str(teams[partner_id].get("team_name") or teams[partner_id].get("owner") or "Unassigned Franchise")
                    generated.append(result)
                else:
                    proposals_rejected += 1
                    for reason in result['evaluation'].get('recommendation_trace', {}).get('rule_reasons', []):
                        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                    plausibility = result['evaluation'].get('dimensions', {}).get('counterparty_plausibility', {}).get('assessment')
                    if plausibility in ('LOW', 'INSUFFICIENT EVIDENCE'):
                        key = 'COUNTERPARTY_' + plausibility.replace(' ', '_')
                        rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
        assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        if (len(diverse_rows(generated, assets, limit=5)) >= 5 or full_evaluations >= funnel.budget
                or not partner_ids or not any(a.asset_id not in protected | excluded for a in workspace['pools'][active_id])
                or projection_reader.snapshot() is None
                or (not generated and full_evaluations and funnel.counts['missing_evidence'] == full_evaluations)):
            break
    if workflow == 'trade_for':
        generated.sort(key=lambda row: (row['evaluation']['values']['sent'],
                                       row['evaluation']['provenance']['evaluation_id']))
        by_id = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        generated = _distinct_trade_for_offers(generated, by_id)
        # Prefer different constructions before tiny variants with the same shape.
        shapes, rest = {}, []
        for row in generated:
            shape = (tuple(sorted(by_id[i].kind for i in row['proposal']['assets_sent'])),
                     tuple(sorted(by_id[i].kind for i in row['proposal']['assets_received'])))
            if shape not in shapes:
                shapes[shape] = row
            else:
                rest.append(row)
        generated = list(shapes.values()) + rest
    elif workflow == 'shop':
        from services.shop_asset_search import rank_returns
        assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        markets = {}
        for row, ranking in rank_returns(generated, assets, shop_preference):
            row['shop_ranking_evidence'] = ranking
            markets.setdefault(row['proposal']['partner_roster_id'], []).append(row)
        for rid, rows in markets.items():
            distinct = _distinct_trade_for_offers(rows, assets)[:3]
            shop_markets.append({'counterparty_roster_id': rid, 'returns': distinct,
                'buyer_rationale': distinct[0]['evaluation']['dimensions']['counterparty_plausibility'],
                'ranking_basis': 'explicit shared dimensions; preference ordering, not an independent Shop score'})
        shop_markets = shop_markets[:5]
        generated = [market['returns'][0] for market in shop_markets]
    else:
        generated.sort(key=lambda row: (
            row["evaluation"]["values"]["ratio"] < 1,
            -int(row["evaluation"]["dimensions"]["historical_counterparty_evidence"]["score"]),
            abs(1 - row["evaluation"]["values"]["ratio"]),
            row["evaluation"]["provenance"]["evaluation_id"],
        ))
    limit = 5 if workflow in {"shop", "recommended"} else 3
    offer_labels = ("LOWEST MARKET COST FOUND", "ALTERNATIVE CONSTRUCTION", "ALTERNATIVE CONSTRUCTION") if workflow == "trade_for" else ()
    for index, result in enumerate(generated[:limit]):
        if index < len(offer_labels):
            result["offer_level"] = offer_labels[index]
    next_paths = []
    closest_path = None
    if not generated and workflow == "trade_for" and target:
        target_asset = next(asset for asset in workspace["pools"][ownership[target]] if asset.asset_id == target)
        next_paths = [
            "No candidate in this bounded search cleared the shared bilateral evaluator.",
            "Review protected/excluded assets or inspect a specific construction in Create Trade.",
        ]
        closest_path = {
            "target_asset_id": target,
            "target_value": target_asset.trade_value,
            "owner_roster_id": ownership[target],
            "guidance": next_paths[0],
            "availability": "target_context_only_not_a_verified_acquisition_path",
        }
    if targeted_search and _trade_search_boundary(data) != boundary:
        raise TradeInputError('workspace_context_changed', 'Canonical evidence changed during trade search. Refresh and run the search again.')
    return {
        "workflow": workflow, "target_asset_id": target or None,
        "result_state": "HARD INVALID" if target in excluded or (workflow == "shop" and target in protected) else result_state(funnel, generated[:limit]), "near_misses": funnel.near(),
        "count": min(len(generated), limit), "results": generated[:limit],
        "quiet_state": None if generated else (("The shopped asset is protected or excluded by this search's constraints." if target in protected | excluded else "No credible market in this bounded Shop search.") if workflow == 'shop' else "No legitimate bilateral construction clears the current constraints."),
        **({'shop_preference': shop_preference, 'markets': shop_markets, 'counterparty_discovery': shop_discovery} if workflow == 'shop' else {}),
        "next_paths": next_paths,
        "closest_path": closest_path,
        "search_evidence": {
            **funnel.result(min(len(generated), limit)),
            'stages': stage_counts, 'rejection_reason_counts': rejection_reasons,
            'timings_seconds': {'candidate_generation': generation_seconds, 'shared_evaluation': evaluation_seconds,
                               'total_workflow': perf_counter() - started},
            'full_evaluations': full_evaluations,
            "partner_count": len(partner_ids),
            "package_shapes": max((row.get("shape_count", 6) for row in stage_counts), default=6),
            "proposals_considered": proposals_considered,
            "proposals_rejected": proposals_rejected,
            "result_count": min(len(generated), limit),
            "bounded": True,
            "behavior_profiles_loaded": len(evidence_context.behavior_by_roster),
            "trend_summaries_loaded": len(evidence_context.trends_by_asset),
            "historical_context_duration_ms": evidence_context.preparation_duration_ms,
            "reuse": projection_reader.lineup_memo.status(),
            "wrong_league_evidence_rejected": evidence_context.wrong_league_evidence_rejected,
            "wrong_league_evidence_consumed": evidence_context.wrong_league_evidence_consumed,
            "provider_requests": 0,
            "raw_history_scans": 0,
            "profile_rebuilds": 0,
            "trend_rebuilds": 0,
        },
        "generated_only_after_counterparty_gate": True,
        "provider_requests": 0,
        "asset_market_constructions": 0,
        "raw_history_scans": 0,
        "profile_rebuilds": 0,
        "trend_rebuilds": 0,
        "historical_context_generation": evidence_context.generation,
        "wrong_league_evidence_rejected": evidence_context.wrong_league_evidence_rejected,
        "wrong_league_evidence_consumed": evidence_context.wrong_league_evidence_consumed,
        "constraints": {"protected_assets": sorted(protected), "excluded_assets": sorted(excluded)},
    }


def _generate_recommended(data, payload):
    """Progressive bounded discovery with actual evaluated near misses."""
    from services.recommended_trade_search import session_constraints, discover, construct, family_identity, surface_evidence
    from services.trade_search_policy import SearchFunnel, diverse_rows, result_state
    started = perf_counter()
    selected_filter, excluded_families = session_constraints(payload)
    if payload.get('asset_id') or payload.get('partner_roster_id'):
        raise ValueError('Recommended Trades discovers its own targets and counterparties.')
    if selected_filter == 'sell_high':
        return {'workflow': 'recommended', 'count': 0, 'results': [], 'result_state': 'UNSUPPORTED GOAL',
                'quiet_state': 'Sell High requires comparable Market movement and a supported sale rationale; that evidence is unavailable.',
                'search_evidence': {'full_evaluations': 0, 'bounded': True}, 'provider_requests': 0, 'durable_writes': 0}
    protected = {str(a) for a in payload.get('protected_assets') or []}
    excluded = {str(a) for a in payload.get('excluded_assets') or []}
    boundary = _trade_search_boundary(data)
    reader = _search_reader(data, payload, boundary)
    workspace = build_trade_workspace(data, int(payload.get('active_roster_id') or 0))
    _requested_strategy(workspace, payload)
    assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    projection_available = bool(reader.snapshot() and str(reader.snapshot().get('league_id')) == str(workspace['manager_context'].league_id))
    evidence_context = build_trade_evidence_context(data, assets.values())
    funnel = SearchFunnel(180, [rid for rid in workspace['pools'] if rid != workspace['active_roster_id']], workspace['pools'])
    evaluated, constructed, seen = [], 0, set()
    construction_seconds = evaluation_seconds = derivation_seconds = 0.0
    tag = {'win_now': 'WIN-NOW OPPORTUNITY', 'value': 'VALUE OPPORTUNITY', 'roster_fit': 'ROSTER CONSTRUCTION',
           'future': 'FUTURE VALUE'}.get(selected_filter)
    discoveries = []
    for phase in range(3):
        discovery = discover(data, workspace, reader, protected, excluded, max_theses=(6, 24, 48)[phase],
                             excluded_families=excluded_families, search_phase=phase)
        discoveries.append(discovery)
        # Round-robin theses across teams before considering variants.
        packages = []
        for thesis in discovery['theses']:
            stage = perf_counter()
            diagnostics = {}
            proposals = construct(workspace, thesis, protected, excluded, search_phase=phase, search_diagnostics=diagnostics)
            construction_seconds += perf_counter() - stage
            constructed += len(proposals)
            funnel.construction(thesis['partner_id'], proposals, diagnostics)
            packages.append((thesis, proposals))
        for index in range((3, 6, 8)[phase]):
            for thesis, proposals in packages:
                if index >= len(proposals) or len(seen) >= funnel.budget:
                    continue
                p = _proposal_payload(proposals[index], 'recommended')
                key = (p['partner_roster_id'], tuple(sorted(p['assets_sent'])), tuple(sorted(p['assets_received'])))
                if key in seen:
                    continue
                seen.add(key)
                stage = perf_counter()
                row = evaluate_trade_request(data, p, workspace=workspace, evidence_context=evidence_context, projection_reader=reader)
                evaluation_seconds += perf_counter() - stage
                stage = perf_counter()
                row['family_id'] = family_identity(workspace['manager_context'].league_id, row, assets)
                row['opportunity'] = surface_evidence(row)
                row['discovery_thesis'] = thesis
                derivation_seconds += perf_counter() - stage
                filtered = row['family_id'] in excluded_families or bool(tag and tag not in row['opportunity']['reason_tags'])
                qualifies = funnel.assessed(row, filtered=filtered)
                row['workflow_eligibility'] = {'workflow': 'recommended', 'eligible': qualifies}
                if qualifies:
                    evaluated.append(row)
        results = diverse_rows(evaluated, assets)
        if len(results) >= 5 or len(seen) >= funnel.budget or not projection_available:
            break
    results = diverse_rows(evaluated, assets)
    if _trade_search_boundary(data) != boundary:
        raise TradeInputError('workspace_context_changed', 'Canonical evidence changed during recommendation discovery. Refresh and try again.')
    return {'workflow': 'recommended', 'count': len(results), 'results': results,
            'result_state': 'MISSING REQUIRED EVIDENCE' if not projection_available and not results else result_state(funnel, results), 'near_misses': funnel.near(),
            'quiet_state': None if results else 'Canonical projection evidence is unavailable for this league.' if not projection_available
                else 'Required trade evidence is unavailable; review the evaluated near misses.' if result_state(funnel, results) == 'MISSING REQUIRED EVIDENCE'
                else 'No credible result within the bounded search and current filters. Review evaluated near misses.',
            'recommendation_filter': selected_filter, 'discovery': discovery,
            'has_more': bool(results and projection_available and (discovery.get('omitted_theses') or len(evaluated) > len(results) or phase < 2)),
            'search_evidence': {**funnel.result(len(results)), 'stages': funnel.stages, 'phases': len(discoveries),
                'full_evaluations': len(seen), 'packages_constructed': constructed,
                'qualifying_before_session_filter': funnel.counts['eligible'] + funnel.counts['filtered'],
                'timings_seconds': {'discovery': sum(d['discovery_seconds'] for d in discoveries), 'candidate_generation': construction_seconds,
                    'shared_evaluation': evaluation_seconds, 'reason_derivation': derivation_seconds, 'total_workflow': perf_counter() - started},
                'bounded': True, 'projection_weeks_read': len(reader.weeks), 'provider_requests': 0,
                'reuse': reader.lineup_memo.status(),
                'raw_history_scans': 0, 'durable_writes': 0},
            'constraints': {'protected_assets': sorted(protected), 'excluded_assets': sorted(excluded)},
            'session': {'persistence': 'request_only', 'excluded_family_count': len(excluded_families), 'maximum_families': 256},
            'provider_requests': 0, 'durable_writes': 0, 'generated_only_after_counterparty_gate': True}


def autocomplete_trade_assets(data: dict[str, Any], query: str, active_roster_id: int | None = None, limit: int = 20) -> dict[str, Any]:
    workspace = build_trade_workspace(data, active_roster_id)
    needle = query.strip().casefold()
    rows = []
    for team in workspace["teams"]:
        roster_id = int(team.get("roster_id") or 0)
        team_name = str(team.get("team_name") or team.get("owner") or "Unassigned Franchise")
        for asset in workspace["pools"][roster_id]:
            searchable = f"{asset.asset_id} {asset.label} {asset.position or ''} {asset.season or ''} {asset.round or ''}".casefold()
            if needle and needle not in searchable:
                continue
            identity = asset.label
            if asset.kind == "pick":
                identity = asset.exact_slot or f"{asset.season} Round {asset.round} — {asset.projected_range or 'UNKNOWN'}"
            rows.append({
                "asset_id": asset.asset_id, "kind": asset.kind, "label": identity,
                "position": asset.position, "owner_roster_id": roster_id, "owner_team_name": team_name,
                "owned_by_active_roster": roster_id == workspace["active_roster_id"],
                "projected_range": asset.projected_range, "range_confidence": asset.projected_range_confidence,
                "exact_slot": asset.exact_slot, "positional_rank": asset.positional_rank,
                "market_value": asset.trade_value, "market_fact": asset.market_fact,
            })
    rows.sort(key=lambda row: (not str(row["label"]).casefold().startswith(needle), str(row["label"]).casefold(), row["asset_id"]))
    return {"query": query, "count": min(len(rows), limit), "results": rows[:limit], "ownership_revalidation_required": True}


def compare_trade_requests(data: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    boundary = _trade_search_boundary(data)
    reader = _SearchProjectionReader(_trade_projection_service(data))
    if not 2 <= len(proposals) <= 4:
        raise ValueError("Compare Trades requires between two and four proposals.")
    active_id = int(proposals[0].get("active_roster_id") or 0)
    if any(int(row.get("active_roster_id") or 0) != active_id for row in proposals):
        raise ValueError("Compare Trades requires one controlled Front Office context.")
    workspace = build_trade_workspace(data, active_id)
    evidence_context = build_trade_evidence_context(
        data, (asset for pool in workspace["pools"].values() for asset in pool),
    )
    evaluations = [
        evaluate_trade_request(
            data, proposal, workspace=workspace, evidence_context=evidence_context, projection_reader=reader,
        ) for proposal in proposals
    ]
    from services.recommended_trade_search import rank
    # Same explicit canonical ordering, not a Market ratio substituted for all
    # strategy dimensions. Temporary family keys do not change the evaluations.
    sortable = [dict(row, family_id=row['evaluation']['provenance']['evaluation_id']) for row in evaluations]
    ranked = [{key: value for key, value in row.items() if key != 'family_id'} for row in rank(sortable)]
    if _trade_search_boundary(data) != boundary:
        raise TradeInputError('workspace_context_changed', 'Canonical evidence changed during comparison. Refresh and try again.')
    preferred = ranked[0]['evaluation']['provenance']['evaluation_id'] if _trade_for_eligible(ranked[0]['evaluation']) else None
    return {"count": len(ranked), "preferred_evaluation_id": preferred, "comparisons": ranked,
            "basis": ["Canonical Recommendation", "Counterparty Plausibility", "Confidence", "Scoped Horizon Effects"],
            'preference_availability': 'supported' if preferred else 'unavailable'}
