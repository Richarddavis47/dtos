"""Bounded current-offer repair constructions, never pricing or acceptance rules."""
from collections import Counter
from heapq import nsmallest
from itertools import combinations
from math import isfinite

from src.core.trade_intelligence.models import TradeProposal


REPAIR_EVALUATION_BUDGET = 160
REPAIR_OPTION_LIMIT = 3


def market_cost(assets):
    """Compare the full available canonical values without display rounding."""
    values = [a.trade_value for a in assets]
    if any(v is None or not isfinite(v) for v in values):
        return None
    return sum(values)


def repair_family(proposal, assets):
    """Equivalent exact picks stay distinct assets but need not fill every slot."""
    def side(ids):
        return tuple(sorted((a.kind, a.asset_id if a.kind == 'player' else
                             str((a.season, a.round, a.projected_range, a.exact_slot, a.trade_value)))
                            for a in (assets[i] for i in ids)))
    return side(proposal['assets_sent']), side(proposal['assets_received'])


def cheaper_phase(workspace, payload, phase, seen):
    """Try local reductions/substitutions first, then bounded package changes.

    Phase zero orders replacements against the asset being replaced, rather than
    the target price. Later phases diversify at most 18/24 owned assets and inspect
    at most three outgoing assets per package. Only canonical evaluation can
    establish credibility. Every construction rejection has a named reason.
    """
    from src.core.intelligence import trade_pick_identity_errors

    active, partner = payload['active_roster_id'], payload['partner_roster_id']
    assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    sent = tuple(assets[i] for i in payload['assets_sent'])
    received = tuple(assets[i] for i in payload['assets_received'])
    original = frozenset(payload['assets_sent']), frozenset(payload['assets_received'])
    required = set(payload.get('required_outgoing_assets') or ())
    protected, excluded = set(payload.get('protected_assets') or ()), set(payload.get('excluded_assets') or ())
    current_cost, return_cost = market_cost(sent), market_cost(received)
    reasons, counts, missing = Counter(), Counter(), set()
    owned = tuple(workspace['pools'][active])

    def constructions():
        if phase == 0:
            for index, old in enumerate(sent):
                # Attempted removals are diagnosed, including required anchors.
                yield sent[:index] + sent[index + 1:], 'Cheaper reduction'
                replacements = sorted((a for a in owned if a.asset_id not in original[0]
                                       and (a.trade_value is None or a.trade_value < old.trade_value)),
                    key=lambda a: (a.kind != old.kind, a.position != old.position,
                                   a.trade_value is None, -(a.trade_value or 0), a.asset_id))[:24]
                for asset in replacements:
                    yield sent[:index] + (asset,) + sent[index + 1:], 'Cheaper substitution'
        else:
            groups = {}
            for asset in owned:
                if asset.trade_value is None or asset.trade_value < current_cost:
                    groups.setdefault((asset.kind, asset.position or 'PICK'), []).append(asset)
            for rows in groups.values():
                rows.sort(key=lambda a: (a.asset_id not in original[0], a.trade_value is None,
                                        abs((a.trade_value or 0) - return_cost), a.asset_id))
            pool = [assets[i] for i in sorted(required)]
            while len(pool) < (18 if phase == 1 else 24) and any(groups.values()):
                for group in sorted(groups):
                    if groups[group] and len(pool) < (18 if phase == 1 else 24):
                        a = groups[group].pop(0)
                        if a not in pool:
                            pool.append(a)
            anchors = tuple(a for a in pool if a.asset_id in required)
            extras = tuple(a for a in pool if a.asset_id not in required)
            for size in range(max(1, len(anchors)), 3 if phase == 1 else 4):
                for additions in combinations(extras, size - len(anchors)):
                    yield anchors + additions, 'Cheaper package change'

    proposals, phase_seen = [], set(seen)
    for outgoing, label in constructions():
        counts['constructions_generated'] += 1
        ids = tuple(a.asset_id for a in outgoing)
        identity = frozenset(ids), original[1]
        cost = market_cost(outgoing)
        if identity in phase_seen:
            reason = 'DUPLICATE_CONSTRUCTION'
        elif cost is not None and current_cost is not None and cost < current_cost:
            counts['cheaper_by_price_candidates'] += 1
            reason = None
        else:
            reason = 'MISSING_MARKET_PRICE' if cost is None else 'EQUAL_OR_HIGHER_OUTGOING_COST'
        if reason is None:
            if not required.issubset(ids):
                reason = 'REQUIRED_SHOP_ANCHOR_MISSING'
            elif not ids:
                reason = 'EMPTY_OUTGOING_PACKAGE'
            elif len(set(ids)) != len(ids) or set(ids) & original[1]:
                reason = 'DUPLICATE_ASSET'
            elif protected.intersection(ids) or excluded.intersection((*ids, *original[1])):
                reason = 'EXACT_LOCK_CONFLICT'
            elif any(a.source_roster_id != active for a in outgoing):
                reason = 'ASSET_NOT_OWNED'
            elif any(trade_pick_identity_errors(a) for a in outgoing):
                reason = 'INVALID_PICK_IDENTITY'
        if reason:
            reasons[reason] += 1
            if reason == 'MISSING_MARKET_PRICE':
                missing.update(a.asset_id for a in outgoing if market_cost((a,)) is None)
            continue
        phase_seen.add(identity)
        proposals.append(TradeProposal(active, partner, outgoing, received, label))

    def order(p):
        cost = market_cost(p.assets_sent)
        return (len({a.asset_id for a in p.assets_sent} ^ original[0]),
                abs(cost - return_cost), cost, tuple(sorted(a.asset_id for a in p.assets_sent)))
    selected = nsmallest(REPAIR_EVALUATION_BUDGET, proposals, key=order)
    seen.update((frozenset(a.asset_id for a in p.assets_sent), original[1]) for p in selected)
    reasons['PHASE_CONSTRUCTION_LIMIT'] += len(proposals) - len(selected)
    return tuple(selected), {
        'search_phase': phase, 'objective': 'LOWER_CANONICAL_OUTGOING_COST',
        'cheap_package_pairs_inspected': counts['constructions_generated'],
        'constructed_candidates': len(selected),
        'cheaper_by_price_candidates': counts['cheaper_by_price_candidates'],
        'prune_reason_counts': {k: v for k, v in reasons.items() if v},
        'missing_asset_ids': sorted(missing),
        'ordering': 'current-offer edits then bounded package changes; strictly cheaper before evaluation',
        'exhaustive': False,
    }


