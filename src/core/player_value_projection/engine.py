"""Unified, contextual player values built from existing intelligence evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.player_value_projection.models import DataStatus, LineupValue, PlayerValueProfile, PositionalContext, ValueMetric
from src.core.player_value_projection.providers import PlayerDataRegistry, player_data_registry
from src.core.valuation import CalibrationStatus, PlayerIntelligenceCard, normalize_internal
from src.core.valuation.models import ConsensusProvider


def _metric(value: float | None, source: str, status: DataStatus, confidence: int, limitations: tuple[str, ...] = ()) -> ValueMetric:
    return ValueMetric(round(value, 2) if value is not None else None, source, status, confidence, datetime.now(timezone.utc).isoformat() if status != DataStatus.UNAVAILABLE else None, limitations)


def _posture(gap: float | None, liquidity: int, confidence: int, calibration: CalibrationStatus) -> str:
    if liquidity < 35:
        return "Illiquid"
    if gap is None or confidence < 55 or calibration not in {CalibrationStatus.CALIBRATED, CalibrationStatus.PARTIALLY_CALIBRATED}:
        return "Monitor — calibration incomplete"
    return "Strong Buy" if gap >= 120 else "Buy" if gap >= 60 else "Strong Sell" if gap <= -120 else "Sell" if gap <= -60 else "Fair Value"


def evaluate_player_values(context: Any, decision: Any, reports: dict[str, Any], market: Any, registry: PlayerDataRegistry = player_data_registry) -> dict[str, PlayerValueProfile]:
    scoring = context.cached_data.get("scoring_settings") or context.settings.get("scoring_settings") or {}
    week = context.cached_data.get("week")
    raw_by_id = {str(player.get("id") or player.get("player_id")): player for player in decision.profile.players}
    projections = {player_id: registry.projection().project(raw_by_id[player_id], report.core_values.redraft.score, scoring, int(week) if week else None) for player_id, report in reports.items()}
    supplies = decision.profile.market_context.get("position_counts") or {}
    profiles: dict[str, PlayerValueProfile] = {}
    for player_id, report in reports.items():
        raw = raw_by_id[player_id]
        projection = projections[player_id]
        same_position = sorted((item.projected_points or 0 for key, item in projections.items() if reports[key].profile.position == report.profile.position))
        replacement = same_position[max(0, len(same_position) // 3 - 1)] if same_position else 0
        starters = [raw_by_id[key] for key in reports if reports[key].profile.position == report.profile.position and raw_by_id[key].get("roster_slot") == "Starter"]
        starter_points = [projections[str(item.get("id") or item.get("player_id"))].projected_points or 0 for item in starters]
        current_starter = min(starter_points) if starter_points else replacement
        above_replacement = round((projection.projected_points or 0) - replacement, 2)
        above_starter = round((projection.projected_points or 0) - current_starter, 2)
        market_report = market.assets.get(player_id)
        consensus = market_report.consensus.value if market_report else None
        quotes = [quote.value for quote in market_report.consensus.quotes if quote.value is not None] if market_report else []
        market_status = DataStatus.UNAVAILABLE
        if market_report and quotes:
            modes = {quote.retrieval_mode for quote in market_report.consensus.quotes if quote.value is not None}
            market_status = DataStatus.LIVE if "online" in modes else DataStatus.CACHED
        dynasty = normalize_internal(report.core_values.dynasty.score)
        redraft = normalize_internal(report.core_values.redraft.score)
        team_fit = normalize_internal(report.core_values.team_fit.score)
        contender = round(redraft * .55 + team_fit * .30 + dynasty * .15)
        rebuilder = round(dynasty * .70 + team_fit * .20 + normalize_internal(100 - report.risk.score) * .10)
        scarcity = max(0, min(100, round(100 - int(supplies.get(report.profile.position, 0)) / max(1, len(context.teams)) * 12)))
        liquidity = max(0, min(100, round(((consensus if consensus is not None else dynasty) / 10) * .65 + (market_report.consensus.confidence if market_report else 25) * .35)))
        gap = round(dynasty - consensus, 2) if consensus is not None else None
        calibration = CalibrationStatus(market_report.consensus.calibration_status) if market_report else CalibrationStatus.INSUFFICIENT_DATA
        position_reports = [item for item in reports.values() if item.profile.position == report.profile.position]
        dynasty_rank = 1 + sum(item.core_values.dynasty.score > dynasty for item in position_reports)
        weekly_rank = 1 + sum((projections[key].projected_points or 0) > (projection.projected_points or 0) for key in reports if reports[key].profile.position == report.profile.position)
        tier = report.archetypes[0]
        role = "Starter" if raw.get("roster_slot") == "Starter" else "Flex Upgrade" if above_starter > 0 else "Bench / Developmental"
        lineup = LineupValue(role, raw.get("roster_slot") == "Starter", report.profile.position in {"RB", "WR", "TE"}, report.profile.position == "QB" and "SUPER_FLEX" in context.settings.get("roster_positions", ()), round(replacement, 2), above_replacement, above_starter, max(0, min(100, round(50 + above_replacement * 5))), scarcity)
        positional = PositionalContext(dynasty_rank, dynasty_rank, weekly_rank, tier, scarcity, above_replacement, int(supplies.get(report.profile.position, 0)), dynasty_rank <= 2 and scarcity >= 65)
        production = registry.production().production(raw)
        limitations = tuple(dict.fromkeys((*report.limitations, *projection.limitations, *production.limitations)))
        evidence = (f"DTOS intrinsic value {dynasty}/1000 remains independent from provider market evidence.", f"Projection state is {projection.status.value} from {projection.source}.", f"Projects {above_replacement:+.2f} points above roster-specific replacement.", f"Market state is {market_status.value}; raw provider values are normalized before comparison.")
        name = report.profile.name
        initials = "".join(part[:1] for part in name.split()[:2]).upper() or "DT"
        confidence = market_report.consensus.confidence if market_report else 0
        provider_evidence = tuple(
            ConsensusProvider(quote.provider, float(quote.value), int(quote.normalized_value), dict(market_report.consensus.provider_weights).get(quote.provider, 0.0), quote.freshness)
            for quote in market_report.consensus.quotes
            if quote.value is not None and quote.normalized_value is not None
        ) if market_report else ()
        posture = _posture(gap, liquidity, confidence, calibration)
        card = PlayerIntelligenceCard(
            player_id, consensus, dynasty, contender, rebuilder, dynasty,
            round((dynasty + (consensus if consensus is not None else dynasty)) / 2),
            max(0, min(100, round((100 - report.risk.score) * .7))),
            50 if production.status is DataStatus.UNAVAILABLE else production.consistency or 50,
            60 if report.profile.nfl_team != "Free Agent" else 30,
            report.risk.score, liquidity, confidence, calibration, provider_evidence,
            posture, evidence, tuple(limitations[:3]),
        )
        normalized_quotes = sorted(quote.normalized_value for quote in market_report.consensus.quotes if quote.normalized_value is not None) if market_report else []
        profiles[player_id] = PlayerValueProfile(
            player_id, name, report.profile.position, report.profile.nfl_team, report.profile.age,
            raw.get("portrait_url") or raw.get("headshot_url"), "available" if raw.get("portrait_url") or raw.get("headshot_url") else "fallback", initials,
            _metric(dynasty, "DTOS Asset Intelligence", DataStatus.FALLBACK, report.core_values.dynasty.confidence, report.core_values.dynasty.limitations),
            _metric(consensus, "Market Intelligence normalized consensus" if consensus is not None else "Market Intelligence unavailable", market_status, confidence, tuple(f"Missing provider: {provider}" for provider in market_report.consensus.missing_providers) if market_report else ("No market snapshot available.",)),
            (normalized_quotes[0], normalized_quotes[-1]) if normalized_quotes else None,
            _metric(contender, "DTOS contender value · canonical 0–1000", DataStatus.FALLBACK, 65),
            _metric(rebuilder, "DTOS rebuild value · canonical 0–1000", DataStatus.FALLBACK, 65),
            _metric(redraft, "DTOS win-now value · canonical 0–1000", DataStatus.FALLBACK, report.core_values.redraft.confidence),
            _metric(round(dynasty * .7 + scarcity * 3), "DTOS positional value · canonical 0–1000", DataStatus.FALLBACK, 60),
            _metric(max(0, min(1000, round(dynasty + above_replacement * 20))), "DTOS replacement-adjusted value · canonical 0–1000", DataStatus.FALLBACK, projection.confidence),
            _metric(liquidity, "Market coverage and risk model · 0–100", market_status if consensus is not None else DataStatus.FALLBACK, 55),
            market_report.trend.direction if market_report else "Unavailable", gap, posture, projection, production, lineup, positional,
            report.recommendation.action.upper(), evidence, limitations, card,
        )
    return profiles
