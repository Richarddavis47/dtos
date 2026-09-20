"""Bounded opportunity discovery and presentation over canonical Trade evidence.

Discovery identifies possible legal-slot improvements, never trade quality.
Only the shared evaluator may assess the resulting complete bilateral package.
No durable state, provider fetch, valuation or manager-intent inference here.
"""
from collections import defaultdict
from hashlib import sha256
import json
from time import perf_counter

from src.core.intelligence.team_strength import compatible_profile
from src.core.intelligence import lineup_slot_eligible as _eligible, TradeProposal, generate_proposals

METHOD = 'recommended-opportunities-v1'
FILTERS = {'all', 'win_now', 'value', 'roster_fit', 'future', 'sell_high'}


def session_constraints(payload):
    selected = payload.get('recommendation_filter') or 'all'
    if not isinstance(selected, str) or selected not in FILTERS:
        raise ValueError('Unsupported Recommended Trades filter.')
    excluded = payload.get('excluded_recommendation_families') or []
    if (not isinstance(excluded, list) or len(excluded) > 64
            or any(not isinstance(value, str) or len(value) != 64
                   or any(c not in '0123456789abcdef' for c in value) for value in excluded)):
        raise ValueError('Recommendation refresh requires at most 64 valid session family identities.')
    return selected, set(excluded)


def discover(data, workspace, reader, protected, excluded, *, max_theses=6, excluded_families=()):
    """Complementary supported slot opportunities; six theses, not all packages.

    A potential incoming player must beat an eligible supported optimal slot in
    at least one published week. Pair with an owned outgoing player independently
    useful to the other side. This is NOT a net post-trade impact or surplus
    verdict: removal, flex reassignment, depth/capacity and all horizons are left
    to the shared evaluator. No absolute roster-count threshold participates.
    """
    started = perf_counter()
    profile = compatible_profile(data, reader.snapshot())
    active = workspace['active_roster_id']
    partners = sorted(rid for rid in workspace['pools'] if rid != active)
    report = {'methodology': METHOD, 'potential_counterparties': len(partners),
              'discovered_counterparties': 0, 'theses': [], 'omitted_theses': [],
              'limitations': [], 'durable_writes': 0}
    if profile is None:
        report['limitations'] = ['COMPATIBLE_PREPARED_LINEUPS_UNAVAILABLE']
        report['discovery_seconds'] = perf_counter() - started
        return report
    weeks = sorted({int(w) for row in profile['teams'].values() for w in row['weekly']})
    snapshots = {w: reader.week_snapshot(w, generation_snapshot=reader.snapshot()) for w in weeks}
    for week, snapshot in snapshots.items():
        if snapshot and (str(snapshot.get('league_id')) != profile['league_id']
                         or snapshot.get('horizon_generation') != profile['projection_generation']
                         or snapshot.get('scoring_profile_id') != profile['scoring_profile_id']
                         or snapshot.get('season') != profile['season'] or snapshot.get('week') != week):
            raise ValueError('Recommendation projection evidence scope changed.')
    def opportunity(asset, recipient, donor):
        if asset.kind != 'player' or asset.trade_value is None or asset.asset_id in excluded:
            return None
        pid = asset.asset_id.removeprefix('player:')
        observations = []
        for week in weeks:
            receiver_week = recipient['weekly'].get(week, recipient['weekly'].get(str(week), {}))
            donor_week = donor['weekly'].get(week, donor['weekly'].get(str(week), {}))
            projection = ((snapshots[week] or {}).get('players') or {}).get(pid) or {}
            points = projection.get('canonical_projection')
            if points is None or pid in donor_week.get('known_bye_player_ids', []):
                continue
            # Partial recipient evidence cannot establish a complete slot baseline.
            if not receiver_week.get('available'):
                continue
            entries = receiver_week.get('optimal', {}).get('entries') or []
            eligible = [e for e in entries if _eligible(asset.position or '', e['slot'])]
            if not eligible:
                continue
            baseline = min(eligible, key=lambda e: (e['projected_points'], e['slot'], e['asset_id']))
            if points <= baseline['projected_points']:
                continue
            observations.append({'week': week, 'slot': baseline['slot'],
                'baseline_player_id': baseline['asset_id'], 'baseline_projection': baseline['projected_points'],
                'incoming_projection': points, 'projection_snapshot_id': (snapshots[week] or {}).get('projection_snapshot_id'),
                'donor_optimal_starter': pid in {e['asset_id'] for e in donor_week.get('optimal', {}).get('entries', [])}})
        return {'asset_id': asset.asset_id, 'position': asset.position, 'weeks': observations} if observations else None
    by_partner = {}
    for rid in partners:
        own, other = profile['teams'].get(str(active)), profile['teams'].get(str(rid))
        if not own or not other:
            continue
        incoming = [row for a in workspace['pools'][rid] if (row := opportunity(a, own, other))]
        outgoing = [row for a in workspace['pools'][active] if a.asset_id not in protected
                    and (row := opportunity(a, other, own))]
        def order(row):
            return (-len(row['weeks']), sum(w['donor_optimal_starter'] for w in row['weeks']), row['asset_id'])
        # Position-diverse evidence shortlists, not dynasty/quality ranks.
        def diverse(rows):
            groups = defaultdict(list)
            for row in sorted(rows, key=order):
                groups[row['position']].append(row)
            return [rows[0] for _, rows in sorted(groups.items())]
        pairs = [{'partner_id': rid, 'send': send, 'receive': receive,
                  'type': 'COMPLEMENTARY_SUPPORTED_SLOT_OPPORTUNITY',
                  'league_id': profile['league_id'], 'season': profile['season'],
                  'current_week': profile['current_week'], 'generation': profile['semantic_generation'],
                  'projection_generation': profile['projection_generation'],
                  'assessment': 'discovery_only_not_net_trade_impact'}
                 for send in diverse(outgoing) for receive in diverse(incoming)]
        pairs.sort(key=lambda p: (order(p['receive']), order(p['send'])))
        if pairs:
            by_partner[rid] = pairs[:2]
    report['discovered_counterparties'] = len(by_partner)
    # Round-robin opportunities across counterparties avoids filling the budget
    # with variations from the first franchise. Deterministic, never randomized.
    all_theses = [rows[index] for index in range(2) for _, rows in sorted(by_partner.items()) if index < len(rows)]
    assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    eligible_theses = []
    for thesis in all_theses:
        family = family_identity(profile['league_id'], {'proposal': {'active_roster_id': active,
            'partner_roster_id': thesis['partner_id'], 'assets_sent': [thesis['send']['asset_id']],
            'assets_received': [thesis['receive']['asset_id']]}}, assets)
        thesis['family_id'] = family
        if family not in excluded_families:
            eligible_theses.append(thesis)
    report.update(theses=eligible_theses[:max_theses], omitted_theses=eligible_theses[max_theses:],
                  session_excluded_theses=len(all_theses) - len(eligible_theses),
                  candidate_theses=len(all_theses), generation=profile['semantic_generation'],
                  discovery_seconds=perf_counter() - started)
    report['limitations'] = ['BOUNDED_PLAYER_LINEUP_DISCOVERY', 'NOT_EXHAUSTIVE_DYNASTY_OR_PICK_OPPORTUNITY_SEARCH']
    return report


