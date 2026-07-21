"""Unified orchestration of DTOS's four intelligence pillars."""
from __future__ import annotations

from time import perf_counter
from typing import Any

from src.core.asset_intelligence import AssetContext, evaluate_pick, evaluate_player
from src.core.asset_intelligence.portfolio import evaluate_pick_portfolio, evaluate_player_portfolio
from src.core.decision_engine import DecisionContext, evaluate_team
from src.core.front_office_intelligence import build_league_model
from src.core.intelligence.cache import IntelligenceCache, intelligence_cache
from src.core.intelligence.confidence import calculate_confidence
from src.core.intelligence.context import IntelligenceContext, build_context
from src.core.intelligence.evidence import aggregate_evidence, normalize_evidence
from src.core.intelligence.models import IntelligenceResult
from src.core.intelligence.pipeline import IntelligencePipeline
from src.core.intelligence.recommendations import resolve_recommendation
from src.core.intelligence.registry import IntelligenceRegistry, intelligence_registry
from src.core.trade_intelligence import trade_intelligence


def _decision_provider(context: IntelligenceContext) -> dict[int, Any]:
    return {
        int(team.get("roster_id") or 0): evaluate_team(
            context.cached_data,
            int(team.get("roster_id") or 0),
            DecisionContext(int(team.get("roster_id") or 0), context.league_id, context.settings),
        )
        for team in context.teams
    }


def _asset_context(context: IntelligenceContext, decision: Any) -> AssetContext:
    depths = {position: room.total_players for position, room in decision.profile.position_rooms.items()}
    needs = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55)
    return AssetContext(context.league_id, context.active_roster_id, context.settings, decision.window.value, decision.profile.strategy, needs, depths, decision.profile.market_context.get("position_counts") or {})


def _asset_provider(context: IntelligenceContext, decision: Any) -> tuple[Any, Any]:
    asset_context = _asset_context(context, decision)
    return evaluate_player_portfolio(decision.profile.players, asset_context), evaluate_pick_portfolio(decision.profile.picks, asset_context)


def _front_office_provider(context: IntelligenceContext, decisions: dict[int, Any]) -> Any:
    return build_league_model(context.cached_data, decisions)


def _trade_provider(context: IntelligenceContext, decisions: dict[int, Any], front_offices: Any) -> tuple[Any, ...]:
    return trade_intelligence.opportunities(context.cached_data, context.active_roster_id, decisions=decisions, front_office_model=front_offices)


def _register_defaults(registry: IntelligenceRegistry) -> None:
    defaults = {"decision": _decision_provider, "asset": _asset_provider, "front_office": _front_office_provider, "trade": _trade_provider}
    existing = set(registry.names())
    for name, provider in defaults.items():
        if name not in existing:
            registry.register(name, provider)


class IntelligenceOrchestrator:
    def __init__(self, registry: IntelligenceRegistry = intelligence_registry, cache: IntelligenceCache = intelligence_cache) -> None:
        self.registry = registry
        self.cache = cache
        self.last_timings_ms: dict[str, float] = {}
        self.last_error: str | None = None
        self.runs = 0
        _register_defaults(registry)

    def context(self, data: dict[str, Any], roster_id: int, user_preferences: dict[str, Any] | None = None) -> IntelligenceContext:
        return build_context(data, roster_id, user_preferences)

    def analyze(self, data: dict[str, Any], roster_id: int, user_preferences: dict[str, Any] | None = None, *, refresh: bool = False) -> IntelligenceResult:
        context = self.context(data, roster_id, user_preferences)
        prefix = f"snapshot:{context.snapshot_key}:"
        key = prefix + "result"
        if refresh:
            self.cache.invalidate(prefix)
        before_hits = self.cache.hits

        def execute() -> IntelligenceResult:
            total_started = perf_counter()
            pipeline = IntelligencePipeline()
            decisions = pipeline.run("decision_engine", self.cache.get_or_create, prefix + "league", lambda: self.registry.provider("decision")(context))
            decision = decisions[roster_id]
            player_portfolio, pick_portfolio = pipeline.run("asset_intelligence", self.cache.get_or_create, prefix + "assets", lambda: self.registry.provider("asset")(context, decision))
            offices = pipeline.run("front_office_intelligence", self.cache.get_or_create, prefix + "front_offices", lambda: self.registry.provider("front_office")(context, decisions))
            trades = pipeline.run("trade_intelligence", self.cache.get_or_create, prefix + "trades", lambda: self.registry.provider("trade")(context, decisions, offices))
            top_trade = trades[0] if trades else None
            evidence = aggregate_evidence((
                normalize_evidence("Decision Engine", decision.current_outlook.factors + decision.future_outlook.factors),
                normalize_evidence("Asset Intelligence", player_portfolio.evidence + pick_portfolio.evidence),
                normalize_evidence("Front Office Intelligence", offices.reports[roster_id].evidence),
                normalize_evidence("Trade Intelligence", top_trade.recommendation.evidence if top_trade else ()),
            ))
            missing = tuple(dict.fromkeys((*player_portfolio.limitations, *pick_portfolio.limitations)))
            confidence = calculate_confidence(evidence, providers=4, market_available=False, sample_size=offices.reports[roster_id].activity.trades, missing=missing)
            recommendation = resolve_recommendation(decision=decision, trade=top_trade, front_office=offices.reports[roster_id], evidence=evidence, confidence=confidence)
            pipeline.timings_ms["orchestration_total"] = round((perf_counter() - total_started) * 1000, 3)
            return IntelligenceResult(context, decision, decisions, player_portfolio, pick_portfolio, offices, trades, recommendation, pipeline.timings_ms, False)

        try:
            result = self.cache.get_or_create(key, execute)
            self.runs += 1
            cache_hit = self.cache.hits > before_hits
            self.last_timings_ms = result.timings_ms
            self.last_error = None
            if cache_hit and not result.cache_hit:
                return IntelligenceResult(result.context, result.decision, result.decisions, result.player_portfolio, result.pick_portfolio, result.front_office_model, result.trades, result.recommendation, result.timings_ms, True)
            return result
        except Exception as exc:
            self.last_error = str(exc)
            raise

    def health(self, sleeper_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = sleeper_state or {}
        provider_status = "healthy" if self.last_error is None else "degraded"
        return {
            "status": provider_status,
            "engines": {name: {"status": provider_status} for name in self.registry.names()},
            "sleeper": {"status": "connected" if state.get("last_error") is None and state.get("last_sync") else "cached_fallback" if state.get("data") else "unavailable", "last_sync": state.get("last_sync"), "last_error": state.get("last_error")},
            "cache": self.cache.health(),
            "database": {"status": "not_configured", "detail": "DTOS currently uses the configured cache file."},
            "orchestration": {"runs": self.runs, "last_timings_ms": self.last_timings_ms, "last_error": self.last_error},
        }

    def player_report(self, data: dict[str, Any], player: dict[str, Any], roster_id: int) -> Any:
        result = self.analyze(data, roster_id)
        return evaluate_player(player, _asset_context(result.context, result.decision))

    def pick_report(self, data: dict[str, Any], pick: dict[str, Any], roster_id: int) -> Any:
        result = self.analyze(data, roster_id)
        return evaluate_pick(pick, _asset_context(result.context, result.decision))


intelligence_orchestrator = IntelligenceOrchestrator()
