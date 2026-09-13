"""Non-scalar, generation-scoped pick portfolio evidence."""
from collections import Counter
import json

RANGE_METHOD = 'pick-slot-interval-1'
MAX_RANGE_TRANSITIONS = 128


def assess_pick_range(pick, *, league_id):
    """Classify a sourced draft-order interval, never a Market price or seed.

    No provider currently guarantees a future finish interval for every team.
    Absent such evidence UNKNOWN is deliberate. An interval must stay inside
    one third of the league's draft order to support EARLY/MID/LATE.
    """
    result = dict(pick)
    result.update(projected_range='UNKNOWN', projected_range_confidence='LOW',
                  range_supported=False, range_method=RANGE_METHOD,
                  range_reasons=['NO_SUPPORTED_DRAFT_ORDER_INTERVAL'])
    evidence = pick.get('range_evidence') or {}
    year = pick.get('year', pick.get('season'))
    if not evidence:
        return result
    if (evidence.get('league_id') != league_id
            or str(evidence.get('original_roster_id')) != str(pick.get('original_roster_id'))
            or evidence.get('year') != year
            or not evidence.get('reference') or not evidence.get('generation')):
        result['range_reasons'] = ['RANGE_EVIDENCE_IDENTITY_OR_GENERATION_UNAVAILABLE']
        return result
    lower, upper, size = (evidence.get(k) for k in ('earliest_slot', 'latest_slot', 'league_size'))
    if (any(not isinstance(x, int) or isinstance(x, bool) for x in (lower, upper, size))
            or not 1 <= lower <= upper <= size or size < 3
            or evidence.get('draft_order_rules_supported') is not True
            or evidence.get('data_complete') is not True):
        result['range_reasons'] = ['DRAFT_ORDER_OR_COVERAGE_UNSUPPORTED']
        return result
    # A playoff seed is not a draft-order interval. The canonical upstream
    # source must explicitly establish the latter under this league's rules.
    if evidence.get('concept') != 'draft_order_interval':
        result['range_reasons'] = ['NOT_DRAFT_ORDER_EVIDENCE']
        return result
    stage = evidence.get('season_stage')
    if stage not in {'regular_season', 'postseason', 'complete'}:
        result['range_reasons'] = ['SEASON_STAGE_UNSUPPORTED']
        return result
    def band(slot):
        return 'EARLY' if slot * 3 <= size else 'MID' if slot * 3 <= size * 2 else 'LATE'
    if band(lower) != band(upper):
        result['range_reasons'] = ['INTERVAL_CROSSES_RANGE_BOUNDARY']
        return result
    locked = (evidence.get('result_locked') is True
              and evidence.get('all_round_components_complete') is True
              and stage == 'complete')
    result.update(projected_range=band(lower), range_supported=True,
                  projected_range_confidence='HIGH' if locked else 'MEDIUM' if stage == 'postseason' else 'LOW',
                  range_reasons=['RESULT_LOCKED' if locked else 'PROJECTED_INTERVAL_NOT_LOCKED'],
                  range_reference=evidence['reference'], range_generation=evidence['generation'])
    if lower == upper and locked:
        round_number = pick.get('round')
        if isinstance(round_number, int) and not isinstance(round_number, bool) and round_number > 0:
            result['exact_slot'] = f"{round_number}.{lower:02d}"
            result['exact_slot_established'] = True
    return result


def pick_portfolio(picks, *, league_id, generation):
    """Count owned assets without inventing range, class quality or utility.

    Original-franchise exposure is independent of current ownership. Range
    labels only count when the upstream evidence explicitly supports them.
    """
    years, rounds, originals, ranges, confidence = (Counter() for _ in range(5))
    seen = set()
    for pick in picks:
        year = pick.get('year', pick.get('season'))
        round_number = pick.get('round')
        original = pick.get('original_roster_id')
        identity = (year, round_number, original)
        if identity in seen:
            raise ValueError('Duplicate pick identity in portfolio')
        seen.add(identity)
        if pick.get('league_id') not in (None, league_id):
            raise ValueError('Cross-league pick portfolio')
        years[str(year) if year is not None else 'UNKNOWN'] += 1
        rounds[str(round_number) if round_number is not None else 'UNKNOWN'] += 1
        originals[str(original) if original is not None else 'UNKNOWN'] += 1
        band = pick.get('projected_range') if pick.get('range_supported') is True else None
        if band not in {'EARLY', 'MID', 'LATE'}:
            band = 'UNKNOWN'
        ranges[band] += 1
        confidence[str(pick.get('projected_range_confidence') or 'LOW') if band != 'UNKNOWN' else 'LOW'] += 1
    return {'league_id': league_id, 'generation': generation,
            'years': dict(sorted(years.items())), 'rounds': dict(sorted(rounds.items())),
            'original_franchise_exposure': dict(sorted(originals.items())),
            'projected_range_distribution': dict(sorted(ranges.items())),
            'range_confidence_distribution': dict(sorted(confidence.items())),
            'timing': 'Draft years, not a forecast of class quality or current lineup production.',
            'score': None}


