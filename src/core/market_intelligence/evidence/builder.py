"""Traceable market evidence generation."""
from __future__ import annotations

from src.core.market_intelligence.models import MarketConsensus, MarketEvidence, MarketTrend, ValueGap


def build_market_evidence(consensus: MarketConsensus, gap: ValueGap, trend: MarketTrend) -> tuple[MarketEvidence, ...]:
    rows = [
        MarketEvidence("Market consensus", str(consensus.value) if consensus.value is not None else "Unavailable", (consensus.value or 50) - 50, "A robust confidence-weighted center limits outlier influence.", "Market Consensus", consensus.value is not None),
        MarketEvidence("Provider agreement", f"{consensus.agreement}%", consensus.agreement - 50, "Dispersion across available providers determines agreement.", "Market Consensus", bool(consensus.quotes)),
        MarketEvidence("Value gap", gap.label.value, gap.difference or 0, "Intrinsic and market values remain independent; their difference identifies possible opportunity, not an automatic action.", "Value Gap Engine", gap.market_value is not None),
        MarketEvidence("Trend", f"{trend.direction}; {trend.momentum:+.2f}%", trend.momentum, "Historical cached snapshots determine direction and momentum.", "Market History", any(value is not None for value in trend.periods.values())),
    ]
    rows.extend(
        MarketEvidence(
            item.provider,
            f"{item.value if item.available else 'Unavailable'}; mode={item.retrieval_mode}; freshness={item.freshness}; age={item.cache_age_seconds if item.cache_age_seconds is not None else 'n/a'}s",
            ((item.value or 50) - 50) + item.confidence_impact,
            f"{item.detail} Provider status, retrieval mode, freshness, cache age, and confidence impact are disclosed.",
            item.source,
            item.available,
        )
        for item in consensus.quotes
    )
    return tuple(rows)
