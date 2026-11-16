"""Shared bounded presentation of an already admitted team assessment.

No scoring, acquisition, solver, new cache or retained runtime owner.
"""
from services.my_team_outlook import prepared_outlook
from services.my_team_overview import roster_overview
from services.team_assessment_presentation import prepared_comparison, weekly_comparison
from services.trade_capital_inventory import inventory_baseline


def franchise_outlook(data, result, *, players=(), strategy='', overview=None):
    assessment = result.team_assessment
    overview = roster_overview(data, result, players) if overview is None else overview
    outlook = prepared_outlook(data, assessment, overview, players, strategy=strategy)
    comparison = prepared_comparison(data, result.context.projection_snapshot)
    outlook['position'] = weekly_comparison(assessment.team, data.get('week') or assessment.projection_week, diagnostics=comparison)
    outlook['brief'] = weekly_comparison(assessment.team, data.get('week') or assessment.projection_week, compact=True, diagnostics=comparison)
    # Reapply the existing diagnostic reader's effective qualification. Never
    # pair a saved roster claim with a newer availability-adjusted comparison.
    own = ((comparison or {}).get('teams') or {}).get(str(assessment.roster_id)) or {}
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
    outlook['details'] = list(dict.fromkeys([*outlook['details'], 'Weekly lineup strength is separate from overall franchise health. A saved goal is your preference, not a proven competitive window.']))
    return outlook
