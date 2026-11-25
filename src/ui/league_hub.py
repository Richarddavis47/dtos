"""Compact League navigation and a prepared score preview."""
from html import escape
from urllib.parse import urlencode

from src.core.intelligence.season_calendar import matchup_calendar
from src.core.player_value_projection.sleeper_actuals import actual_display


def league_week_heading(data, selected):
    calendar = matchup_calendar(data.get("league") or {}, data.get("week") or 1, data.get("nfl_state"))
    weeks = sorted(set(calendar.get("regular_season_weeks") or []) | {
        week for group in calendar.get("playoff_rounds") or [] for week in group
    } | {selected})
    index = weeks.index(selected)

    def arrow(label, symbol, target):
        if target is None:
            return f'<span class="league-week-unavailable" aria-hidden="true">{symbol}</span>'
        return f'<a href="/league?week={target}" aria-label="{label}, Week {target}">{symbol}</a>'

    previous = arrow("Previous matchup week", "‹", weeks[index - 1] if index else None)
    following = arrow("Next matchup week", "›", weeks[index + 1] if index + 1 < len(weeks) else None)
    return ('<header class="league-heading"><h1>League</h1>'
            f'<nav aria-label="Matchup preview week">{previous}<strong>Week {selected}</strong>{following}</nav></header>')


def matchup_preview(week, view, viewer):
    all_href = f'/matchups?week={week}'
    heading = (f'<div class="league-section-heading"><h2 id="league-matchup-title">Week {week} matchups</h2>'
               f'<a href="{all_href}">All matchups</a></div>')
    identity, sides = next(iter(view.get("groups", {}).items()), (None, []))
    if identity is None or view.get("availability") != "available":
        if not viewer:
            note = "Select your franchise to see its matchup here."
        elif not view["opponents_locked"]:
            note = "Playoff opponents are not confirmed for this week."
        elif any(row["roster_id"] == viewer for row in view.get("byes", [])):
            note = "Your franchise has a confirmed first-round bye."
        elif view["availability"] != "available":
            note = "Matchup evidence is unavailable for this week."
        else:
            note = "A matchup for your team has not been confirmed for this week."
        content = f'<p class="card">{note}</p>'
    else:
        state = view["states"][identity]
        label = {"pregame": "Projected points", "in-game": "Live score", "final": "Final score"}[state]
        scores = []
        for side in sides:
            value = side["projection"] if state == "pregame" else side["actual"]
            score = ('—' if value is None else f'{value:.2f}' if state == "pregame" else actual_display(value))
            missing = ''
            if value is None and state == 'pregame':
                missing = f'<small>Projection incomplete · {side["supported_slots"]}/{side["expected_slots"]} slots</small>'
            elif value is None:
                missing = '<small>Score unavailable</small>'
            name = escape(str(side["team"]))
            scores.append(f'<div><b>{name}</b><strong>{score}</strong>{missing}</div>')
        query = urlencode({"week": week})
        href = f'/matchups/{escape(identity, quote=True)}?{query}'
        future = '<small>Based on the source-listed lineup. Future submissions may change.</small>' if view["period"] == "future" else ''
        content = (f'<div class="card league-matchup-preview" data-game-state="{state}">'
                   f'<div class="league-score-pair">{"".join(scores)}</div><p>{label}</p>{future}'
                   f'<a class="ux-primary-action" href="{href}">View matchup</a></div>')
    return f'<section class="league-matchup" aria-labelledby="league-matchup-title">{heading}{content}</section>'
