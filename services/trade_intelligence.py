"""Application-facing Trade Intelligence view assembly."""
from __future__ import annotations

from typing import Any
from hashlib import sha256
import json

from src.core.intelligence import AssetContext, TradeProposal, build_asset_pool, build_league_model, evaluate_bilateral, generate_proposals, intelligence_orchestrator
from src.core.valuation import cached_market_consensus


def build_trade_center(data: dict[str, Any], active_roster_id: int | None = None) -> dict[str, Any]:
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    roster_id = active_roster_id if active_roster_id in valid_ids else int(teams[0].get("roster_id") or 0)
    active_team = next(team for team in teams if int(team.get("roster_id") or 0) == roster_id)
    intelligence = intelligence_orchestrator.analyze(data, roster_id)
    dossiers: tuple[Any, ...] = intelligence.trades
    impacts = {}
    for dossier in dossiers:
        def totals(assets: tuple[Any, ...], attribute: str) -> float:
            return sum(float(getattr(intelligence.player_values.get(asset.asset_id), attribute).value or 0) for asset in assets if intelligence.player_values.get(asset.asset_id))

        def projections(assets: tuple[Any, ...]) -> float:
            return sum(float(intelligence.player_values[asset.asset_id].projection.projected_points or 0) for asset in assets if asset.asset_id in intelligence.player_values)

        received, sent = dossier.proposal.assets_received, dossier.proposal.assets_sent
        impacts[dossier.partner.roster_id] = {
            "dtos_dynasty": round(totals(received, "dtos_dynasty") - totals(sent, "dtos_dynasty"), 1),
            "market": round(totals(received, "market_consensus") - totals(sent, "market_consensus"), 1),
            "contender": round(totals(received, "contender") - totals(sent, "contender"), 1),
            "rebuild": round(totals(received, "rebuilder") - totals(sent, "rebuilder"), 1),
            "weekly": round(projections(received) - projections(sent), 2),
        }
    workspace = build_trade_workspace(data, roster_id)
    canonical_results = []
    accepted_dossiers = []
    for dossier in dossiers:
        result = evaluate_trade_request(data, _proposal_payload(dossier.proposal, "recommended"), workspace=workspace)
        if not result["evaluation"]["generated_trade_eligible"]:
            continue
        accepted_dossiers.append(dossier)
        result["partner_team_name"] = next(
            str(team.get("team_name") or team.get("owner") or "Unassigned Franchise")
            for team in teams if int(team.get("roster_id") or 0) == dossier.proposal.partner_roster_id
        )
        result["package_type"] = dossier.proposal.package_type
        canonical_results.append(result)
    return {"active_team": active_team, "teams": teams, "dossiers": tuple(accepted_dossiers), "canonical_results": canonical_results, "value_impacts": impacts, "unified_recommendation": intelligence.recommendation, "brain": intelligence.brain, "brain_recommendation": intelligence.brain_decision, "decision_confidence": intelligence.brain_decision.confidence}


def build_trade_workflow_context(
    data: dict[str, Any], active_roster_id: int | None = None,
) -> dict[str, Any]:
    """Return only the league identity needed for an initial workflow render."""
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    roster_id = (
        active_roster_id if active_roster_id in valid_ids
        else int(teams[0].get("roster_id") or 0)
    )
    active_team = next(
        team for team in teams if int(team.get("roster_id") or 0) == roster_id
    )
    return {"active_team": active_team, "teams": teams}


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
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    roster_id = active_roster_id if active_roster_id in valid_ids else int(teams[0].get("roster_id") or 0)
    model = build_league_model(data)
    decisions = {identifier: report.decision for identifier, report in model.reports.items()}
    player_ids = {str(player.get("id") or player.get("player_id")) for team in teams for player in team.get("players") or ()}
    market_values = cached_market_consensus(data.get("market_data") or {}, player_ids)
    pools = {}
    for team in teams:
        identifier = int(team.get("roster_id") or 0)
        pools[identifier] = build_asset_pool(data, team, _context(decisions[identifier]), market_values)
    return {"active_roster_id": roster_id, "teams": teams, "pools": pools, "workflows": WORKFLOWS}


