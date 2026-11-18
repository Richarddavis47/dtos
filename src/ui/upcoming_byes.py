"""Compact disclosure for the prepared two-week bye outlook."""
from html import escape


def _slots(slots):
    return escape(', '.join(
        'Superflex' if slot in {'SUPER_FLEX', 'SF'} else slot.replace('_', ' ')
        for slot in slots
    ))


def upcoming_byes_panel(weeks, players, *, active):
    if not active:
        return ''
    if not weeks:
        return ('<section class="thq-section" id="upcoming-byes"><h2>Upcoming bye weeks</h2>'
                '<p>Future-week roster coverage is unavailable for this lineup snapshot.</p></section>')
    order = {'shortfall': 0, 'unknown': 1, 'covered': 2, 'no_gap': 3}
    priority = sorted(weeks, key=lambda row: (order[row['state']], row['week']))
    names = {str(player['id']): escape(player.get('name') or 'Unnamed player') for player in players}

    def finding(row):
        week = f"Week {row['week']}"
        positions = _slots(row['affected'])
        if row['state'] == 'shortfall':
            return f"{week} · Bye affects {positions}. This roster cannot fill every starting spot."
        if row['state'] == 'covered':
            return f"{week} · The roster has legal cover for {positions}."
        if row['state'] == 'unknown':
            if positions:
                return f"{week} · Bye affects {positions}. Replacement coverage is unconfirmed."
            return f"{week} · Schedule or roster coverage is incomplete."
        return f"{week} · No material bye gap identified."

    def detail(row, *, leading):
        bye_names = ', '.join(names.get(pid, 'Unnamed player') for pid in row['byes'])
        moves = ''.join(f'<li>{_slots([slot])} — {names.get(pid, "Unnamed player")}</li>'
                        for slot, pid in row['moves'])
        vacancy = _slots(row['unfilled'])
        notes = (
            (f'<p>Players on bye in this planning lineup: {bye_names}.</p>' if bye_names else '')
            + (f'<p>One legal set of changes:</p><ul>{moves}</ul>' if moves else '')
            + (f'<p>Unfilled in one best legal fit: {vacancy}.</p>' if vacancy else '')
            + ('<p>A complete projected lineup is unavailable for this week.</p>'
               if not row['projection_ready'] else '')
        )
        href = f'/matchups?week={row["week"]}'
        heading = f"Week {row['week']} details" if leading else finding(row)
        return (f'<h3>{heading}</h3>{notes}'
                f'<a class="thq-record-link" href="{href}">View Week {row["week"]} Matchups</a>')

    return (
        '<section class="thq-section" id="upcoming-byes"><h2>Upcoming bye weeks</h2>'
        f'<p>{finding(priority[0])}</p>'
        '<details class="thq-strength-detail"><summary>See weeks and possible moves</summary>'
        '<p>This plan uses the latest prepared roster and NFL schedule. It shows who fits together under your league’s rules. '
        'Check player availability again before setting your Sleeper lineup.</p>'
        + ''.join(detail(row, leading=index == 0) for index, row in enumerate(priority)) + '</details></section>'
    )
