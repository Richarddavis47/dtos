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
    pool = tuple(asset for asset in pool if asset.trade_value is not None)
    # Missing fit has no preference; canonical identity breaks ties, not a substitute value.
    players = sorted((asset for asset in pool if asset.kind == "player"), key=lambda item: (item.team_fit_value is None, -item.team_fit_value if item.team_fit_value is not None else 0, item.asset_id))[:8]
    # This shortlist answers acquisition-package coverage, not intrinsic quality.
    picks = sorted((asset for asset in pool if asset.kind == "pick"), key=lambda item: (-item.trade_value, item.asset_id))[:4]
    return tuple(players + picks)


def _shortlist_with_required(pool: tuple[TradeAsset, ...], required_asset_id: str | None) -> tuple[TradeAsset, ...]:
    rows = list(_shortlist(pool))
    required = next((asset for asset in pool if asset.asset_id == required_asset_id), None)
    if required is not None and required.trade_value is not None and all(asset.asset_id != required.asset_id for asset in rows):
        rows.append(required)
    return tuple(rows)


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
    *,
    required_sent_asset_id: str | None = None,
    required_received_asset_id: str | None = None,
    construction_only: bool = False,
    search_diagnostics: dict | None = None,
    return_preference: dict | None = None,
) -> tuple[TradeProposal, ...]:
    if construction_only:
        if required_sent_asset_id:
            # Search the other side's bounded return pool around the owned
            # shopped asset, then restore the canonical user perspective.
            mirrored = _canonical_candidates(partner_roster_id, active_roster_id, incoming_pool, outgoing_pool,
                                             required_sent_asset_id, search_diagnostics, return_preference)
            if search_diagnostics is not None:
                for field in ('shortlisted_asset_ids', 'shortlist_excluded_asset_ids'):
                    if field in search_diagnostics:
                        row = search_diagnostics[field]
                        row['sent'], row['received'] = row['received'], row['sent']
                if 'shortlisted_outgoing' in search_diagnostics:
                    search_diagnostics['shortlisted_outgoing'], search_diagnostics['shortlisted_incoming'] = (
                        search_diagnostics['shortlisted_incoming'], search_diagnostics['shortlisted_outgoing'])
                for boundary in search_diagnostics.get('package_boundaries', []):
                    for row in boundary['nearest_constructions']:
                        row['assets_sent'], row['assets_received'] = row['assets_received'], row['assets_sent']
            return tuple(TradeProposal(active_roster_id, partner_roster_id, p.assets_received, p.assets_sent,
                                       'Shop return: ' + p.package_type) for p in mirrored)
        return _canonical_candidates(active_roster_id, partner_roster_id, outgoing_pool, incoming_pool,
                                     required_received_asset_id, search_diagnostics)
    outgoing = _shortlist_with_required(outgoing_pool, required_sent_asset_id)
    incoming = _shortlist_with_required(incoming_pool, required_received_asset_id)
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
                superflex = any(asset.position == "QB" for asset in (*sent, *received))
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
                            -sum(item.team_fit_value for item in received) if all(item.team_fit_value is not None for item in received) else 0,
                            sent,
                            received,
                        )
                    )
        if candidates:
            _, _, sent, received = min(candidates, key=lambda item: (item[0], item[1], tuple(asset.asset_id for asset in item[2]), tuple(asset.asset_id for asset in item[3])))
            proposals.append(TradeProposal(active_roster_id, partner_roster_id, sent, received, label))
    return tuple(proposals)


def _diverse_shortlist(pool, target, limit=12):
    """Round-robin asset type/position groups; price orders within groups only."""
    groups = {}
    for asset in pool:
        if asset.trade_value is not None:
            key = (asset.kind, asset.position or 'PICK')
            groups.setdefault(key, []).append(asset)
    for rows in groups.values():
        rows.sort(key=lambda a: (abs(a.trade_value - target.trade_value), a.asset_id))
    selected = []
    while len(selected) < limit and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(selected) < limit:
                selected.append(groups[key].pop(0))
    return tuple(selected)


def _canonical_candidates(active_id, partner_id, outgoing_pool, incoming_pool, target_id, diagnostics=None, return_preference=None):
    """Bounded Trade For search ordering, never a valuation/acceptance decision.

    Raw acquisition-price distance chooses one construction per existing shape.
    No price-ratio rejection, universal discount, fit scalar or legacy guardrail.
    The target is constrained before selection, not filtered out afterward.
    """
    target = next((a for a in incoming_pool if a.asset_id == target_id), None)
    if target is None or target.trade_value is None:
        if diagnostics is not None:
            diagnostics.update(unavailable_target_price=True, constructed_candidates=0)
        return ()
    outgoing = _diverse_shortlist(outgoing_pool, target)
    incoming = (target, *_diverse_shortlist(tuple(a for a in incoming_pool if a.asset_id != target_id), target, 11))
    proposals, seen = [], set()
    pair_count = 0
    boundaries = []
    for label, sent_count, received_count, sent_kind, received_kind in PACKAGE_SHAPES:
        candidates = ((sent, received) for sent in combinations(outgoing, sent_count)
                      if _matches(sent, sent_kind)
                      if not return_preference or return_preference['name'] != 'draft_capital' or any(a.kind == 'pick' for a in sent)
                      if not return_preference or return_preference['name'] != 'position_need' or any(a.position == return_preference['position'] for a in sent)
                      for received in combinations(incoming, received_count)
                      if _matches(received, received_kind) and any(a.asset_id == target_id for a in received))
        chosen, best_key = None, None
        nearest = []
        shape_count = 0
        for sent, received in candidates:
            pair_count += 1
            shape_count += 1
            key = (abs(sum(a.trade_value for a in sent) - sum(a.trade_value for a in received)),
                   tuple(a.asset_id for a in sent), tuple(a.asset_id for a in received))
            if diagnostics is not None:
                nearest.append(key)
                nearest.sort()
                del nearest[3:]
            if best_key is None or key < best_key:
                chosen, best_key = (sent, received), key
        if diagnostics is not None:
            boundaries.append({'shape': label, 'candidate_count': shape_count,
                               'nearest_constructions': [
                                   {'raw_market_distance': key[0], 'assets_sent': list(key[1]),
                                    'assets_received': list(key[2]),
                                    'selection': 'selected_before_exact_deduplication' if index == 0 else 'pruned_search_budget',
                                    'quality': 'not_assessed'}
                                   for index, key in enumerate(nearest)]})
        if chosen is not None:
            sent, received = chosen
            identity = (tuple(sorted(a.asset_id for a in sent)), tuple(sorted(a.asset_id for a in received)))
            if identity not in seen:
                seen.add(identity)
                proposals.append(TradeProposal(active_id, partner_id, sent, received, label))
    if diagnostics is not None:
        diagnostics.update(shortlisted_outgoing=len(outgoing), shortlisted_incoming=len(incoming),
                           cheap_package_pairs_inspected=pair_count, constructed_candidates=len(proposals),
                           shortlisted_asset_ids={'sent': [a.asset_id for a in outgoing], 'received': [a.asset_id for a in incoming]},
                           shortlist_excluded_asset_ids={
                               'sent': [a.asset_id for a in outgoing_pool if a not in outgoing],
                               'received': [a.asset_id for a in incoming_pool if a not in incoming]},
                           package_boundaries=boundaries,
                           pruning='position/type diversification then raw Market proximity; not a recommendation',
                           exhaustive=False)
    return tuple(proposals)