def evaluate_trade_request(
    data: dict[str, Any], payload: dict[str, Any], *, workspace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_id = int(payload.get("active_roster_id") or 0)
    partner_id = int(payload.get("partner_roster_id") or 0)
    workspace = workspace or build_trade_workspace(data, active_id)
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
    evaluation = evaluate_bilateral(
        proposal, active_team=teams[active_id], partner_team=teams[partner_id], league=data.get("league") or {},
        player_database=data.get("players") or {}, ownership=ownership,
    )
    identity_input = {
        "league_id": str((data.get("league") or {}).get("league_id") or data.get("league_id") or ""),
        "active_roster_id": active_id, "partner_roster_id": partner_id,
        "assets_sent": sorted(sent_ids), "assets_received": sorted(received_ids),
        "market_generation": str((data.get("market_data") or {}).get("generation") or (data.get("market_data") or {}).get("generated_at") or "current"),
        "projection_generation": str((data.get("projection_intelligence") or {}).get("generation") or "current"),
        "evaluator": "bilateral_trade_v1",
    }
    evaluation["provenance"]["evaluation_id"] = sha256(json.dumps(identity_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    evaluation["provenance"]["inputs"] = identity_input
    evaluation["actions"] = ["EDIT TRADE", "ADJUST OFFER"]
    if not evaluation["generated_trade_eligible"]:
        evaluation["repair_paths"] = ["MAKE THIS TRADE WORK", "ALTERNATIVE CONSTRUCTION", "ALTERNATIVE TARGET"]
    return {"workflow": str(payload.get("workflow") or "create"), "proposal": {"active_roster_id": active_id, "partner_roster_id": partner_id, "assets_sent": sent_ids, "assets_received": received_ids}, "evaluation": evaluation}


def _proposal_payload(proposal: TradeProposal, workflow: str = "adjust") -> dict[str, Any]:
    return {
        "workflow": workflow,
        "active_roster_id": proposal.active_roster_id,
        "partner_roster_id": proposal.partner_roster_id,
        "assets_sent": [asset.asset_id for asset in proposal.assets_sent],
        "assets_received": [asset.asset_id for asset in proposal.assets_received],
        "package_type": proposal.package_type,
    }


def _bounded_adjustment_candidates(workspace: dict[str, Any], payload: dict[str, Any]) -> tuple[TradeProposal, ...]:
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
    sent = tuple(by_id[item] for item in sent_ids)
    received = tuple(by_id[item] for item in received_ids)
    candidates = list(generate_proposals(active_id, partner_id, pools[active_id], pools[partner_id]))
    active_options = sorted(
        (asset for asset in pools[active_id] if asset.asset_id not in protected | excluded | set(sent_ids)),
        key=lambda asset: (abs(asset.trade_value - max((item.trade_value for item in received), default=0)), -asset.trade_value, asset.asset_id),
    )[:10]
    partner_options = sorted(
        (asset for asset in pools[partner_id] if asset.asset_id not in excluded | set(received_ids)),
        key=lambda asset: (abs(asset.trade_value - max((item.trade_value for item in sent), default=0)), -asset.trade_value, asset.asset_id),
    )[:10]
    if sent and received:
        for asset in active_options:
            candidates.append(TradeProposal(active_id, partner_id, (*sent, asset), received, "Assisted Addition"))
            for index in range(len(sent)):
                if sent[index].asset_id not in protected:
                    candidates.append(TradeProposal(active_id, partner_id, sent[:index] + (asset,) + sent[index + 1:], received, "Assisted Replacement"))
        for asset in partner_options:
            candidates.append(TradeProposal(active_id, partner_id, sent, (*received, asset), "Assisted Return"))
            for index in range(len(received)):
                candidates.append(TradeProposal(active_id, partner_id, sent, received[:index] + (asset,) + received[index + 1:], "Alternative Target"))
        if len(sent) > 1:
            candidates.extend(TradeProposal(active_id, partner_id, sent[:index] + sent[index + 1:], received, "Assisted Reduction") for index in range(len(sent)) if sent[index].asset_id not in protected)
        if len(received) > 1:
            candidates.extend(TradeProposal(active_id, partner_id, sent, received[:index] + received[index + 1:], "Assisted Reduction") for index in range(len(received)))
    unique: dict[tuple[tuple[str, ...], tuple[str, ...]], TradeProposal] = {}
    for proposal in candidates:
        sent_key = tuple(sorted(asset.asset_id for asset in proposal.assets_sent))
        received_key = tuple(sorted(asset.asset_id for asset in proposal.assets_received))
        if not sent_key or not received_key or protected.intersection(sent_key) or excluded.intersection((*sent_key, *received_key)):
            continue
        unique.setdefault((sent_key, received_key), proposal)
    return tuple(unique[key] for key in sorted(unique))[:250]


def assist_trade_request(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Return calculated repair/adjustment options, never static action labels."""
    active_id = int(payload.get("active_roster_id") or 0)
    workspace = build_trade_workspace(data, active_id)
    original_sent = set(str(item) for item in payload.get("assets_sent") or ())
    original_received = set(str(item) for item in payload.get("assets_received") or ())
    instruction = str(payload.get("instruction") or payload.get("action") or "make this trade work").strip()
    lowered = instruction.casefold()
    enriched = dict(payload)
    protected = {str(item) for item in payload.get("protected_assets") or ()}
    excluded = {str(item) for item in payload.get("excluded_assets") or ()}
    active_assets = workspace["pools"].get(active_id, ())
    all_assets = tuple(asset for pool in workspace["pools"].values() for asset in pool)
    by_id = {asset.asset_id: asset for asset in all_assets}
    for asset in active_assets:
        label = asset.label.casefold()
        if label in lowered and any(prefix in lowered for prefix in ("don't trade", "do not trade", "keep ", "protect ")):
            protected.add(asset.asset_id)
    for asset in all_assets:
        label = asset.label.casefold()
        if label in lowered and any(prefix in lowered for prefix in ("replace ", "exclude ", "not this ")):
            excluded.add(asset.asset_id)
    enriched["protected_assets"] = sorted(protected)
    enriched["excluded_assets"] = sorted(excluded)
    unresolved_reference = (
        ("keep this player" in lowered or "do not trade this pick" in lowered) and not protected
    ) or ("replace this asset" in lowered and not excluded)
    if unresolved_reference:
        return {
            "instruction": instruction,
            "count": 0,
            "results": [],
            "quiet_state": "Choose or name the specific player or pick so DTOS can apply that constraint safely.",
            "calculated": True,
            "provider_requests": 0,
            "asset_market_constructions": 0,
            "constraints": {"protected_assets": sorted(protected), "excluded_assets": sorted(excluded)},
            "interpretation_error": "specific_asset_required",
        }
    original_sent_assets = tuple(by_id[item] for item in original_sent if item in by_id)
    original_received_assets = tuple(by_id[item] for item in original_received if item in by_id)
    requested_position = next((position for position in ("WR", "RB", "QB", "TE") if f"{position.casefold()}s instead" in lowered or f"{position.casefold()} instead" in lowered), None)
    requested_kind = "pick" if "pick" in lowered and "instead" in lowered else None
    add_pick = "add a pick" in lowered
    another_player = "another player back" in lowered
    expand = "expand" in lowered or "bigger deal" in lowered
    cheaper = "cheaper" in lowered
    younger = "younger" in lowered
    win_now = "win-now" in lowered or "win now" in lowered
    candidates = []
    for proposal in _bounded_adjustment_candidates(workspace, enriched):
        result = evaluate_trade_request(data, _proposal_payload(proposal), workspace=workspace)
        if not result["evaluation"]["generated_trade_eligible"]:
            continue
        sent = set(result["proposal"]["assets_sent"])
        received = set(result["proposal"]["assets_received"])
        sent_assets = tuple(by_id[item] for item in sent)
        received_assets = tuple(by_id[item] for item in received)
        if requested_kind and not any(asset.kind == requested_kind for asset in sent_assets):
            continue
        if requested_position and not any(asset.position == requested_position for asset in sent_assets):
            continue
        if add_pick and sum(asset.kind == "pick" for asset in (*sent_assets, *received_assets)) <= sum(asset.kind == "pick" for asset in (*original_sent_assets, *original_received_assets)):
            continue
        if another_player and sum(asset.kind == "player" for asset in received_assets) <= sum(asset.kind == "player" for asset in original_received_assets):
            continue
        if expand and len(sent_assets) + len(received_assets) <= len(original_sent_assets) + len(original_received_assets):
            continue
        if cheaper and sum(asset.trade_value for asset in sent_assets) >= sum(asset.trade_value for asset in original_sent_assets):
            continue
        original_ages = [asset.age for asset in original_received_assets if asset.age is not None]
        candidate_ages = [asset.age for asset in received_assets if asset.age is not None]
        if younger and (not original_ages or not candidate_ages or sum(candidate_ages) / len(candidate_ages) >= sum(original_ages) / len(original_ages)):
            continue
        if win_now and sum(asset.redraft_value for asset in received_assets) <= sum(asset.redraft_value for asset in original_received_assets):
            continue
        distance = len(sent ^ original_sent) + len(received ^ original_received)
        target_changed = bool(received != original_received)
        candidates.append((distance, target_changed, abs(1 - result["evaluation"]["values"]["ratio"]), result))
    candidates.sort(key=lambda row: (row[0], row[2], row[3]["evaluation"]["provenance"]["evaluation_id"]))
    closest = candidates[0][3] if candidates else None
    materially_different = next((row[3] for row in candidates if row[0] >= 2 and not row[1]), None)
    alternative_target = next((row[3] for row in candidates if row[1]), None)
    options = []
    if closest:
        closest["repair_type"] = "MAKE THIS TRADE WORK"
        options.append(closest)
    if materially_different and materially_different is not closest:
        materially_different["repair_type"] = "ALTERNATIVE CONSTRUCTION"
        options.append(materially_different)
    if alternative_target and alternative_target not in options:
        alternative_target["repair_type"] = "ALTERNATIVE TARGET"
        options.append(alternative_target)
    return {
        "instruction": instruction,
        "count": len(options),
        "results": options,
        "quiet_state": None if options else "No legitimate revised construction clears ownership, market, package-quality, and bilateral gates.",
        "calculated": True,
        "provider_requests": 0,
        "asset_market_constructions": 0,
        "constraints": {"protected_assets": sorted(protected), "excluded_assets": sorted(excluded)},
    }


def create_trade_alternatives(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Return up to three distinct, editable approaches to the same negotiation goal."""
    active_id = int(payload.get("active_roster_id") or 0)
    workspace = build_trade_workspace(data, active_id)
    by_id = {asset.asset_id: asset for pool in workspace["pools"].values() for asset in pool}
    sent_ids = tuple(str(item) for item in payload.get("assets_sent") or ())
    received_ids = tuple(str(item) for item in payload.get("assets_received") or ())
    if not sent_ids or not received_ids or any(item not in by_id for item in (*sent_ids, *received_ids)):
        raise ValueError("Create Trade alternatives require one valid asset on each side.")
    key_asset_id = str(payload.get("protected_asset_id") or max((by_id[item] for item in sent_ids), key=lambda asset: (asset.trade_value, asset.asset_id)).asset_id)
    target_id = max((by_id[item] for item in received_ids), key=lambda asset: (asset.trade_value, asset.asset_id)).asset_id
    original = (frozenset(sent_ids), frozenset(received_ids))

    def evaluated(candidate_payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for proposal in _bounded_adjustment_candidates(workspace, candidate_payload):
            result = evaluate_trade_request(data, _proposal_payload(proposal, "create_alternative"), workspace=workspace)
            if result["evaluation"]["generated_trade_eligible"]:
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
    return {
        "count": len(chosen[:3]), "results": chosen[:3], "protected_asset_id": key_asset_id,
        "target_asset_id": target_id, "calculated": True, "provider_requests": 0,
        "asset_market_constructions": 0,
        "quiet_state": None if chosen else "The original construction is currently the strongest legitimate path; no materially different alternative clears bilateral quality gates.",
    }


def generate_trade_workflow(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Bounded generation adapter; manual analysis remains available for any construction."""
    active_id = int(payload.get("active_roster_id") or 0)
    workflow = str(payload.get("workflow") or "recommended")
    if workflow not in {"trade_for", "shop", "recommended"}:
        raise ValueError("Generated workflow must be trade_for, shop, or recommended.")
    target = str(payload.get("asset_id") or "")
    protected = {str(item) for item in payload.get("protected_assets") or ()}
    excluded = {str(item) for item in payload.get("excluded_assets") or ()}
    workspace = build_trade_workspace(data, active_id)
    teams = {int(team.get("roster_id") or 0): team for team in workspace["teams"]}
    ownership = {asset.asset_id: roster_id for roster_id, pool in workspace["pools"].items() for asset in pool}
    if target and target not in ownership:
        raise ValueError("The selected trade asset is no longer available in the canonical league context.")
    if workflow == "shop" and target and ownership[target] != active_id:
        raise ValueError("Shop Asset requires an asset currently owned by the active Front Office.")
    if workflow == "trade_for" and target and ownership[target] == active_id:
        raise ValueError("Trade For requires an asset currently owned by another franchise.")
    partner_ids = [ownership[target]] if workflow == "trade_for" and target else [identifier for identifier in sorted(teams) if identifier != active_id]
    generated = []
    for partner_id in partner_ids:
        proposals = generate_proposals(
            active_id, partner_id, workspace["pools"][active_id], workspace["pools"][partner_id],
            required_sent_asset_id=target if workflow == "shop" else None,
            required_received_asset_id=target if workflow == "trade_for" else None,
        )
        for proposal in proposals:
            sent = tuple(asset.asset_id for asset in proposal.assets_sent)
            received = tuple(asset.asset_id for asset in proposal.assets_received)
            if protected.intersection(sent) or excluded.intersection((*sent, *received)):
                continue
            if workflow == "trade_for" and target not in received:
                continue
            if workflow == "shop" and target not in sent:
                continue
            result = evaluate_trade_request(data, _proposal_payload(proposal, workflow), workspace=workspace)
            if result["evaluation"]["generated_trade_eligible"]:
                result["partner_team_name"] = str(teams[partner_id].get("team_name") or teams[partner_id].get("owner") or "Unassigned Franchise")
                generated.append(result)
    generated.sort(key=lambda row: (row["evaluation"]["values"]["ratio"] < 1, abs(1 - row["evaluation"]["values"]["ratio"]), row["evaluation"]["provenance"]["evaluation_id"]))
    limit = 5 if workflow in {"shop", "recommended"} else 3
    offer_labels = ("CHEAPEST PLAUSIBLE", "FAIR OFFER", "BEST OFFER") if workflow == "trade_for" else ()
    for index, result in enumerate(generated[:limit]):
        if index < len(offer_labels):
            result["offer_level"] = offer_labels[index]
    return {
        "workflow": workflow, "target_asset_id": target or None,
        "count": min(len(generated), limit), "results": generated[:limit],
        "quiet_state": None if generated else "No legitimate bilateral construction clears the current constraints.",
        "generated_only_after_counterparty_gate": True,
        "constraints": {"protected_assets": sorted(protected), "excluded_assets": sorted(excluded)},
    }


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
                "exact_slot": asset.exact_slot,
            })
    rows.sort(key=lambda row: (not str(row["label"]).casefold().startswith(needle), str(row["label"]).casefold(), row["asset_id"]))
    return {"query": query, "count": min(len(rows), limit), "results": rows[:limit], "ownership_revalidation_required": True}


def compare_trade_requests(data: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    if not 2 <= len(proposals) <= 4:
        raise ValueError("Compare Trades requires between two and four proposals.")
    evaluations = [evaluate_trade_request(data, proposal) for proposal in proposals]
    ranked = sorted(evaluations, key=lambda row: (
        not row["evaluation"]["generated_trade_eligible"],
        abs(1 - row["evaluation"]["values"]["ratio"]),
        row["evaluation"]["provenance"]["evaluation_id"],
    ))
    return {"count": len(ranked), "preferred_evaluation_id": ranked[0]["evaluation"]["provenance"]["evaluation_id"], "comparisons": ranked, "basis": ["Value Fairness", "Strategic Fit", "Counterparty Plausibility", "Package Quality", "Lineup Impact", "Confidence"]}
