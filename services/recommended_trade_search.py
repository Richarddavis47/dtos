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

METHOD = 'recommended-opportunities-v4-roster-admission'
FILTERS = {'all', 'win_now', 'value', 'roster_fit', 'future', 'sell_high'}


def session_constraints(payload):
    selected = payload.get('recommendation_filter') or 'all'
    if not isinstance(selected, str) or selected not in FILTERS:
        raise ValueError('Unsupported Recommended Trades filter.')
    excluded = payload.get('excluded_recommendation_families') or []
    if (not isinstance(excluded, list) or len(excluded) > 256
            or any(not isinstance(value, str) or len(value) != 64
                   or any(c not in '0123456789abcdef' for c in value) for value in excluded)):
        raise ValueError('Recommendation refresh requires at most 256 valid session family identities.')
    return selected, set(excluded)


def discover(data, workspace, reader, protected, excluded, *, max_theses=6, excluded_families=(), search_phase=0):
    """Supported slot opportunities first; bounded Market construction expansion.

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
    if profile is None and not search_phase:
        report['limitations'] = ['COMPATIBLE_PREPARED_LINEUPS_UNAVAILABLE']
        report['discovery_seconds'] = perf_counter() - started
        return report
    profile = profile or {'teams': {}, 'league_id': str(workspace['manager_context'].league_id),
        'semantic_generation': None, 'projection_generation': None, 'season': None, 'current_week': None, 'scoring_profile_id': None}
    from src.core.intelligence import resolve_trade_strategy
    team = next((t for t in workspace.get('teams', []) if int(t['roster_id']) == active), {})
    window = (workspace.get('competitive_windows') or {}).get(str(active))
    if not window or window.get('generation') != profile['semantic_generation']:
        window = None
    intent = resolve_trade_strategy(workspace.get('requested_strategy') or team.get('strategy'), window)['strategy']
    own_assets = {a.asset_id: a for a in workspace['pools'][active]}
    report['analysis_strategy'] = intent
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
            if not search_phase:
                continue
            own = other = {'weekly': {}}
        incoming = [row for a in workspace['pools'][rid] if (row := opportunity(a, own, other))]
        outgoing = [row for a in workspace['pools'][active] if a.asset_id not in protected
                    and (row := opportunity(a, other, own))]
        def order(row):
            return (-len(row['weeks']), sum(w['donor_optimal_starter'] for w in row['weeks']), row['asset_id'])
        def sale_order(row):
            # Supported recipient utility and own starter cost precede age.
            # This is a discovery tie-break, never a longevity forecast,
            # selling rule, personal price or acceptance estimate.
            age = own_assets[row['asset_id']].age
            return (sum(w['donor_optimal_starter'] for w in row['weeks']),
                    -max(w['incoming_projection'] - w['baseline_projection'] for w in row['weeks']),
                    -len(row['weeks']), age is None, -age if age is not None else 0, row['asset_id'])
        # Position-diverse evidence shortlists, not dynasty/quality ranks.
        def diverse(rows, *, selling=False):
            groups = defaultdict(list)
            for row in sorted(rows, key=sale_order if selling and intent == 'REBUILD' else order):
                groups[row['position']].append(row)
            if selling and intent == 'REBUILD':
                return [groups[position][index] for index in range(1 + search_phase)
                        for position in sorted(groups) if index < len(groups[position])]
            return [r for _, rows in sorted(groups.items()) for r in rows[:1 + search_phase]]
        pairs = [{'partner_id': rid, 'send': send, 'receive': receive,
                  'type': 'COMPLEMENTARY_SUPPORTED_SLOT_OPPORTUNITY',
                  'league_id': profile['league_id'], 'season': profile['season'],
                  'current_week': profile['current_week'], 'generation': profile['semantic_generation'],
                  'projection_generation': profile['projection_generation'],
                  'assessment': 'discovery_only_not_net_trade_impact'}
                 for send in diverse(outgoing, selling=True) for receive in diverse(incoming)]
        pairs.sort(key=lambda p: (order(p['receive']), order(p['send'])))
        # Bounded capital theses reuse the same observed player slot opportunity.
        # Picks supply acquisition capital, never fictional slot production.
        def priced_picks(owner):
            return sorted((a for a in workspace['pools'][owner] if a.kind == 'pick'
                           and a.trade_value is not None and a.asset_id not in excluded
                           and (owner != active or a.asset_id not in protected)),
                          key=lambda a: (-a.trade_value, a.asset_id))
        capital_pairs = []
        for player_rows, pick_rows, buying in ((incoming, priced_picks(active), True),
                                              (outgoing, priced_picks(rid), False)):
            if intent not in (('WIN NOW', 'RETOOL') if buying else ('REBUILD', 'RETOOL')):
                continue
            for player in diverse(player_rows, selling=not buying):
                price = next(a.trade_value for a in workspace['pools'][rid if buying else active]
                             if a.asset_id == player['asset_id'])
                picks = sorted(pick_rows, key=lambda a: (abs(a.trade_value - price), a.asset_id))
                if not picks:
                    continue
                # A nearest single first can be an inadequate return even when
                # a player plus an exact second forms a sound bilateral offer.
                # Explore different capital maturities/rounds progressively;
                # every chosen pick retains its own identity and quote.
                selected_picks = picks[:1]
                if intent == 'REBUILD' and not buying:
                    groups = {}
                    for candidate in picks:
                        groups.setdefault((candidate.season, candidate.round), []).append(candidate)
                    selected_picks = [rows[0] for rows in groups.values()][:1 + search_phase]
                for candidate in selected_picks:
                    pick = {'asset_id': candidate.asset_id, 'weeks': [], 'position': None}
                    capital_pairs.append({'partner_id': rid, 'send': pick if buying else player,
                        'receive': player if buying else pick, 'type': 'CAPITAL_SUPPORTED_SLOT_OPPORTUNITY',
                        'league_id': profile['league_id'], 'season': profile['season'],
                        'current_week': profile['current_week'], 'generation': profile['semantic_generation'],
                        'projection_generation': profile['projection_generation'],
                        'assessment': 'discovery_only_not_net_trade_impact'})
        # Preserve the existing per-counterparty limits. Rebuild spends its
        # first slots on observed production-to-capital opportunities.
        if capital_pairs:
            pairs = capital_pairs + pairs[:1] if intent == 'REBUILD' else pairs[:1] + capital_pairs[:1] if pairs else capital_pairs[:2]
        if search_phase:
            # Slot-only theses miss reserve consolidation and intentional capital exchanges.
            # Price is a cheap construction ordering, never a bilateral benefit verdict.
            own_pool = [a for a in workspace['pools'][active] if a.trade_value is not None
                        and a.asset_id not in protected | excluded]
            other_pool = [a for a in workspace['pools'][rid] if a.trade_value is not None and a.asset_id not in excluded]
            market_pairs = []
            for receive in sorted(other_pool, key=lambda a: (-a.trade_value, a.asset_id))[:12 + 6 * search_phase]:
                for send in sorted(own_pool, key=lambda a: (abs(a.trade_value - receive.trade_value), a.asset_id))[:2 + search_phase]:
                    market_pairs.append({'partner_id': rid,
                        'send': {'asset_id': send.asset_id, 'weeks': [], 'position': send.position},
                        'receive': {'asset_id': receive.asset_id, 'weeks': [], 'position': receive.position},
                        'type': 'CANONICAL_MARKET_PACKAGE_SEARCH', 'league_id': profile['league_id'],
                        'assessment': 'construction_only_not_a_benefit_or_acceptance_claim'})
            pairs += market_pairs
        if pairs:
            by_partner[rid] = pairs[:(2, 12, 24)[search_phase]]
    report['discovered_counterparties'] = len(by_partner)
    # Round-robin opportunities across counterparties avoids filling the budget
    # with variations from the first franchise. Deterministic, never randomized.
    partner_order = sorted(by_partner)
    if intent == 'REBUILD':
        def buyer_order(rid):
            observations = [w for row in by_partner[rid] if row['type'] == 'CAPITAL_SUPPORTED_SLOT_OPPORTUNITY'
                            for w in row['send']['weeks']]
            buyer = (workspace.get('competitive_windows') or {}).get(str(rid)) or {}
            current_window = buyer.get('classification') if buyer.get('generation') == profile['semantic_generation'] else None
            return (not bool(observations), -max((w['incoming_projection'] - w['baseline_projection'] for w in observations), default=0),
                    current_window not in ('Elite Contender', 'Contender', 'Playoff Team'), rid)
        partner_order.sort(key=buyer_order)
    all_theses = [by_partner[rid][index] for index in range((2, 12, 24)[search_phase])
                  for rid in partner_order if index < len(by_partner[rid])]
    assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    eligible_theses = []
    for thesis in all_theses:
        thesis['analysis_strategy'] = intent
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
    report['limitations'] = ['BOUNDED_PLAYER_AND_CAPITAL_DISCOVERY', 'NOT_EXHAUSTIVE_DYNASTY_OR_PICK_OPPORTUNITY_SEARCH']
    return report


def construct(workspace, thesis, protected, excluded, *, search_phase=0, search_diagnostics=None):
    active, partner = workspace['active_roster_id'], thesis['partner_id']
    outgoing = tuple(a for a in workspace['pools'][active] if a.asset_id not in protected | excluded)
    incoming = tuple(a for a in workspace['pools'][partner] if a.asset_id not in excluded)
    sent = next(a for a in outgoing if a.asset_id == thesis['send']['asset_id'])
    received = next(a for a in incoming if a.asset_id == thesis['receive']['asset_id'])
    admission = workspace.get('candidate_admission')
    rows = ([TradeProposal(active, partner, (sent,), (received,),
                          'Capital / production exchange' if sent.kind == 'pick' or received.kind == 'pick' else 'Complementary player exchange')]
            if admission is None or admission.allows(active, partner, (sent,), (received,)) else [])
    candidates = generate_proposals(active, partner, outgoing, incoming,
        required_sent_asset_id=sent.asset_id, required_received_asset_id=received.asset_id,
        construction_only=True, search_phase=search_phase, search_diagnostics=search_diagnostics,
        candidate_admission=admission if admission is not None and admission.capacity_supported else None)
    from src.core.intelligence import resolve_trade_strategy
    intent = thesis.get('analysis_strategy') or resolve_trade_strategy(workspace.get('requested_strategy'))['strategy']
    if intent == 'REBUILD' and sent.kind == 'player' and received.kind == 'pick':
        # Reserve coverage for disaggregation rather than consuming all shape
        # slots with two-for-one purchases. Proximity still orders within a
        # shape; only the shared evaluator can qualify any package.
        priority = {(1, 2): 0, (1, 1): 1, (2, 2): 2, (2, 1): 3, (3, 2): 4, (3, 1): 5}
        groups = {}
        for candidate in sorted(candidates, key=lambda p: priority.get((len(p.assets_sent), len(p.assets_received)), 6)):
            shape = (len(candidate.assets_sent), len(candidate.assets_received),
                     tuple(sorted(a.kind for a in candidate.assets_sent)), tuple(sorted(a.kind for a in candidate.assets_received)))
            groups.setdefault(shape, []).append(candidate)
        candidates = [group[index] for index in range(max(map(len, groups.values()), default=0))
                      for group in groups.values() if index < len(group)]
    seen = {(tuple(a.asset_id for a in row.assets_sent), tuple(a.asset_id for a in row.assets_received)) for row in rows}
    for candidate in candidates:
        key = (tuple(a.asset_id for a in candidate.assets_sent), tuple(a.asset_id for a in candidate.assets_received))
        if key in seen or sent.asset_id not in key[0]:
            continue
        seen.add(key)
        rows.append(candidate)
        if len(rows) == (3, 6, 8)[search_phase]:
            break
    if search_diagnostics is not None:
        search_diagnostics['cheap_package_pairs_inspected'] = search_diagnostics.get('cheap_package_pairs_inspected', 0) + 1
        search_diagnostics['constructed_candidates'] = len(rows)
        search_diagnostics['required_thesis_outgoing'] = sent.asset_id
    return rows


def family_identity(league_id, row, assets):
    """Group secondary variants by primary asset identities; retain exact packages."""
    p = row['proposal']
    def primary(ids):
        players = [assets[i] for i in ids if assets[i].kind == 'player']
        return max(players or [assets[i] for i in ids], key=lambda a: (a.trade_value or 0, a.asset_id)).asset_id
    return sha256(json.dumps([str(league_id), p['active_roster_id'], p['partner_roster_id'],
                             primary(p['assets_sent']), primary(p['assets_received'])]).encode()).hexdigest()


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
    capital = ((dimensions.get('strategic_fit') or {}).get('active') or {}).get('future_capital') or {}
    if ((capital.get('assessment') or {}).get('net_market_value') or 0) > 0:
        tags.append('FUTURE VALUE')
    return {'reason_tags': tags, 'stable_opportunity_reasons': stable,
        'unsupported_tags': {'SELL-HIGH OPPORTUNITY': 'No comparable current Market movement plus supported sale rationale.'},
        'market_price_edge': price_edge, 'why_now': {'availability': 'supported_current_state' if catalysts else 'unavailable',
        'catalysts': catalysts, 'historical_movement': None, 'urgency': None,
        'limitations': ['NO_COMPARABLE_CHANGE_CATALYST_ESTABLISHED']}}


def rank(rows):
    from services.trade_search_policy import rank_key
    return sorted(rows, key=rank_key)


def zero_result_guidance(funnel, discoveries, workspace, *, projection_available):
    """Summarize assessed limits and prepared search leads; never an offer."""
    counts = {key: funnel.counts[key] for key in (
        'hard_invalid', 'missing_evidence', 'counterparty_limited', 'strategically_rejected', 'filtered')}
    text = 'No bilateral recommendation to show under this search’s strategy and filters.'
    descriptions = {
        'hard_invalid': 'unresolved roster-space or ownership requirements',
        'missing_evidence': 'incomplete evidence required for a full assessment',
        'counterparty_limited': 'benefit to the other team was not established',
        'strategically_rejected': 'production, capital or Market cost was not justified',
        'filtered': 'offers excluded by filters or previously viewed families',
    }
    reasons = sorted(((count, key) for key, count in counts.items() if count), key=lambda row: (-row[0], row[1]))
    if reasons:
        count, key = reasons[0]
        text += f' Main limit: {descriptions[key]} ({count} assessed packages).'
        if counts['missing_evidence']:
            text += ' Review the source gaps in the assessed alternatives.'
    elif not projection_available:
        text += ' Compatible projection evidence is not ready. Check source preparation before trying again.'
    else:
        text += ' No priced, permitted construction reached evaluation. Review Market evidence and optional filters; protections are unchanged.'
    admission = workspace.get('candidate_admission')
    construction = admission.summary() if admission else {}
    if construction.get('roster_capacity_rejected_checks'):
        text += ' Some constructions needed extra roster space; DTOS did not assume a drop or an IR/taxi move.'
    if construction.get('ownership_rejected_assets'):
        text += ' Assets with unconfirmed current ownership or conflicting exact identity were excluded from the search.'
    leads = []
    assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
    if projection_available:
        for discovery in reversed(discoveries):
            for thesis in discovery.get('theses', []):
                if thesis['type'] != 'CAPITAL_SUPPORTED_SLOT_OPPORTUNITY' or not thesis['send']['weeks']:
                    continue
                asset = assets[thesis['send']['asset_id']]
                if asset.kind != 'player' or any(row['asset_id'] == asset.asset_id for row in leads):
                    continue
                leads.append({'asset_id': asset.asset_id, 'label': asset.label, 'position': asset.position,
                              'assessment': 'search_lead_not_a_qualified_offer'})
                if len(leads) == 3:
                    break
            if len(leads) == 3:
                break
    if leads:
        text += ' Consider reviewing ' + ', '.join(row['label'] for row in leads) + ' in Shop Asset. These are search leads, not qualified offers.'
    return {'message': text, 'assessed_limit_counts': counts, 'construction_admission': construction, 'shop_review_leads': leads,
            'recommendation': False, 'acceptance_probability': None}
