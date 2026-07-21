"""Bounded realistic package generation."""
from __future__ import annotations

from itertools import combinations

from src.core.trade_intelligence.models import TradeAsset, TradeProposal


PACKAGE_SHAPES = (
    ("1-for-1", 1, 1, "player", "player"),
    ("2-for-1", 2, 1, None, None),
    ("3-for-2", 3, 2, None, None),
    ("Player + Pick", 2, 1, "mixed", None),
    ("Pick Package", 2, 1, "pick", None),
    ("Multi-Asset", 2, 2, None, None),
)


def _value(assets: tuple[TradeAsset, ...]) -> float:
    return sum((asset.dynasty_value + asset.team_fit_value) / 2 for asset in assets)


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
        for sent in combinations(outgoing, sent_count):
            if not _matches(sent, sent_kind):
                continue
            for received in combinations(incoming, received_count):
                if not _matches(received, received_kind):
                    continue
                sent_value, received_value = _value(sent), _value(received)
                if not sent_value or not received_value:
                    continue
                ratio = received_value / sent_value
                if 0.80 <= ratio <= 1.25:
                    candidates.append((abs(received_value - sent_value), -sum(item.team_fit_value for item in received), sent, received))
        if candidates:
            _, _, sent, received = min(candidates, key=lambda item: (item[0], item[1], tuple(asset.asset_id for asset in item[2]), tuple(asset.asset_id for asset in item[3])))
            proposals.append(TradeProposal(active_roster_id, partner_roster_id, sent, received, label))
    return tuple(proposals)
