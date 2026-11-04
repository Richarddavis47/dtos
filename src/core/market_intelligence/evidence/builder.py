"""Traceable market evidence generation."""
from __future__ import annotations

from src.core.market_intelligence.models import MarketConsensus, MarketEvidence, MarketTrend, ValueGap


def build_market_evidence(consensus: MarketConsensus, gap: ValueGap, trend: MarketTrend) -> tuple[MarketEvidence, ...]:
    rows = [
        # Impact is a recommendation contribution, not the observed evidence.
        # Price magnitude and provider agreement imply no directional action.
        MarketEvidence(consensus.evidence_state, str(consensus.value) if consensus.value is not None else "Unavailable", 0, consensus.warning or "Source-scoped external price 0–1000; price magnitude is not a recommendation.", "Market Evidence", consensus.value is not None),
        MarketEvidence("Provider agreement", f"{consensus.agreement}/100" if consensus.agreement is not None else "Unavailable", 0, "Requires multiple admitted providers; agreement is not outcome probability.", "Market Consensus", consensus.agreement is not None),
        MarketEvidence("Value gap", gap.label.value if gap.difference is not None else "Unavailable", 0, "No directional recommendation is inferred from unlike or unavailable evidence concepts.", "Value Gap Engine", gap.difference is not None),
        MarketEvidence("Trend", f"{trend.direction}; {trend.momentum:+.2f}%" if trend.momentum is not None else "Unavailable", trend.momentum if trend.momentum is not None else 0, "Comparable provider, concept, scale, format, methodology and ordered timestamps are required.", "Market History", trend.momentum is not None),
    ]
    rows.extend(
        MarketEvidence(
            item.provider,
            f"raw={item.value if item.available else 'Unavailable'}; normalized={item.normalized_value if item.normalized_value is not None else 'Unavailable'}/1000; mode={item.retrieval_mode}; freshness={item.freshness}; age={item.cache_age_seconds if item.cache_age_seconds is not None else 'n/a'}s",
            0,
            f"{item.detail} Provider status, retrieval mode, freshness, cache age, and confidence impact are disclosed.",
            item.source,
            item.available,
        )
        for item in consensus.quotes
    )
    return tuple(rows)
