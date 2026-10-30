"""Presentation facts over the existing canonical assessment, not a new model."""
from collections import Counter

from services.standings import standings_order, playoff_position
from src.core.history_context.results import number


def roster_overview(data, intelligence, players):
    evidence = intelligence.team_assessment.roster_evidence
    positions = evidence.positions
    supported = [item for item in positions.items() if item[1]['starting_points'] is not None]
    best = max(supported, key=lambda item: item[1]['starting_points'], default=None)
    strength = (f"{best[0]} has the largest supported starting contribution: {best[1]['starting_points']:.2f} Sleeper-projected points across {best[1]['starting_count']} players in the {best[1]['lineup_basis']}. Position and starting-slot demand differ; this is not a cross-position quality grade."
                if best else 'Starting strength cannot be confirmed without compatible Sleeper projections and lineup evidence.')
    demand = [item for item in positions.items() if item[1]['starting_count'] or item[1]['required_slots']]
    risky = sorted(demand, key=lambda item: (item[1]['reserve_covered'] == item[1]['reserve_expected'] and item[1]['reserve_expected'] > 0,
                                          item[1]['reserve_covered'] > 0, -(item[1]['starting_count'] or item[1]['required_slots'])))
    risk = 'Player quantity alone does not establish expendable depth. Review replacement coverage before shopping an asset.'
    if risky:
        pos, row = risky[0]
        if row['reserve_covered'] < row['reserve_expected']:
            risk = f"{pos} has {row['reserve_covered']}/{row['reserve_expected']} eligible reserves with supported projections. Missing backup evidence prevents DTOS from confirming reliable {pos} depth."
        elif not row['reserve_expected']:
            risk = f"{pos} has no eligible reserve behind its starting group. An absence would require a replacement; no injury probability is estimated."
        else:
            risk = f"{pos} backup projection coverage is complete, but a supported projection does not guarantee availability or make a player expendable."
    status_risks = []
    diagnostic_rows = [(pos, facts.get('diagnostic') or {}) for pos, facts in positions.items()]
    needs = sorted((row for _, row in diagnostic_rows if row.get('starter_need') or row.get('resilience_need') or row.get('quality_depth_need')),
                   key=lambda row: not row.get('starter_need'))
    strengths = [pos for pos, row in diagnostic_rows if row.get('strength')]
    expendable = [pos for pos, row in diagnostic_rows if row.get('surplus_assets')]
    if needs:
        risk = needs[0]['interpretation']
    if strengths:
        strength = 'Supported current-week positional strength: ' + ', '.join(strengths) + '. Strength is not automatically expendable surplus.'
    if expendable:
        strength += ' Conditional expendable depth: ' + ', '.join(expendable) + '; review exact removal scenarios before trading.'
    from src.ui.intelligence_presentation import projection_evidence_summary
    diagnostic = next((row for _, row in diagnostic_rows if row), {})
    diagnostic_evidence = diagnostic.get('evidence') or {}
    notice = projection_evidence_summary(diagnostic_evidence, concise=True) if diagnostic_evidence.get('conclusion_state') not in (None, 'current') else ''
    if notice:
        strength = notice + ' ' + strength.replace('Supported current-week positional strength:', 'Provisional current-week positional strength:')
        risk = notice + ' ' + risk
    for player in players:
        source = (data.get('players') or {}).get(str(player['id'])) or {}
        status = player.get('injury_status') or source.get('injury_status') or player.get('status') or source.get('status')
        player['availability_status'] = status
        if status and str(status).upper() not in {'ACTIVE', 'HEALTHY'}:
            status_risks.append(f"{player['name']}: {status}")
    order = standings_order(data)
    rid = intelligence.context.active_roster_id
    rank = order['ranks'].get(rid)
    playoff = playoff_position(data, order)
    return {'strength': strength, 'risk': risk, 'positions': positions, 'statuses': status_risks,
            'slots': dict(Counter(p.get('roster_slot') or 'Unknown' for p in players)),
            'standing': f'#{rank} of {len(order["teams"])}' if rank is not None else 'Unavailable',
            'standing_reason': order['reason'] if not rank else order['provenance'],
            'playoff': playoff, 'projection_week': evidence.projection_week,
            'generation': evidence.generation, 'projection_generation': evidence.projection_generation,
            'market_generation': (intelligence.context.cached_data.get('market_data') or {}).get('generation'),
            'max_points': number(intelligence.context.roster.get('max_points'))}
