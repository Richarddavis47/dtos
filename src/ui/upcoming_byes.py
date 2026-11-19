"""Compact disclosure for the prepared two-week bye outlook."""
from html import escape


def _slot_name(slot):
    return 'Superflex' if slot in {'SUPER_FLEX', 'SF'} else slot.replace('_', ' ')


def _slots(slots):
    return escape(', '.join(map(_slot_name, slots)))


def _indexed_slot(slots, index):
    slot = slots[index]
    name = _slot_name(slot)
    if slots.count(slot) > 1:
        name += f' {slots[:index + 1].count(slot)}'
    return escape(name)


def _status_age(row):
    minutes = row.get('availability_age_minutes')
    if minutes is None:
        return 'The time of the Sleeper status check is unavailable.'
    if minutes < 1:
        age = 'less than a minute ago'
    else:
        count, unit = ((minutes // 1440, 'day') if minutes >= 1440 else
                       (minutes // 60, 'hour') if minutes >= 60 else (minutes, 'minute'))
        age = f"{count} {unit}{'s' if count != 1 else ''} ago"
    note = ' That check is stale.' if row.get('availability_freshness') == 'Stale' else ''
    return f'Sleeper player status checked {age}.{note}'


def _status_dependency(name, status):
    labels = {'ir': 'on injured reserve', 'pup': 'on PUP', 'out': 'out', 'inactive': 'inactive',
              'suspended': 'suspended', 'retired': 'retired', 'questionable': 'questionable', 'doubtful': 'doubtful'}
    if status in labels:
        return f'Sleeper listed {name} as {labels[status]} at the status check.'
    return f'{name} has unconfirmed availability.'


def upcoming_byes_panel(weeks, players, *, active):
    if not active:
        return ''
    if not weeks:
        return ('<section class="thq-section" id="upcoming-byes"><h2>Upcoming bye weeks</h2>'
                '<p>Future-week roster coverage is unavailable for this lineup snapshot.</p></section>')
    order = {'shortfall': 0, 'unknown': 1, 'conditional': 2, 'covered': 3, 'no_gap': 4}
    priority = sorted(weeks, key=lambda row: (order[row['state']], row['week']))
    names = {str(player['id']): escape(player.get('name') or 'Unnamed player') for player in players}

    def finding(row):
        week = f"Week {row['week']}"
        positions = _slots(dict.fromkeys(row['slots'][index] for index, _ in row['bye_starters']))
        if row['state'] == 'shortfall':
            return f"{week} · Bye affects {positions}. This roster cannot fill every starting spot with its current eligible slots."
        if row['state'] == 'conditional':
            return f"{week} · Legal cover for the {positions} bye depends on player availability."
        if row['state'] == 'covered':
            return f"{week} · A legal lineup change can cover the {positions} bye."
        if row['state'] == 'unknown':
            if positions:
                return f"{week} · Bye affects {positions}. The roster and schedule do not confirm full cover."
            return f"{week} · Schedule or roster coverage is incomplete."
        return f"{week} · No starters on bye."

    def detail(row, *, leading):
        slots = row['slots']
        absent = ''.join(
            f'<li data-bye-starter="{escape(pid, quote=True)}" data-slot-index="{index}">'
            f'{names.get(pid, "Unnamed player")} is on bye in {_indexed_slot(slots, index)}.</li>'
            for index, pid in row['bye_starters']
        )
        moves = []
        for index, pid, prior in row['moves']:
            name = names.get(pid, 'Unnamed player')
            destination = _indexed_slot(slots, index)
            instruction = (f'Start {name} at {destination}.' if prior is None else
                           f'Move {name} from {_indexed_slot(slots, prior)} to {destination}.')
            moves.append(f'<li data-bye-move="{escape(pid, quote=True)}" data-slot-index="{index}">{instruction}</li>')
        if row['state'] == 'conditional':
            instruction_heading = 'Use this lineup only if all its players are available.'
        else:
            instruction_heading = 'Make this change.' if len(moves) == 1 else 'Make these changes together.'
        dependencies = ''.join(
            f'<li>{_status_dependency(names.get(pid, "Unnamed player"), status)}</li>'
            for pid, status in row['availability_dependencies']
        )
        vacancy = _slots(row['unfilled'])
        notes = (
            (f'<ul>{absent}</ul>' if absent else '')
            + (f'<p>{instruction_heading}</p><ul>{"".join(moves)}</ul><p>{_status_age(row)}</p>' if moves else '')
            + (f'<ul>{dependencies}</ul>' if dependencies else '')
            + (f'<p>One legal fit leaves {vacancy} unfilled.</p>' if vacancy else '')
            + ('<p>A complete projected lineup is unavailable for this week.</p>'
               if not row['projection_ready'] else '')
        )
        href = f'/matchups?week={row["week"]}'
        heading = f"Week {row['week']} details" if leading else finding(row)
        return (f'<section data-bye-week="{row["week"]}" data-bye-state="{row["state"]}">'
                f'<h3>{heading}</h3>{notes}'
                f'<a class="thq-record-link" href="{href}">View Week {row["week"]} Matchups</a></section>')

    return (
        '<section class="thq-section" id="upcoming-byes"><h2>Upcoming bye weeks</h2>'
        f'<p>{finding(priority[0])}</p>'
        '<details class="thq-strength-detail"><summary>See weeks and possible moves</summary>'
        '<p>This plan uses the latest prepared roster and NFL schedule. It shows who fits together under your league’s rules. '
        'Check player availability again before setting your Sleeper lineup.</p>'
        + ''.join(detail(row, leading=index == 0) for index, row in enumerate(priority)) + '</details></section>'
    )