def no_cheaper_reason(funnel, diagnostics):
    """An empty bounded repair says what was actually tried and what blocked it."""
    if diagnostics['repair_stop_reason'] == 'EVALUATION_BUDGET_EXHAUSTED':
        return f"No credible cheaper option found within the {funnel.budget}-evaluation repair budget. Further constructions remain unassessed."
    reasons = diagnostics['prune_reason_counts']
    messages = []
    if reasons.get('EXACT_LOCK_CONFLICT'):
        messages.append('Some cheaper constructions violate your exact protected/excluded asset locks; no lock was relaxed.')
    if reasons.get('MISSING_MARKET_PRICE'):
        messages.append('Required canonical Market prices are missing for named candidate assets; their cost cannot be compared.')
    if funnel.counts['hard_invalid']:
        messages.append('Evaluated cheaper constructions fail ownership, identity or roster/capacity legality.')
    if funnel.counts['missing_evidence']:
        messages.append('Evaluated cheaper constructions lack required projection or other evidence.')
    if funnel.counts['counterparty_limited']:
        messages.append('Evaluated cheaper constructions do not establish a meaningful counterparty benefit after their costs.')
    if funnel.counts['strategically_rejected']:
        messages.append('Evaluated cheaper constructions fail the selected strategy or bilateral materiality assessment.')
    if funnel.counts['filtered']:
        messages.append('Evaluated cheaper constructions fail an additional requested adjustment constraint.')
    if not messages:
        messages.append('No lower-cost construction preserves the required target/Shop anchor within the bounded owned-asset pool.')
    codes = dict(funnel.reasons)
    return ' '.join(messages) + (f" Evaluated blockers: {', '.join(sorted(codes))}." if codes else '')
