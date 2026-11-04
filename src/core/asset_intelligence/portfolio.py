"""Portfolio-level adapters consumed by the Decision Engine."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.asset_intelligence.models import AssetContext, AssetEvaluation, Evidence
from src.core.asset_intelligence.players.player_evaluator import evaluate_player


def evaluate_player_portfolio(players: tuple[dict[str, Any], ...], context: AssetContext) -> AssetEvaluation:
    if not players:
        evidence = (Evidence("Player inventory", "0 players", 0, "A neutral value is retained because no players are available.", "Sleeper roster", False),)
        return AssetEvaluation("Player Portfolio", None, 0, "No player assets are available for evaluation.", evidence, ("No player dossiers could be generated.",))
    reports = tuple(evaluate_player(player, context) for player in players)
    values = [report.core_values.dynasty.score for report in reports]
    if any(value is None for value in values):
        return AssetEvaluation('Player Portfolio', None, 0,
            'No supported aggregate long-term player scalar.',
            tuple(item for report in reports for item in report.core_values.dynasty.evidence),
            ('Market holdings, projected lineup and production quality are separate roster dimensions.',))
    known = sum(report.profile.age is not None for report in reports)
    evidence = (
        Evidence("Player dossier values", f"{len(values)} dossiers; mean {mean(values):.1f}", mean(values) - 50, "The portfolio is the arithmetic mean of individually explainable dynasty values.", "Asset Intelligence player reports"),
        Evidence("Age coverage", f"{known}/{len(values)} known", 0, "Coverage is disclosed because age is a primary v1 dynasty input.", "Sleeper player records", known > 0),
    )
    limitations = tuple(dict.fromkeys(limit for report in reports for limit in report.core_values.dynasty.limitations))
    return AssetEvaluation("Player Portfolio", round(mean(values)), min(report.core_values.dynasty.confidence for report in reports), "Aggregate of individual Asset Intelligence player dossiers.", evidence, limitations)


def evaluate_pick_portfolio(picks: tuple[dict[str, Any], ...], context: AssetContext) -> AssetEvaluation:
    # Counts are inventory facts, not quality against one league's round count.
    firsts = sum(str(pick.get('round')) == '1' for pick in picks)
    evidence = (
        Evidence("Pick inventory", f"{len(picks)} picks", 0, "Owned inventory; no assumed league-round benchmark.", "Sleeper pick ledger"),
        Evidence("First-round inventory", f"{firsts} firsts", 0, "Count, not a portfolio quality score.", "Sleeper pick ledger"),
    )
    return AssetEvaluation("Pick Portfolio", None, 0,
        "Owned draft capital; consume canonical portfolio distributions and separate Market evidence.",
        evidence, ("No supported aggregate pick utility scalar.",))
