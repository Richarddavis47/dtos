"""Canonical arithmetic and small, owned, constraint-preserving Market adjustments.

No parallel prices, provider retrieval, discovery engine or persistent cache.
Only shortlisted balancing proposals invoke the existing bilateral assessment.
"""
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from itertools import combinations
import json
from time import perf_counter

from services import trade_intelligence as trade
from src.core.intelligence import trade_market_balance as market_balance

CONSTRUCTION_BUDGET = 512
EVALUATION_BUDGET = 8
OPTION_LIMIT = 4


def _constraints(payload):
    for field in ('protected_assets', 'excluded_assets'):
        ids = payload.get(field) or []
        if not isinstance(ids, (list, tuple)) or len(ids) > 256 or any(not isinstance(i, str) or not i or len(i) > 256 for i in ids):
            raise trade.TradeInputError('invalid_proposal', 'Use the exact asset controls to set protections and exclusions.')
    for field in ('required_outgoing_asset', 'required_incoming_asset'):
        if payload.get(field) is not None and (not isinstance(payload[field], str) or not payload[field] or len(payload[field]) > 256):
            raise trade.TradeInputError('invalid_proposal', 'Select an exact workflow anchor.')
    return set(payload.get('protected_assets') or []), set(payload.get('excluded_assets') or [])


def market_generation(workspace):
    rows = [(a.asset_id, a.source_roster_id, a.trade_value, a.market_fact, a.pick_market_evidence)
            for pool in workspace['pools'].values() for a in pool]
    return sha256(json.dumps(sorted(rows, key=lambda r: (r[0], r[1])), sort_keys=True,
                            separators=(',', ':'), default=str).encode()).hexdigest()


def market_verdict(sent, received):
    result = market_balance(sent, received)
    difference = result['difference']
    result.update(verdict='UNAVAILABLE' if difference is None else 'APPROXIMATELY_BALANCED' if difference == 0
                  else 'SIDE_A_FAVORED' if difference > 0 else 'SIDE_B_FAVORED',
                  absolute_gap=abs(difference) if difference is not None else None,
                  balance_policy='Equal canonical totals only; no inferred fairness band or probability.',
                  meaning='Which side receives more canonical Market value, not which team benefits strategically.')
    return result


def calculate_trade_market(data, payload, *, workspace=None):
    protected, excluded = _constraints(payload)
    workspace = workspace or trade.build_trade_workspace(data, int(payload.get('active_roster_id') or 0), market_only=True)
    trade.validate_trade_ownership(workspace, payload)
    generation = market_generation(workspace)
    if payload.get('market_generation') and payload['market_generation'] != generation:
        raise trade.TradeInputError('canonical_evidence_changed', 'Market evidence changed. Reload this workspace to compare and balance the current generation.')
    by_id = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    sent = tuple(by_id[i] for i in payload['assets_sent'])
    received = tuple(by_id[i] for i in payload['assets_received'])
    return {'market': market_verdict(sent, received), 'market_generation': generation,
            'assets_sent': [asdict(a) for a in sent], 'assets_received': [asdict(a) for a in received],
            'ownership_valid': True, 'constraint_conflicts': sorted(protected.intersection(payload['assets_sent']) |
                excluded.intersection(payload['assets_sent'] + payload['assets_received'])),
            'provider_requests': 0, 'advanced_analysis_performed': False}


