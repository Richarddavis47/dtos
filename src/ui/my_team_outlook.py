"""Accessible, conclusion-first presentation of an existing prepared assessment."""
from html import escape
import json

from services.my_team_outlook import goal_options


def outlook_panel(outlook, *, editable, roster_id):
    rows = [('Current position', outlook['position']), ('Main strength', outlook['strength']),
            ('Biggest depth risk', outlook['concern']), ('Future flexibility', outlook['future'])]
    action = (f'<p><a id="my-team-outlook-action" class="thq-action" href="{escape(outlook["href"], quote=True)}">{escape(outlook["action"])}</a></p>'
              if editable else '<p>Read-only franchise view. Manager intent is not inferred.</p>')
    choices = escape(json.dumps(goal_options(roster_id), separators=(',', ':')), quote=True) if editable else '{}'
    return (f'<section id="my-team-outlook" class="thq-outlook" data-outlook-goals="{choices}" data-dtos-component="recommendation" aria-labelledby="my-team-outlook-title">'
            '<h2 id="my-team-outlook-title">Your roster at a glance</h2>'
            + ''.join(f'<p><b>{label}:</b> {escape(text)}</p>' for label, text in rows)
            + (f'<p><b>Your goal:</b> <span id="my-team-outlook-goal">{escape(outlook["guidance"])}</span></p>' if editable else '') + action
            + '<details id="my-team-outlook-evidence" class="thq-strength-detail"><summary>Why this outlook?</summary><ul>'
            + ''.join(f'<li>{escape(text)}</li>' for text in outlook['details']) + '</ul></details></section>')
