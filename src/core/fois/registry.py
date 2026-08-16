"""Expandable category and metric registry for FOIS."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.fois.models import Directionality, MetricStatus


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    name: str
    category: str
    description: str
    directionality: Directionality = Directionality.HIGHER_IS_BETTER
    default_status: MetricStatus = MetricStatus.UNAVAILABLE
    weight: float = 1.0


_CATEGORY_METRICS = {
    "results": (
        "Championships", "Championship-game appearances", "Final Four appearances",
        "Playoff appearances", "Regular-season winning percentage",
        "Sustained winning seasons", "Average finish", "Best finish", "Worst finish",
        "Championship conversion rate", "Playoff advancement rate",
        "Contention-window length", "Reload efficiency", "Rebuild duration",
        "Long-term competitive consistency",
    ),
    "trading_asset_management": (
        "Trade activity", "Productive trade activity", "Value captured at transaction time",
        "Subsequent asset value change", "Championship-impact acquisitions",
        "Market timing", "Buy-low effectiveness", "Sell-high effectiveness",
        "Asset liquidity gained or lost", "Optionality created",
        "Roster-need alignment", "Competitive-window alignment", "Trade adaptability",
        "Repeat trade-partner access", "Relationship capital",
        "League-market exploitation", "Future-capital management", "Overpay efficiency",
        "Missed-opportunity analysis", "Recovery from unsuccessful trades",
    ),
    "roster_construction": (
        "Starting-lineup strength", "Elite-player concentration", "Positional balance",
        "Depth", "Replacement-level exposure", "Age-curve alignment",
        "Competitive-window coherence", "Roster flexibility", "Asset liquidity",
        "Injury resilience", "Bench utility", "Quarterback strength in superflex",
        "Tight-end advantage", "Future-pick support", "Contender readiness",
        "Rebuild readiness", "Dead-roster percentage",
        "Championship probability created", "Multi-year championship outlook",
        "Window-extension efficiency",
    ),
    "drafting_talent_evaluation": (
        "Rookie draft hit rate", "Value over expected draft slot", "Early-round hit rate",
        "Late-round hit rate", "Player development captured", "Breakout identification",
        "Bust avoidance", "Prospect-to-production conversion",
        "Draft-class strength adjustment", "Positional context",
        "Pick-value realization", "Drafted-player retention value",
        "Drafted-player trade value", "Talent forecasting accuracy",
        "Proven-player preference effectiveness", "Top-four rookie-pick utilization",
        "Mid and late pick efficiency",
    ),
    "waivers_transactions": (
        "Waiver activity", "Waiver value created", "FAAB efficiency",
        "Free-agent decision quality",
    ),
}


def _key(value: str) -> str:
    return value.casefold().replace("-", " ").replace("/", " ").replace(" ", "_")


DEFAULT_METRIC_REGISTRY = tuple(
    MetricDefinition(
        _key(name),
        name,
        category,
        f"FOIS {category.replace('_', ' ')} metric: {name}.",
        default_status=(
            MetricStatus.PROVISIONAL
            if name in {
                "Championships", "Playoff appearances",
                "Regular-season winning percentage", "Rebuild duration",
                "Trade activity", "Productive trade activity",
                "Starting-lineup strength", "Roster flexibility",
            }
            else MetricStatus.UNAVAILABLE
        ),
    )
    for category, names in _CATEGORY_METRICS.items()
    for name in names
)

CROSS_CATEGORY_TRAITS = {
    "adaptability": ("reload_efficiency", "trade_adaptability", "recovery_from_unsuccessful_trades"),
    "self_awareness": ("competitive_window_alignment", "roster_need_alignment"),
    "timing": ("market_timing", "championship_impact_acquisitions"),
    "risk_management": ("overpay_efficiency", "future_capital_management"),
    "league_intelligence": ("league_market_exploitation", "positional_context"),
    "market_access": ("repeat_trade_partner_access", "relationship_capital"),
    "relationship_capital": ("relationship_capital", "repeat_trade_partner_access"),
    "opportunity_creation": ("productive_trade_activity", "optionality_created"),
    "sustainable_aggression": ("trade_activity", "long_term_competitive_consistency"),
    "competitive_cycle_management": ("rebuild_duration", "window_extension_efficiency"),
    "decision_quality": ("value_captured_at_transaction_time", "pick_value_realization"),
    "process_versus_outcome_separation": ("overpay_efficiency", "championship_conversion_rate"),
}


def registry_by_category() -> dict[str, tuple[MetricDefinition, ...]]:
    return {
        category: tuple(metric for metric in DEFAULT_METRIC_REGISTRY if metric.category == category)
        for category in _CATEGORY_METRICS
    }
