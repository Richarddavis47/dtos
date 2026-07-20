"""Portfolio-level adapters consumed by the Decision Engine."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.asset_intelligence.models import AssetContext, AssetEvaluation, Evidence
from src.core.asset_intelligence.picks.pick_evaluator import evaluate_pick
from src.core.asset_intelligence.players.player_evaluator import evaluate_player


def evaluate_player_portfolio(players: tuple[dict[str, Any], ...], context: AssetContext) -> AssetEvaluation:
    if not players:
        evidence = (Evidence("Player inventory", "0 players", 0, "A neutral value is retained because no players are available.", "Sleeper roster", False),)
        return AssetEvaluation("Player Portfolio", 50, 35, "No player assets are available for evaluation.", evidence, ("No player dossiers could be generated.",))
    reports = tuple(evaluate_player(player, context) for player in players)
    values = [report.core_values.dynasty.score for report in reports]
    known = sum(report.profile.age is not None for report in reports)
    evidence = (
        Evidence("Player dossier values", f"{len(values)} dossiers; mean {mean(values):.1f}", mean(values) - 50, "The portfolio is the arithmetic mean of individually explainable dynasty values.", "Asset Intelligence player reports"),
        Evidence("Age coverage", f"{known}/{len(values)} known", 0, "Coverage is disclosed because age is a primary v1 dynasty input.", "Sleeper player records", known > 0),
    )
    limitations = tuple(dict.fromkeys(limit for report in reports for limit in report.core_values.dynasty.limitations))
    return AssetEvaluation("Player Portfolio", round(mean(values)), min(report.core_values.dynasty.confidence for report in reports), "Aggregate of individual Asset Intelligence player dossiers.", evidence, limitations)


def evaluate_pick_portfolio(picks: tuple[dict[str, Any], ...], context: AssetContext) -> AssetEvaluation:
    if not picks:
        evidence = (Evidence("Pick inventory", "0 picks", -50, "No owned picks are available in the cached ledger.", "Sleeper pick ledger"),)
        return AssetEvaluation("Pick Portfolio", 0, 70, "No current draft-pick inventory.", evidence)
    reports = tuple(evaluate_pick(pick, context) for pick in picks)
    option_values = [report.dynasty_value.score for report in reports]
    inventory_coverage = min(len(reports) / 12, 1) * 100
    firsts = sum(report.round == 1 for report in reports)
    first_coverage = min(firsts / 3, 1) * 100
    score = inventory_coverage * 0.35 + first_coverage * 0.35 + mean(option_values) * 0.30
    evidence = (
        Evidence("Pick inventory", f"{len(reports)} picks", inventory_coverage * 0.35, "35% coverage against a documented three-year, four-round benchmark.", "Sleeper pick ledger"),
        Evidence("First-round inventory", f"{firsts} firsts", first_coverage * 0.35, "35% coverage against a documented three-first benchmark.", "Sleeper pick ledger"),
        Evidence("Individual pick values", f"Mean {mean(option_values):.1f}", mean(option_values) * 0.30, "30% mean of individually explainable pick reports.", "Asset Intelligence pick reports"),
    )
    limitations = tuple(dict.fromkeys(limit for report in reports for limit in report.limitations))
    return AssetEvaluation("Pick Portfolio", round(score), min(report.dynasty_value.confidence for report in reports), "Inventory and individual pick reports combined with published weights.", evidence, limitations)
