"""Accessible, conclusion-first presentation of an existing prepared assessment."""
from html import escape
import json

from services.my_team_outlook import goal_options


def roster_shortcuts():
    return '''<nav class="thq-actions" aria-label="Roster sections">
<a class="thq-action" href="#full-roster" aria-label="View full roster">Players</a>
<a class="thq-action" href="#my-team-outlook" aria-label="Roster outlook and next step">Outlook</a>
<a class="thq-action" href="#positional-depth">Depth</a>
<a class="thq-action" href="#draft-capital" aria-label="Draft capital">Picks</a>
</nav>'''


def outlook_panel(outlook, *, editable, roster_id):
    rows = [('Current position', outlook['brief']), ('Main strength', outlook['strength']),
            ('Depth and uncertainty', outlook['concern']), ('Future flexibility', outlook['future'])]
    unprepared = outlook.get('comparison_prepared') is False
    action = (f'<a id="my-team-outlook-action" class="thq-action" href="{escape(outlook["href"], quote=True)}">{escape(outlook["action"])}</a>'
              if editable else '')
    need = outlook.get('trade_need') if editable else None
    if need:
        action += (f'<p>{escape(need["reason"])}</p><a id="my-team-trade-need" class="thq-action" '
                   f'href="{escape(need["href"], quote=True)}">Explore {escape(need["position"])} trades</a>')
    trade = (f'<a class="thq-action" href="/trades/calculator?front_office={roster_id}">Evaluate a trade</a>'
             f'<a class="thq-action" href="/trades?front_office={roster_id}">Recommended Trades</a>') if editable else ''
    choices = escape(json.dumps(goal_options(roster_id), separators=(',', ':')), quote=True) if editable else '{}'
    heading = '<h2 id="my-team-outlook-title">Your roster at a glance</h2>'
    lead = (f'<p id="my-team-outlook-lead">Comparison pending: lineup and depth. {escape(outlook["future_summary"])}</p>'
            if unprepared else ''.join('<p' + (' id="my-team-outlook-lead"' if label == 'Current position' else '')
                + f'><b>{label}:</b> {escape(text)}</p>' for label, text in rows))
    details = ('<details id="my-team-outlook-evidence" class="thq-strength-detail">'
               '<summary aria-label="Why this outlook? Expand the assessment and evidence" aria-describedby="my-team-outlook-lead">'
               + (heading + lead if unprepared else '<span>Why this outlook?</span>') + '</summary>'
               + f'<p>{escape(outlook["position"])}</p>'
               + (f'<p>{escape(outlook["brief"])}</p>' if unprepared else '')
               + ''.join(f'<p><b>{label}:</b> {escape(text)}</p>' for label, text in rows[1:])
               + '<p>Standing and record are separate from this projected lineup comparison.</p>'
               + (f'<p><b>Your goal:</b> <span id="my-team-outlook-goal">{escape(outlook["guidance"])}</span></p>'
                  if editable else '<p>Read-only franchise view. Manager intent is not inferred.</p>')
               + '<ul>' + ''.join(f'<li>{escape(text)}</li>' for text in outlook['details']) + '</ul>'
               + ('<nav class="thq-actions" aria-label="Trade shortcuts">' + trade + '</nav>' if trade else '')
               + '</details>')
    return (f'<section id="my-team-outlook" class="thq-outlook" data-outlook-goals="{choices}" data-dtos-component="recommendation" aria-labelledby="my-team-outlook-title">'
            + (details if unprepared else heading + lead + details)
            + '<div class="thq-outlook-next">' + action + '</div></section>')
