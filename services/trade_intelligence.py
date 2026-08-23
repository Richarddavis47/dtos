"""Application-facing Trade Intelligence view assembly."""
from __future__ import annotations

from typing import Any
from hashlib import sha256
import json

from src.core.intelligence import AssetContext, TradeProposal, build_asset_pool, build_league_model, evaluate_bilateral, intelligence_orchestrator
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
    return {"active_team": active_team, "teams": teams, "dossiers": dossiers, "value_impacts": impacts, "unified_recommendation": intelligence.recommendation, "brain": intelligence.brain, "brain_recommendation": intelligence.brain_decision, "decision_confidence": intelligence.brain_decision.confidence}


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


def evaluate_trade_request(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    active_id = int(payload.get("active_roster_id") or 0)
    partner_id = int(payload.get("partner_roster_id") or 0)
    workspace = build_trade_workspace(data, active_id)
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


def generate_trade_workflow(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Bounded generation adapter; manual analysis remains available for any construction."""
    active_id = int(payload.get("active_roster_id") or 0)
    workflow = str(payload.get("workflow") or "recommended")
    if workflow not in {"trade_for", "shop", "recommended"}:
        raise ValueError("Generated workflow must be trade_for, shop, or recommended.")
    target = str(payload.get("asset_id") or "")
    protected = {str(item) for item in payload.get("protected_assets") or ()}
    excluded = {str(item) for item in payload.get("excluded_assets") or ()}
    center = build_trade_center(data, active_id)
    generated = []
    for dossier in center["dossiers"]:
        sent = tuple(asset.asset_id for asset in dossier.proposal.assets_sent)
        received = tuple(asset.asset_id for asset in dossier.proposal.assets_received)
        if protected.intersection(sent) or excluded.intersection((*sent, *received)):
            continue
        if workflow == "trade_for" and (not target or target not in received):
            continue
        if workflow == "shop" and (not target or target not in sent):
            continue
        result = evaluate_trade_request(data, {
            "workflow": workflow, "active_roster_id": active_id,
            "partner_roster_id": dossier.proposal.partner_roster_id,
            "assets_sent": sent, "assets_received": received,
            "package_type": dossier.proposal.package_type,
        })
        if result["evaluation"]["generated_trade_eligible"]:
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
