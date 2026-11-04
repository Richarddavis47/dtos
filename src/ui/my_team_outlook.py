"""Accessible, conclusion-first presentation of an existing prepared assessment."""
from html import escape
import json

from services.my_team_outlook import goal_options


def outlook_panel(outlook, *, editable, roster_id):
    rows = [('Current position', outlook['position']), ('Main strength', outlook['strength']),
            ('Depth and uncertainty', outlook['concern']), ('Future flexibility', outlook['future'])]
    action = (f'<a id="my-team-outlook-action" class="thq-action" href="{escape(outlook["href"], quote=True)}">{escape(outlook["action"])}</a>'
              if editable else '')
    trade = (f'<a class="thq-action" href="/trades/calculator?front_office={roster_id}">Trade Calculator</a>'
             f'<a class="thq-action" href="/trades?front_office={roster_id}">Trade opportunities</a>') if editable else ''
    navigation = ('<div class="thq-outlook-next">' + action + '</div>'
                  '<nav class="thq-actions" aria-label="Roster sections">'
                  '<a class="thq-action" href="#full-roster" aria-label="View full roster">Roster</a>'
                  '<a class="thq-action" href="#positional-depth">Depth</a>'
                  '<a class="thq-action" href="#draft-capital" aria-label="Draft capital">Capital</a></nav>')
    choices = escape(json.dumps(goal_options(roster_id), separators=(',', ':')), quote=True) if editable else '{}'
    return (f'<section id="my-team-outlook" class="thq-outlook" data-outlook-goals="{choices}" data-dtos-component="recommendation" aria-labelledby="my-team-outlook-title">'
            '<details id="my-team-outlook-evidence" class="thq-strength-detail">'
            '<summary aria-label="Why this outlook? Expand the assessment and evidence" aria-describedby="my-team-outlook-lead">'
            '<h2 id="my-team-outlook-title">Your roster at a glance</h2>'
            f'<p id="my-team-outlook-lead">{escape(outlook["brief"])}</p></summary>'
            + ''.join(f'<p><b>{label}:</b> {escape(text)}</p>' for label, text in rows)
            + (f'<p><b>Your goal:</b> <span id="my-team-outlook-goal">{escape(outlook["guidance"])}</span></p>' if editable else '<p>Read-only franchise view. Manager intent is not inferred.</p>')
            + '<ul>' + ''.join(f'<li>{escape(text)}</li>' for text in outlook['details'])
            + '</ul>' + ('<nav class="thq-actions" aria-label="Trade shortcuts">' + trade + '</nav>' if trade else '')
            + '</details>' + navigation + '</section>')
