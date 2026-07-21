"""Stable prioritization for generated trade dossiers."""
from __future__ import annotations

from src.core.trade_intelligence.models import TradeDossier, TradePriority


def prioritize(dossiers: tuple[TradeDossier, ...], limit: int = 12) -> tuple[TradeDossier, ...]:
    order = {
        TradePriority.URGENT: 0,
        TradePriority.HIGH: 1,
        TradePriority.MEDIUM: 2,
        TradePriority.LOW: 3,
        TradePriority.FUTURE_WATCH: 4,
    }
    unique = {}
    for dossier in dossiers:
        key = (
            dossier.proposal.partner_roster_id,
            tuple(asset.asset_id for asset in dossier.proposal.assets_sent),
            tuple(asset.asset_id for asset in dossier.proposal.assets_received),
        )
        unique.setdefault(key, dossier)
    ranked = sorted(
        unique.values(),
        key=lambda item: (
            order[item.recommendation.priority],
            -item.recommendation.expected_value,
            -item.partner.compatibility_score,
            item.recommendation.title,
        ),
    )
    return tuple(ranked[:limit])