def construct(workspace, thesis, protected, excluded):
    active, partner = workspace['active_roster_id'], thesis['partner_id']
    outgoing = tuple(a for a in workspace['pools'][active] if a.asset_id not in protected | excluded)
    incoming = tuple(a for a in workspace['pools'][partner] if a.asset_id not in excluded)
    sent = next(a for a in outgoing if a.asset_id == thesis['send']['asset_id'])
    received = next(a for a in incoming if a.asset_id == thesis['receive']['asset_id'])
    rows = [TradeProposal(active, partner, (sent,), (received,), 'Complementary player exchange')]
    candidates = generate_proposals(active, partner, outgoing, incoming,
        required_received_asset_id=received.asset_id, construction_only=True)
    seen = {(tuple(a.asset_id for a in rows[0].assets_sent), tuple(a.asset_id for a in rows[0].assets_received))}
    for candidate in candidates:
        key = (tuple(a.asset_id for a in candidate.assets_sent), tuple(a.asset_id for a in candidate.assets_received))
        if key in seen or sent.asset_id not in key[0]:
            continue
        seen.add(key)
        rows.append(candidate)
        if len(rows) == 3:
            break
    return rows


def family_identity(league_id, row, assets):
    """Ignore nominal pick sweeteners for a player thesis, not actual ownership."""
    p = row['proposal']
    def signature(ids):
        players = sorted(i for i in ids if assets[i].kind == 'player')
        return players or sorted((str(assets[i].season), str(assets[i].round),
                                  str(assets[i].projected_range), str(assets[i].exact_slot)) for i in ids)
    return sha256(json.dumps([str(league_id), p['active_roster_id'], p['partner_roster_id'],
                             signature(p['assets_sent']), signature(p['assets_received'])], sort_keys=True).encode()).hexdigest()


