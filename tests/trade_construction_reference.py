"""Frozen v1.21.11 construction loop for exact performance equivalence."""
from itertools import combinations
from src.core.trade_intelligence.models import TradeProposal
from src.core.trade_intelligence.engine.trade_generator import PACKAGE_SHAPES, _diverse_shortlist, _matches


def _canonical_candidates(active_id, partner_id, outgoing_pool, incoming_pool, target_id, diagnostics=None, return_preference=None, search_phase=0):
    """Bounded Trade For search ordering, never a valuation/acceptance decision.

    Raw acquisition-price distance orders a bounded shortlist per shape and phase.
    No price-ratio rejection, universal discount, fit scalar or legacy guardrail.
    The target is constrained before selection, not filtered out afterward.
    """
    target = next((a for a in incoming_pool if a.asset_id == target_id), None)
    if target is None or target.trade_value is None:
        if diagnostics is not None:
            diagnostics.update(unavailable_target_price=True, constructed_candidates=0)
        return ()
    pool_limit = (12, 18, 24)[min(search_phase, 2)]
    per_shape = (1, 4, 8)[min(search_phase, 2)]
    outgoing = _diverse_shortlist(outgoing_pool, target, pool_limit)
    incoming = (target, *_diverse_shortlist(tuple(a for a in incoming_pool if a.asset_id != target_id), target, pool_limit - 1))
    proposals, seen = [], set()
    pair_count = 0
    boundaries = []
    # Keep the six-shape budget, but allow a single pick to buy a player and
    # require a player return when shopping a pick (via the mirrored path).
    # Exact asset IDs and prices still choose the construction; only the shared
    # evaluator decides whether the capital sacrifice fits either manager.
    shapes = (("1-for-1", 1, 1, 'player' if target.kind == 'pick' else None, target.kind), *PACKAGE_SHAPES[1:])
    if search_phase:
        shapes += (('1-for-2', 1, 2, None, None), ('3-for-1', 3, 1, None, None))
    for label, sent_count, received_count, sent_kind, received_kind in shapes:
        candidates = ((sent, received) for sent in combinations(outgoing, sent_count)
                      if _matches(sent, sent_kind)
                      if not return_preference or return_preference['name'] != 'draft_capital' or any(a.kind == 'pick' for a in sent)
                      if not return_preference or return_preference['name'] != 'position_need' or any(a.position == return_preference['position'] for a in sent)
                      for received in combinations(incoming, received_count)
                      if _matches(received, received_kind) and any(a.asset_id == target_id for a in received))
        best = []
        nearest = []
        shape_count = 0
        for sent, received in candidates:
            pair_count += 1
            shape_count += 1
            key = (abs(sum(a.trade_value for a in sent) - sum(a.trade_value for a in received)),
                   tuple(a.asset_id for a in sent), tuple(a.asset_id for a in received))
            best.append((key, sent, received))
            best.sort(key=lambda row: row[0])
            del best[per_shape:]
            if diagnostics is not None:
                nearest.append(key)
                nearest.sort()
                del nearest[3:]
        if diagnostics is not None:
            boundaries.append({'shape': label, 'candidate_count': shape_count,
                               'nearest_constructions': [
                                   {'raw_market_distance': key[0], 'assets_sent': list(key[1]),
                                    'assets_received': list(key[2]),
                                    'selection': 'selected_before_exact_deduplication' if index < per_shape else 'pruned_search_budget',
                                    'quality': 'not_assessed'}
                                   for index, key in enumerate(nearest)]})
        for _, sent, received in best:
            identity = (tuple(sorted(a.asset_id for a in sent)), tuple(sorted(a.asset_id for a in received)))
            if identity not in seen:
                seen.add(identity)
                proposals.append(TradeProposal(active_id, partner_id, sent, received, label))
    if diagnostics is not None:
        diagnostics.update(search_phase=search_phase, per_shape_limit=per_shape, shape_count=len(shapes), shortlisted_outgoing=len(outgoing), shortlisted_incoming=len(incoming),
                           cheap_package_pairs_inspected=pair_count, constructed_candidates=len(proposals),
                           shortlisted_asset_ids={'sent': [a.asset_id for a in outgoing], 'received': [a.asset_id for a in incoming]},
                           shortlist_excluded_asset_ids={
                               'sent': [a.asset_id for a in outgoing_pool if a not in outgoing],
                               'received': [a.asset_id for a in incoming_pool if a not in incoming]},
                           package_boundaries=boundaries,
                           pruning='position/type diversification then raw Market proximity; not a recommendation',
                           exhaustive=False)
    return tuple(proposals)
