"""Shared bounded presentation of an already admitted team assessment.

No scoring, acquisition, solver, new cache or retained runtime owner.
"""
from services.my_team_outlook import goal_options, _slot_description
from src.ui.intelligence_presentation import manager_points
from math import isfinite
from services.my_team_overview import roster_overview
from services.team_assessment_presentation import prepared_comparison, weekly_comparison
from services.trade_capital_inventory import inventory_baseline


def franchise_outlook(data, result, *, players=(), strategy='', overview=None):
    assessment = result.team_assessment
    overview = roster_overview(data, result, players) if overview is None else overview
    goal = strategy if strategy in {'WIN NOW', 'RETOOL', 'REBUILD'} else ''
    outlook = {**goal_options(assessment.roster_id)[goal], 'details': [
        'Standing: ' + (overview.get('standing_reason') or 'Official standing evidence is unavailable.'),
        'Current strength is not championship probability or future sustainability.',
        'Original-franchise identity is separate from current ownership; unknown pick ranges remain unknown.',
        'Ages and current projections do not establish years remaining or a multi-season forecast.']}
    comparison = prepared_comparison(data, result.context.projection_snapshot)
    outlook['position'] = weekly_comparison(assessment.team, data.get('week') or assessment.projection_week, diagnostics=comparison)
    outlook['brief'] = weekly_comparison(assessment.team, data.get('week') or assessment.projection_week, compact=True, diagnostics=comparison)
    # Reapply the existing diagnostic reader's effective qualification. Never
    # pair a saved roster claim with a newer availability-adjusted comparison.
    own = ((comparison or {}).get('teams') or {}).get(str(assessment.roster_id)) or {}
    outlook['comparison_prepared'] = 'optimal_ids' in own
    positions = own.get('positions') or {}
    supported = [(pos, row) for pos, row in positions.items()
                 if (row.get('evidence') or {}).get('calculation_supported')
                 and row.get('conclusion_state') in {'current', 'provisional'}]
    strengths = [(pos, row) for pos, row in supported if row.get('strength')]
    if strengths:
        pos, row = strengths[0]
        outlook['strength'] = ('Provisional: ' if row['conclusion_state'] != 'current' else '') + f'Supported positional strength: {pos}. Backups are not automatically expendable.'
    else:
        outlook['strength'] = 'A positional advantage is not established by the available comparisons.'
    needs = sorted([(pos, row) for pos, row in supported if any(row.get(k) for k in ('starter_need', 'resilience_need', 'quality_depth_need'))],
                   key=lambda item: not item[1].get('starter_need'))
    if needs:
        pos, row = needs[0]
        outlook['concern'] = ('Provisional: ' if row['conclusion_state'] != 'current' else '') + (
            f'{pos}: supported evidence identifies a starting-lineup need.' if row.get('starter_need') else
            f'{pos}: eligible backups project below the supported league reference.' if row.get('quality_depth_need') else
            f'{pos}: the supported backups do not cover every tested starter absence.')
        if row.get('base_reason'):
            outlook['details'].append(row['base_reason'])
    else:
        outlook['concern'] = ('No supported shortfall is established; incomplete evidence is not proof of strong depth.'
                              if supported else 'Compatible lineup and backup evidence is not prepared; missing or incompatible projections are not zero production, and no roster weakness is inferred.')
    # Explanation and numbers come from this same admitted diagnostic, never a
    # retained multi-horizon profile with a different availability baseline.
    outlook['details'].append(outlook['position'])
    outlook['details'].extend(own.get('limitations') or [])
    if outlook['comparison_prepared']:
        cohort = comparison.get('teams') or {}
        comparable = {rid for rid, row in cohort.items() if row.get('optimal_points') is not None
                      and (row.get('evidence') or {}).get('calculation_supported')}
        outlook['details'].append(f'Lineup comparison: {len(comparable)}/{len(cohort)} franchises can fill the configured starting slots with supported eligible projections. Incomplete bench coverage alone does not exclude a franchise; this is separate from official standings and full replacement-depth support.')
        names = {str(team.get('roster_id')): team.get('team_name') or team.get('name') for team in data.get('teams') or []}
        for rid, row in cohort.items():
            if rid in comparable:
                continue
            slots = _slot_description(row.get('unsupported_slots'))
            reason = ('Starting slots without supported eligible players: ' + slots + '.' if slots else
                      ' '.join(row.get('lineup_limitations') or row.get('independent_limitations') or row.get('limitations') or ['Starting-slot coverage is not established.']))
            outlook['details'].append(f"{names.get(str(rid)) or f'Franchise {rid}'}: excluded from this modeled comparison. {reason} Missing points are not zero.")
    outlook['details'].append('Roster projection coverage is a different measure. This counts player-week numbers, including reserve/taxi players; it is separate from playable starting-slot eligibility.')
    for pos, row in supported:
        if row.get('base_reason'):
            outlook['details'].append(row['base_reason'])
        values = row.get('observed_replacement_points') or []
        if values and all(isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v) for v in values):
            low, high = min(values), max(values)
            points = manager_points(low) if low == high else manager_points(low) + '–' + manager_points(high)
            outlook['details'].append(('Provisional · ' if row.get('conclusion_state') != 'current' else '') + f'{pos} observed replacement projection: {points} points across separate starter-absence scenarios; not simultaneous coverage.')
    inventory = inventory_baseline(data, assessment.roster_id)
    if inventory['complete']:
        picks = inventory['before']
        firsts = [p for p in picks if p[1] == 1]
        own = sum(p[2] == assessment.roster_id for p in firsts)
        years = ', '.join(map(str, inventory['seasons']))
        outlook['future'] = (f'{len(picks)} owned picks in {years}, including {len(firsts)} first-round picks '
                             f'({own} originally yours). This is future trade flexibility, not a forecast of future production.')
    else:
        outlook['future'] = inventory['reason']
        if inventory['before']:
            outlook['future'] += f" {len(inventory['before'])} individually supported owned picks are listed in Draft capital; this is not a complete inventory."
    outlook['future_summary'] = outlook['future'] if inventory['complete'] else 'Draft-pick totals unknown.'
    # Home must not restore an unqualified total through its older capital card.
    # Reuse this independently reconciled family, not assessment price coverage.
    recorded = []
    capital = assessment.team.future_capital_evidence or {}
    if (not inventory.get('invalid') and capital.get('league_id') == assessment.league_id
            and capital.get('roster_id') == assessment.roster_id
            and capital.get('generation') == assessment.generation):
        seen = set()
        for row in capital.get('picks', ()):
            pick = row.get('identity') or {}
            fields = [pick.get('year', pick.get('season')), pick.get('round'), pick.get('original_roster_id'), pick.get('current_owner_id')]
            if any(isinstance(v, bool) or not str(v).isdigit() or int(v) <= 0 for v in fields):
                continue
            year, round_number, original, owner = map(int, fields)
            key = (year, round_number, original)
            if owner != assessment.roster_id or key in seen or pick.get('league_id') not in (None, assessment.league_id):
                continue
            if inventory['complete'] and list(key) not in inventory['before']:
                continue
            seen.add(key)
            round_label = 'first' if round_number == 1 else f'round {round_number}'
            original_label = pick.get('original_team') or f'original franchise {original}'
            recorded.append((f'Recorded {year} {round_label} · {original_label} · owned by your team',
                             f'{year} round {round_number} · original {original} · owner {owner}'))
    outlook['capital_action'] = dict(
        title='Review recorded draft picks', reason=outlook['future'] + (' ' + '; '.join(r[0] for r in recorded[:2]) + '.' if recorded else ''),
        drawback='Unknown ranges are not guaranteed early picks. Recorded ownership is separate from future performance. Review exact identities before considering a trade.',
        action='Review exact draft capital', href=f'/teams/{assessment.roster_id}#draft-capital', details=[r[1] for r in recorded])
    outlook['details'] = list(dict.fromkeys([*outlook['details'], 'Weekly lineup strength is separate from overall franchise health. A saved goal is your preference, not a proven competitive window.']))
    return outlook
