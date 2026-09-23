"""Compact Attention display using the shared explanation hierarchy."""
from html import escape

from src.core.explanations import Availability, EvidenceContext, EvidenceItem, EvidenceKind, Explanation, Statement
from src.ui.explanations import explanation_panel
from src.ui.event_presentation import event_presentation


def attention_panel(state):
    cards = []
    for item in state['items']:
        event = event_presentation(item, league_id=state['league_id'], roster_id=state['roster_id'])
        change = item['kind'] == 'change_event'
        context = EvidenceContext('pick_range' if change else 'team_strength', 'owned_pick' if change else 'roster_week', item['generation'], item['source_methodology'], state['league_id'])
        evidence = EvidenceItem('coverage', 'Comparable pick evidence' if change else 'Unsupported required slots', EvidenceKind.DERIVED, context,
                                item['reference'], 'pick range / exact slot' if change else 'lineup slots', Availability.AVAILABLE if change else Availability.PARTIAL,
                                item['why'] if change else ', '.join(item['unsupported_slots']))
        view = Explanation(item['title'], state['league_id'], (context,), (evidence,),
            Statement(event.materiality_reason, event.summary, ('coverage',)),
            confidence=(Statement('COVERAGE_NOT_OUTCOME', item['confidence'], ('coverage',)),))
        related = item.get('related_weeks') or []
        extra = '<p>Also present in prepared weeks: ' + escape(', '.join(map(str, related))) + '.</p>' if related else ''
        cards.append('<article class="card"><small>' + ('Comparable pick evidence change' if change else 'Current state · not a change alert') + '</small>'
                     + '<h3>' + escape(item['title']) + '</h3><p>' + escape(item['why']) + '</p>'
                     + '<details><summary style="min-height:44px;cursor:pointer">Why this deserves review</summary>'
                     + explanation_panel(view) + extra + '</details><a class="ux-action" href="' + escape(item['href'], quote=True)
                     + '">Review Team HQ evidence →</a></article>')
    quiet = '<div class="card"><p>No attention item qualifies in the evaluated prepared evidence.</p></div>'
    gaps = [key.replace('_', ' ') + ': ' + value.replace('_', ' ') for key, value in state['coverage'].items() if value != 'available']
    limitations = ('<details><summary style="min-height:44px;cursor:pointer">Attention coverage</summary>'
                  '<p>Not evaluated: ' + escape(', '.join(gaps)) + '. This is not proof that no changes exist.</p></details>') if gaps else ''
    return '<section class="ux-section" aria-label="Home Attention"><h2>Attention</h2>' + (''.join(cards) or quiet) + limitations + '</section>'
