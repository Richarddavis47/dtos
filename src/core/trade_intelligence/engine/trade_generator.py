"""Bounded realistic package generation."""
from __future__ import annotations

from itertools import combinations

from src.core.trade_intelligence.models import TradeAsset, TradeProposal
from src.core.valuation import (
    PackageValue,
    adjusted_package_value,
    evaluate_trade_guardrails,
)


PACKAGE_SHAPES = (
    ("1-for-1", 1, 1, "player", "player"),
    ("2-for-1", 2, 1, None, None),
    ("3-for-2", 3, 2, None, None),
    ("Player + Pick", 2, 1, "mixed", None),
    ("Pick Package", 2, 1, "pick", None),
    ("Multi-Asset", 2, 2, None, None),
)


def _value(assets: tuple[TradeAsset, ...]) -> PackageValue:
    return adjusted_package_value(assets)


def _matches(assets: tuple[TradeAsset, ...], kind: str | None) -> bool:
    if kind is None:
        return True
    if kind == "mixed":
        return {asset.kind for asset in assets} == {"player", "pick"}
    return all(asset.kind == kind for asset in assets)


def _shortlist(pool: tuple[TradeAsset, ...]) -> tuple[TradeAsset, ...]:
    players = sorted((asset for asset in pool if asset.kind == "player"), key=lambda item: (-item.team_fit_value, item.asset_id))[:8]
    picks = sorted((asset for asset in pool if asset.kind == "pick"), key=lambda item: (-item.dynasty_value, item.asset_id))[:4]
    return tuple(players + picks)


def _valued_combinations(
    pool: tuple[TradeAsset, ...],
    count: int,
    kind: str | None,
) -> tuple[tuple[tuple[TradeAsset, ...], PackageValue], ...]:
    """Calculate each eligible package value once per proposal shape."""
    return tuple(
        (assets, value)
        for assets in combinations(pool, count)
        if _matches(assets, kind)
        if (value := _value(assets)).adjusted_value
    )


def generate_proposals(
    active_roster_id: int,
    partner_roster_id: int,
    outgoing_pool: tuple[TradeAsset, ...],
    incoming_pool: tuple[TradeAsset, ...],
) -> tuple[TradeProposal, ...]:
    outgoing = _shortlist(outgoing_pool)
    incoming = _shortlist(incoming_pool)
    proposals = []
    for label, sent_count, received_count, sent_kind, received_kind in PACKAGE_SHAPES:
        candidates = []
        sent_packages = _valued_combinations(outgoing, sent_count, sent_kind)
        received_packages = _valued_combinations(
            incoming,
            received_count,
            received_kind,
        )
        for sent, sent_value in sent_packages:
            for received, received_value in received_packages:
                ratio = received_value.adjusted_value / sent_value.adjusted_value
                if not 0.80 <= ratio <= 1.25:
                    continue
                superflex = any(
                    asset.position == "QB"
                    for asset in received
                )
                guardrail = evaluate_trade_guardrails(
                    sent,
                    received,
                    superflex=superflex,
                    confidence=min(
                        *(asset.confidence_score for asset in (*sent, *received)),
                        75,
                    ),
                    offered_package=sent_value,
                    requested_package=received_value,
                )
                if guardrail.recommendation_status == "accepted":
                    candidates.append(
                        (
                            abs(
                                received_value.adjusted_value
                                - sent_value.adjusted_value
                            ),
                            -sum(item.team_fit_value for item in received),
                            sent,
                            received,
                        )
                    )
        if candidates:
            _, _, sent, received = min(candidates, key=lambda item: (item[0], item[1], tuple(asset.asset_id for asset in item[2]), tuple(asset.asset_id for asset in item[3])))
            proposals.append(TradeProposal(active_roster_id, partner_roster_id, sent, received, label))
    return tuple(proposals)
