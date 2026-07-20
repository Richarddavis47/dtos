"""Stable facade for player and draft-pick intelligence."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence.models import AssetContext, PickReport, PlayerReport
from src.core.asset_intelligence.picks.pick_evaluator import evaluate_pick
from src.core.asset_intelligence.players.player_evaluator import evaluate_player


class AssetIntelligence:
    def player_report(self, player: dict[str, Any], context: AssetContext) -> PlayerReport:
        return evaluate_player(player, context)

    def pick_report(self, pick: dict[str, Any], context: AssetContext) -> PickReport:
        return evaluate_pick(pick, context)


asset_intelligence = AssetIntelligence()
