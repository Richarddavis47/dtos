"""Mobile-friendly browsing without copying or calculating projection evidence."""
from html import escape
from urllib.parse import quote, urlencode
from src.ui.customer_experience import plain_reason, source_details


def player_projection_panel(view: dict, front_office: int | None = None) -> str:
    from services.asset_explanations import player_projection_explanation
    from src.ui.explanations import explanation_panel
    explanation = source_details(explanation_panel(player_projection_explanation(view))
        + ('<p>' + escape(str(view['display_reason'])) + '</p>' if view.get('display_reason') else ''),
        summary='Projection sources and coverage')
    selected = view['week']
    weeks = view['weeks']
    options = ''.join(f'<option value="{w}"{" selected" if w == selected else ""}>Week {w}</option>'
                      for w in sorted(set(weeks) | {selected}))
    office = f'<input type="hidden" name="front_office" value="{front_office}">' if front_office is not None else ''
    path = '/players/' + quote(view['player_id'], safe='')
    origin = view.get('navigation_context') or {}
    office += ''.join(f'<input type="hidden" name="{escape(key)}" value="{escape(str(value))}">' for key, value in origin.items() if key in {'from_team', 'from_section'})
    links = []
    for label, choices in (('Previous week', [w for w in weeks if w < selected]),
                           ('Next week', [w for w in weeks if w > selected])):
        if choices:
            query = {**origin, 'week': choices[-1] if label.startswith('Previous') else choices[0]}
            if front_office is not None:
                query['front_office'] = front_office
            links.append(f'<a class="button" href="{path}?{escape(urlencode(query))}">{label}</a>')
    notes = dict.fromkeys(plain_reason(view[key]).replace("current league snapshot", "current league data")
                          .replace("scoring publication", "league scoring")
                          for key in ('reason', 'participation_note', 'eligibility_note') if view.get(key))
    reason = ''.join(f'<p>{escape(note)}</p>' for note in notes)
    if view.get('display_reason'):
        reason += '<p>Exact Sleeper display precision has not been verified.</p>'
    return ('<link rel="stylesheet" href="/static/css/matchups.css">'
        f'<section class="card" id="player-weekly-projections" data-week-endpoint="{path}/projections" aria-label="Weekly Sleeper projections"><h2>Weekly Sleeper projections</h2>'
        f'<p>Week {selected} · <strong data-projection-week="{selected}" '
        f'data-projection-availability="{view["availability"]}">{escape(view["display"])}</strong></p>'
        f'{reason}<nav class="season-week-nav" aria-label="Player projection week navigation">'
        + ''.join(links) + f'<form method="get" action="{path}">{office}'
        f'<label for="player-projection-week">Week</label><select id="player-projection-week" name="week">{options}</select>'
        '<button type="submit">Show projection</button></form></nav>'
        '<p class="muted">Sleeper’s projection uses this league’s scoring. Browsing does not change your active league week.</p>'
        '<p class="projection-navigation-status" role="status" aria-live="polite"></p>' + explanation + '</section>'
        '<script src="/static/js/player-projections.js" defer></script>')
