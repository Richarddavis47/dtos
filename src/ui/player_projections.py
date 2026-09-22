"""Mobile-friendly browsing without copying or calculating projection evidence."""
from html import escape
from urllib.parse import quote, urlencode


def player_projection_panel(view: dict, front_office: int | None = None) -> str:
    from services.asset_explanations import player_projection_explanation
    from src.ui.explanations import explanation_panel
    explanation = explanation_panel(player_projection_explanation(view))
    selected = view['week']
    weeks = view['weeks']
    options = ''.join(f'<option value="{w}"{" selected" if w == selected else ""}>Week {w}</option>'
                      for w in sorted(set(weeks) | {selected}))
    office = f'<input type="hidden" name="front_office" value="{front_office}">' if front_office is not None else ''
    path = '/players/' + quote(view['player_id'], safe='')
    links = []
    for label, choices in (('Previous week', [w for w in weeks if w < selected]),
                           ('Next week', [w for w in weeks if w > selected])):
        if choices:
            query = {'week': choices[-1] if label.startswith('Previous') else choices[0]}
            if front_office is not None:
                query['front_office'] = front_office
            links.append(f'<a class="button" href="{path}?{escape(urlencode(query))}">{label}</a>')
    reason = f'<p>{escape(str(view["reason"]))}</p>' if view.get('reason') else ''
    return ('<link rel="stylesheet" href="/static/css/matchups.css">'
        f'<section class="card" id="player-weekly-projections" data-week-endpoint="{path}/projections" aria-label="Weekly Sleeper projections"><h2>Weekly Sleeper projections</h2>'
        f'<p>Week {selected} · <strong data-projection-week="{selected}" '
        f'data-projection-availability="{view["availability"]}">{escape(view["display"])}</strong></p>'
        f'{reason}<nav class="season-week-nav" aria-label="Player projection week navigation">'
        + ''.join(links) + f'<form method="get" action="{path}">{office}'
        f'<label for="player-projection-week">Week</label><select id="player-projection-week" name="week">{options}</select>'
        '<button type="submit">Show projection</button></form></nav>'
        '<p class="muted">League-scored weekly expectation, not dynasty value. Browsing does not change your active league week.</p>'
        '<p class="projection-navigation-status" role="status" aria-live="polite"></p>' + explanation + '</section>'
        '<script src="/static/js/player-projections.js" defer></script>')