def balance_trade_market(data, payload):
    started = perf_counter()
    boundary = trade._trade_search_boundary(data)
    workspace = trade.build_trade_workspace(data, int(payload.get('active_roster_id') or 0), market_only=True)
    original = calculate_trade_market(data, payload, workspace=workspace)
    base = original['market']
    result = {'workflow': 'calculator_balance', 'original_market': base,
              'market_generation': original['market_generation'], 'results': [], 'near_misses': [],
              'count': 0, 'preview_only': True, 'provider_requests': 0,
              'constraints': {'protected_assets': list(payload.get('protected_assets') or []),
                              'excluded_assets': list(payload.get('excluded_assets') or [])},
              'search_evidence': {'construction_budget': CONSTRUCTION_BUDGET, 'evaluation_budget': EVALUATION_BUDGET,
                                  'constructed': 0, 'evaluated': 0, 'bounded': True}}
    if base['difference'] is None:
        result.update(state='MARKET_EVIDENCE_UNAVAILABLE', quiet_state='Complete pricing is required to balance. Known subtotals are partial; review the unavailable assets.')
        return result
    if base['difference'] == 0:
        result.update(state='ALREADY_BALANCED', quiet_state='Canonical totals are equal. Roster fit and strategy remain separate questions.')
        return result
    protected, excluded = _constraints(payload)
    anchors = {i for i in (payload.get('required_outgoing_asset'), payload.get('required_incoming_asset')) if i}
    sent, received = tuple(payload['assets_sent']), tuple(payload['assets_received'])
    conflicting = protected.intersection(sent) | excluded.intersection(sent + received)
    anchor_missing = {i for i, ids in ((payload.get('required_outgoing_asset'), sent),
                                     (payload.get('required_incoming_asset'), received)) if i and i not in ids}
    if conflicting or anchor_missing:
        blockers = sorted(conflicting | anchor_missing)
        result.update(state='PROTECTED_ASSET_CONFLICT', blocking_asset_ids=blockers,
                      conflict_explanation='The original offer conflicts with an exact protection or required anchor.',
                      smallest_optional_relaxation='Edit the original offer or explicitly remove the named lock; constraints are never relaxed automatically.',
                      quiet_state='Resolve the exact constraint before balancing.')
        return result
    active, partner = int(payload['active_roster_id']), int(payload['partner_roster_id'])
    by_id = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    lower = 0 if base['difference'] > 0 else 1
    sides = (sent, received)
    options = []
    for owner, selected_ids in ((active, sent), (partner, received)):
        eligible = [a for a in workspace['pools'][owner] if a.trade_value is not None and
                    a.asset_id not in set(sent + received) | excluded and (owner != active or a.asset_id not in protected)]
        # Nearby additions and swaps, with a bounded pool large enough to cover
        # player and exact-pick choices. Identity is never a generic round key.
        def distance(a):
            add = abs(a.trade_value - base['absolute_gap'])
            swaps = [abs(abs(a.trade_value - by_id[i].trade_value) - base['absolute_gap']) for i in selected_ids]
            return min([add, *swaps]), a.asset_id
        options.append(sorted(eligible, key=distance)[:32])
    candidates, seen, lock_blockers = [], set(), set()
    def consider(pair, change):
        if result['search_evidence']['constructed'] >= CONSTRUCTION_BUDGET:
            return
        result['search_evidence']['constructed'] += 1
        if not all(pair) or len(set(pair[0] + pair[1])) != len(pair[0] + pair[1]):
            return
        if not anchors.issubset(pair[0] + pair[1]):
            lock_blockers.update(anchors - set(pair[0] + pair[1]))
            return
        key = tuple(tuple(sorted(ids)) for ids in pair)
        if key in seen:
            return
        seen.add(key)
        market = market_verdict(tuple(by_id[i] for i in pair[0]), tuple(by_id[i] for i in pair[1]))
        if market['absolute_gap'] is None or market['absolute_gap'] >= base['absolute_gap']:
            return
        changed = sum(len(set(sides[j]) ^ set(pair[j])) for j in (0, 1))
        candidates.append((market['absolute_gap'], changed, key, change, pair, market))
    for a in options[lower]:
        pair = list(sides)
        pair[lower] = (*pair[lower], a.asset_id)
        consider(pair, 'ADD_PICK' if a.kind == 'pick' else 'ADD_PLAYER')
    for side in (0, 1):
        for i in sides[side]:
            if side == 1 - lower:
                pair = list(sides)
                pair[side] = tuple(k for k in pair[side] if k != i)
                consider(pair, 'REMOVE_ASSET')
            for a in options[side]:
                pair = list(sides)
                pair[side] = tuple(a.asset_id if k == i else k for k in pair[side])
                consider(pair, 'SWAP_PICK' if by_id[i].kind == a.kind == 'pick' else 'SWAP_ASSET')
    for additions in combinations(options[lower][:16], 2):
        pair = list(sides)
        pair[lower] = (*pair[lower], *(a.asset_id for a in additions))
        consider(pair, 'TWO_ASSET_ADDITION')
    # Diagnose a useful locked addition without evaluating, proposing or
    # relaxing it. This retains a specific, optional explanation at the budget.
    for a in workspace['pools'][active if lower == 0 else partner]:
        if a.asset_id in excluded or lower == 0 and a.asset_id in protected:
            if a.trade_value is not None and a.asset_id not in sent + received and abs(a.trade_value - base['absolute_gap']) < base['absolute_gap']:
                lock_blockers.add(a.asset_id)
    candidates.sort(key=lambda c: c[:3])
    # Reserve one shortlist slot for each available meaningful construction
    # type before arithmetic ties consume the limited expensive assessment.
    shortlist = []
    for change in ('ADD_PLAYER', 'ADD_PICK', 'SWAP_ASSET', 'SWAP_PICK', 'REMOVE_ASSET', 'TWO_ASSET_ADDITION'):
        row = next((c for c in candidates if c[3] == change), None)
        if row is not None:
            shortlist.append(row)
    shortlist.extend(c for c in candidates if c not in shortlist)
    if shortlist:
        # Only explicit balancing pays for the existing contextual assessment;
        # the initial calculator and editing stay pure Market arithmetic.
        # Reuse the pinned facts, retaining normal strategy/FOIS semantics.
        workspace = trade.build_trade_workspace(data, active, canonical_market_facts=workspace['canonical_market_facts'])
        if market_generation(workspace) != original['market_generation']:
            raise trade.TradeInputError('canonical_evidence_changed', 'Market evidence changed before assessment. Reload the current generation.')
    reader = trade._search_reader(data, payload, boundary)
    evidence = trade.build_trade_evidence_context(data, by_id.values())
    assessed = []
    for gap, changes, key, change, pair, market in shortlist[:EVALUATION_BUDGET]:
        proposed = {**payload, 'workflow': 'create', 'assets_sent': list(pair[0]), 'assets_received': list(pair[1]), 'package_type': 'Market balancing'}
        row = trade.evaluate_trade_request(data, proposed, workspace=workspace, evidence_context=evidence, projection_reader=reader)
        result['search_evidence']['evaluated'] += 1
        evaluation = row['evaluation']
        qualities = evaluation.get('dimensions', {}).get('package_quality', {})
        poor = any(q.get('assessment') == 'POOR' for q in qualities.values() if isinstance(q, dict))
        capacity = any((q.get('roster_capacity') or {}).get('additional_spots_to_resolve') for q in qualities.values() if isinstance(q, dict))
        row['balance_adjustment'] = {'change': change, 'original': base, 'suggested': market,
                                    'gap_reduction': float(Decimal(str(base['absolute_gap'])) - Decimal(str(gap))),
                                    'reason': 'Narrower canonical Market gap with current ownership and exact constraints preserved.',
                                    'meaning': 'Market adjustment, not a guaranteed better trade or manager acceptance.',
                                    'quality': 'POOR' if poor else 'ROSTER_CAPACITY_ISSUE' if capacity else 'ASSESSED_SEPARATELY'}
        if poor or capacity or not evaluation.get('legal'):
            if len(result['near_misses']) < 3:
                result['near_misses'].append({**row, 'blocker_type': 'PACKAGE_QUALITY' if poor else 'ROSTER_CAPACITY',
                                             'conflict_explanation': 'Arithmetic improves, but package quality or roster capacity blocks promotion.'})
            continue
        assessment = evaluation.get('dimensions', {}).get('counterparty_plausibility', {}).get('assessment')
        caution = evaluation.get('recommendation') not in ('WORTH PURSUING', 'FAIR / OPTIONAL') or assessment not in ('STRONG', 'PLAUSIBLE')
        row['balance_adjustment']['strategic_caution'] = caution
        assessed.append((caution, gap, changes, change, key, row))
    if trade._trade_search_boundary(data) != boundary:
        raise trade.TradeInputError('canonical_evidence_changed', 'Canonical evidence changed during balancing. Reload and compare the current generation.')
    assessed.sort(key=lambda c: c[:5])
    chosen = []
    for row in assessed:
        if len(chosen) < OPTION_LIMIT and (not any(c[3] == row[3] for c in chosen) or len(assessed) <= OPTION_LIMIT):
            chosen.append(row)
    for row in assessed:
        if len(chosen) < OPTION_LIMIT and row not in chosen:
            chosen.append(row)
    result['results'] = [c[-1] for c in chosen]
    result.update(count=len(chosen), state='BALANCING_OPTIONS' if chosen else 'NO_CREDIBLE_BALANCING_OPTION',
                  quiet_state=None if chosen else 'No credible gap-reducing option within this bounded search. Review package quality, exact anchors and owned alternatives.')
    if not chosen and lock_blockers:
        result.update(blocking_asset_ids=sorted(lock_blockers),
                      conflict_explanation='Exact protections or required anchors block nearby Market adjustments.',
                      smallest_optional_relaxation='Only if intended, remove the named exact lock or choose Build My Own for a different objective. No constraint was relaxed.')
    result['search_evidence'].update(total_seconds=perf_counter() - started, projection_weeks_read=len(reader.weeks), reuse=reader.lineup_memo.status())
    return result