def record_range_history(store, picks, *, league_id, observed_at):
    """Atomic compact metadata history, bounded per pick; no source copies.

    Unchanged semantic states execute no writes, including timestamp updates.
    A -> B -> A is retained. Oldest transitions beyond the explicit cap are
    summarized by a discarded count; canonical source history is untouched.
    """
    written = 0
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        for pick in picks:
            key = json.dumps([str(league_id), pick.get('year', pick.get('season')),
                              pick.get('round'), pick.get('original_roster_id')], separators=(',', ':'))
            state = {k: pick.get(k) for k in ('projected_range', 'projected_range_confidence', 'range_method')}
            state['exact_slot'] = pick.get('exact_slot') if pick.get('exact_slot_established') is True else None
            row = connection.execute("SELECT value FROM metadata WHERE namespace='pick_range_history' AND key=?", (key,)).fetchone()
            prior = json.loads(row[0]) if row else {'events': [], 'discarded_transitions': 0}
            events = prior['events']
            previous = events[-1] if events else None
            if previous and previous['state'] == state:
                continue
            inputs = pick.get('range_evidence') or {}
            # Only explicit source revisions can establish causal reason codes.
            revisions = {k: inputs[k] for k in ('standings_revision', 'team_strength_revision',
                'playoff_revision', 'season_stage', 'data_complete', 'result_locked') if k in inputs}
            reasons = []
            if previous is None:
                reasons = ['INITIAL_OBSERVATION']
            elif previous['state']['range_method'] != state['range_method']:
                reasons = ['METHODOLOGY_CHANGED']
            else:
                for field, reason in (('standings_revision', 'STANDINGS_CHANGED'),
                    ('team_strength_revision', 'TEAM_STRENGTH_CHANGED'),
                    ('playoff_revision', 'PLAYOFF_POSITION_CHANGED'),
                    ('season_stage', 'SEASON_STAGE_ADVANCED'), ('data_complete', 'DATA_COVERAGE_CHANGED'),
                    ('result_locked', 'RESULT_LOCKED')):
                    if field in revisions and field in previous['source_revisions'] and revisions[field] != previous['source_revisions'][field]:
                        if field == 'result_locked' and revisions[field] is not True:
                            continue
                        if field == 'season_stage':
                            stages = {'preseason': 0, 'regular_season': 1, 'postseason': 2, 'complete': 3}
                            if stages.get(revisions[field], -1) <= stages.get(previous['source_revisions'][field], -1):
                                continue
                        reasons.append(reason)
                if state['exact_slot'] is not None and previous['state']['exact_slot'] != state['exact_slot']:
                    reasons.append('EXACT_SLOT_ESTABLISHED')
                if not reasons:
                    reasons = ['SEMANTIC_CHANGE_CAUSE_UNAVAILABLE']
            events.append({'state': state, 'observed_at': observed_at,
                           'source_revisions': revisions, 'reasons': reasons})
            overflow = max(0, len(events) - MAX_RANGE_TRANSITIONS)
            value = {'events': events[-MAX_RANGE_TRANSITIONS:],
                     'discarded_transitions': prior['discarded_transitions'] + overflow}
            connection.execute("INSERT INTO metadata(namespace,key,value) VALUES('pick_range_history',?,?) "
                               "ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP",
                               (key, json.dumps(value, sort_keys=True, separators=(',', ':'))))
            written += 1
    return written


def prepare_pick_context(data, store, *, observed_at):
    """Synchronization-only publication; request consumers stay read-only."""
    league_id = str((data.get('league') or {}).get('league_id') or '')
    if not league_id:
        raise ValueError('Pick preparation requires an active league')
    prepared = [assess_pick_range(pick, league_id=league_id) for pick in data.get('pick_ledger') or ()]
    # Validate identity uniqueness and league scope before any durable write.
    pick_portfolio(prepared, league_id=league_id, generation=RANGE_METHOD)
    count = record_range_history(store, prepared, league_id=league_id, observed_at=observed_at)
    data['pick_ledger'] = prepared
    for team in data.get('teams') or ():
        roster = str(team.get('roster_id'))
        team['picks_owned'] = [p for p in prepared if str(p.get('current_owner_id')) == roster]
        team['picks_traded_away'] = [p for p in prepared if str(p.get('original_roster_id')) == roster
                                     and str(p.get('current_owner_id')) != roster]
    return {'semantic_history_writes': count, 'picks': len(prepared), 'method': RANGE_METHOD}