def surface_evidence(row):
    """State-based reasons from shared impacts. No invented historical movement."""
    evaluation = row['evaluation']
    impact = evaluation.get('multi_horizon_impact') or {}
    dimensions = evaluation.get('dimensions') or {}
    catalysts, tags, stable = [], [], []
    for side in ('active', 'partner'):
        strategy = (dimensions.get('strategic_fit') or {}).get(side) or {}
        for name, h in (strategy.get('horizons') or {}).items():
            if (h.get('availability') != 'complete' or h.get('delta') is None or h['delta'] <= 0
                    or not impact.get('team_strength_generation') or not h.get('weeks_requested')):
                continue
            reason = {'type': 'SUPPORTED_LINEUP_OPPORTUNITY', 'side': side, 'horizon': name,
                'source_concept': 'pre_trade_optimal_vs_post_trade_optimal',
                'delta': h['delta'], 'weeks': h.get('weeks_requested'),
                'generation': impact.get('team_strength_generation'),
                'confidence': 'supported_projection_evidence_not_outcome_probability',
                'availability': 'supported', 'temporal_claim': 'current_state_not_historical_movement',
                'limitation': 'Conditional on this hypothetical exchange; not urgency or manager intent.'}
            stable.append(reason)
            if name == 'playoff_window':
                catalysts.append(dict(reason, type='SUPPORTED_PLAYOFF_WINDOW_FIT'))
            if side == 'active' and 'ROSTER CONSTRUCTION' not in tags:
                tags.append('ROSTER CONSTRUCTION')
            window = strategy.get('competitive_window') or {}
            if (side == 'active' and name in ('current_week', 'next_n')
                    and window.get('generation') == impact.get('team_strength_generation')
                    and window.get('classification') in ('Elite Contender', 'Contender', 'Playoff Team')
                    and 'WIN-NOW OPPORTUNITY' not in tags):
                tags.append('WIN-NOW OPPORTUNITY')
                catalysts.append(dict(reason, type='CURRENT_COMPETITIVE_WINDOW_ALIGNMENT'))
        # A documented near-term bye plus an improved supported legal lineup is
        # timing context. Missing projections alone never imply a bye.
        near = (strategy.get('horizons') or {}).get('next_n') or {}
        for week, weekly in ((impact.get('sides') or {}).get(side, {}).get('weekly') or {}).items():
            pre = weekly.get('pre') or {}
            if (int(week) not in near.get('weeks_requested', [])
                    or not pre.get('known_bye_player_ids') or weekly.get('delta') is None
                    or weekly['delta'] <= 0 or not impact.get('team_strength_generation')):
                continue
            catalysts.append({'type': 'UPCOMING_BYE_LINEUP_FIT', 'side': side, 'horizon': 'next_n',
                'delta': weekly['delta'], 'weeks': [int(week)],
                'known_bye_player_ids': pre['known_bye_player_ids'],
                'generation': impact['team_strength_generation'], 'availability': 'supported',
                'source_concept': 'canonical_bye_and_supported_legal_lineup_comparison',
                'temporal_claim': 'known_calendar_context_not_projection_movement',
                'limitation': 'Whole-lineup effect; not attributed solely to a bye or an injury prediction.'})
    if {c['side'] for c in stable} == {'active', 'partner'}:
        tags.append('NATURAL TRADE PARTNER')
    market = evaluation.get('market_evidence') or {}
    price_edge = None
    if market.get('availability') == 'full' and market.get('difference') is not None and market['difference'] > 0:
        tags.append('VALUE OPPORTUNITY')
        price_edge = {'source_concept': 'canonical_external_acquisition_price_difference',
                      'difference': market['difference'], 'meaning': 'Market price edge, not an intrinsic bargain or trend'}
    return {'reason_tags': tags, 'stable_opportunity_reasons': stable,
        'unsupported_tags': {'FUTURE VALUE': 'No independently supported long-term utility conclusion.',
                             'SELL-HIGH OPPORTUNITY': 'No comparable current Market movement plus supported sale rationale.'},
        'market_price_edge': price_edge, 'why_now': {'availability': 'supported_current_state' if catalysts else 'unavailable',
        'catalysts': catalysts, 'historical_movement': None, 'urgency': None,
        'limitations': ['NO_COMPARABLE_CHANGE_CATALYST_ESTABLISHED']}}


def rank(rows):
    def order(row):
        e = row['evaluation']
        d = e.get('dimensions') or {}
        horizons = ((d.get('strategic_fit') or {}).get('active') or {}).get('horizons') or {}
        return ({'SMASH ACCEPT': 0, 'WORTH PURSUING': 1, 'FAIR / OPTIONAL': 2}.get(e.get('recommendation'), 3),
                {'STRONG': 0, 'PLAUSIBLE': 1}.get((d.get('counterparty_plausibility') or {}).get('assessment'), 2),
                {'HIGH': 0, 'MEDIUM': 1}.get((d.get('confidence') or {}).get('assessment'), 2),
                tuple((horizons.get(n, {}).get('delta') is None, -(horizons.get(n, {}).get('delta') or 0))
                      for n in ('current_week', 'next_n', 'rest_of_regular_season', 'playoff_window')),
                row['family_id'], e['provenance']['evaluation_id'])
    return sorted(rows, key=order)
