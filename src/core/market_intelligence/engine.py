"""Market Intelligence provider orchestration and opportunity discovery."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.market_intelligence.aggregation import build_consensus
from src.core.market_intelligence.cache import MarketQuoteCache
from src.core.market_intelligence.evidence import build_market_evidence
from src.core.market_intelligence.history import MarketHistoryStore, MarketSnapshot
from src.core.market_intelligence.models import AssetMarketReport, MarketIntelligenceReport, TradeMarketImpact, ValueGap, ValueGapLabel
from src.core.market_intelligence.providers import MarketProviderRegistry, default_market_registry
from src.core.market_intelligence.trends import calculate_trend


def value_gap(intrinsic: int, market: int | None, confidence: int) -> ValueGap:
    if market is None or confidence < 35:
        return ValueGap(intrinsic, market, None, None, ValueGapLabel.UNCERTAIN, confidence)
    difference = intrinsic - market
    percentage = round(difference / max(abs(market), 1) * 100, 2)
    label = ValueGapLabel.UNDERVALUED if percentage >= 12 else ValueGapLabel.OVERVALUED if percentage <= -12 else ValueGapLabel.FAIR
    return ValueGap(intrinsic, market, difference, percentage, label, confidence)


def _opportunity(gap: ValueGap, trend_direction: str) -> str:
    if gap.label is ValueGapLabel.UNDERVALUED:
        return "Buy Low" if trend_direction != "Rising" else "Acquire Before Value Rises"
    if gap.label is ValueGapLabel.OVERVALUED:
        return "Sell High" if trend_direction != "Falling" else "Future Depreciation"
    if gap.label is ValueGapLabel.UNCERTAIN:
        return "Monitor"
    return "Hold"


class MarketIntelligence:
    def __init__(self, registry: MarketProviderRegistry | None = None, cache: MarketQuoteCache | None = None, history: MarketHistoryStore | None = None) -> None:
        self.registry = registry or default_market_registry()
        self.cache = cache or MarketQuoteCache()
        self.history = history or MarketHistoryStore()
        self._health: dict[str, dict[str, object]] = {}

    def evaluate(self, context: Any, player_reports: dict[str, Any], trades: tuple[Any, ...]) -> MarketIntelligenceReport:
        generated_at = datetime.now(timezone.utc).isoformat()
        market_data = context.cached_data.get("market_data") or {}
        context_mode = str(market_data.get("context_mode") or ("online" if market_data.get("providers") else "offline")).casefold()
        allow_cached_fallback = bool(market_data.get("allow_cached_fallback", False))
        namespace = f"{context.league_id}:{context.active_roster_id}"
        players = context.cached_data.get("players") or {}
        intrinsic_by_id = {str(asset_id): int(report.core_values.dynasty.score) for asset_id, report in player_reports.items()}
        labels = {str(player_id): str(row.get("full_name") or player_id) for player_id, row in players.items()}
        reports: dict[str, AssetMarketReport] = {}
        health: dict[str, dict[str, object]] = {name: {"status": "unavailable", "available_quotes": 0, "latency_ms": 0.0, "last_updated": None} for name in self.registry.names()}
        for asset_id, intrinsic in intrinsic_by_id.items():
            asset = {**(players.get(asset_id) or {}), "id": asset_id, "player_id": asset_id}
            quotes = tuple(
                self.cache.quote(
                    provider.name,
                    asset_id,
                    lambda provider=provider: provider.quote(asset_id, asset, market_data),
                    namespace=namespace,
                    context_mode=context_mode,
                    provider_version=str(market_data.get("provider_version") or "v1"),
                    allow_cached_fallback=allow_cached_fallback,
                    maximum_stale_seconds=float(market_data.get("maximum_stale_seconds") or self.cache.ttl_seconds),
                )
                for provider in self.registry.providers()
            )
            asset_snapshots: list[MarketSnapshot] = []
            for quote in quotes:
                state = health[quote.provider]
                state["latency_ms"] = round(float(state["latency_ms"]) + quote.latency_ms, 3)
                if quote.available:
                    state["status"] = "cached_snapshot" if quote.retrieval_mode == "cached_fallback" else "cache_hit" if quote.cached else "available"
                    state["available_quotes"] = int(state["available_quotes"]) + 1
                    state["last_updated"] = max(filter(None, (state["last_updated"], quote.observed_at)), default=None)
                    state["retrieval_mode"] = quote.retrieval_mode
                    state["cache_age_seconds"] = quote.cache_age_seconds
                    state["freshness"] = quote.freshness
                    state["confidence_impact"] = quote.confidence_impact
                    asset_snapshots.append(MarketSnapshot(asset_id, quote.observed_at or generated_at, quote.provider, float(quote.value), quote.confidence))
            consensus = build_consensus(asset_id, quotes, self.registry.names())
            self.history.append(tuple(asset_snapshots))
            trend = calculate_trend(self.history.for_asset(asset_id))
            gap = value_gap(intrinsic, consensus.value, consensus.confidence)
            evidence = build_market_evidence(consensus, gap, trend)
            reports[asset_id] = AssetMarketReport(asset_id, labels.get(asset_id, asset_id), consensus, gap, trend, _opportunity(gap, trend.direction), evidence)
        impacts = tuple(self._trade_impact(dossier, reports) for dossier in trades)
        opportunities = tuple(sorted((item for item in reports.values() if item.opportunity not in {"Hold", "Monitor"}), key=lambda item: (item.value_gap.confidence, abs(item.value_gap.difference or 0)), reverse=True))
        evidence = tuple(item for report in opportunities[:5] for item in report.evidence[:4])
        self._health = health
        offline = context_mode == "offline"
        return MarketIntelligenceReport(reports, opportunities, impacts, evidence, health, generated_at, offline)

    @staticmethod
    def _trade_impact(dossier: Any, reports: dict[str, AssetMarketReport]) -> TradeMarketImpact:
        sent = [reports.get(str(asset.asset_id)) for asset in dossier.proposal.assets_sent]
        received = [reports.get(str(asset.asset_id)) for asset in dossier.proposal.assets_received]
        sent_values = [item.consensus.value for item in sent if item and item.consensus.value is not None]
        received_values = [item.consensus.value for item in received if item and item.consensus.value is not None]
        gain = round(sum(received_values) - sum(sent_values)) if sent_values or received_values else None
        known = [item for item in (*sent, *received) if item]
        consensus = ", ".join(f"{item.label}: {item.consensus.value if item.consensus.value is not None else 'unavailable'}" for item in known) or "No provider-backed asset consensus is available."
        movement = ", ".join(f"{item.label} {item.trend.direction.lower()}" for item in known) or "No historical movement is available."
        arbitrage = "Provider-backed value gap exists; review both teams' context." if any(item.value_gap.label not in {ValueGapLabel.FAIR, ValueGapLabel.UNCERTAIN} for item in known) else "No supported market arbitrage is currently identified."
        evidence = tuple(item for report in known for item in report.evidence[:2])
        return TradeMarketImpact(dossier.proposal.active_roster_id, dossier.proposal.partner_roster_id, gain, consensus, movement, arbitrage, evidence)

    def health(self) -> dict[str, object]:
        return {"providers": self._health or {name: {"status": "not_run"} for name in self.registry.names()}, "cache": self.cache.health()}


market_intelligence = MarketIntelligence()
