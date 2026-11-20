"""Compact disclosure for the prepared two-week bye outlook."""
from html import escape
from urllib.parse import quote, urlencode


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


def upcoming_byes_panel(weeks, players, *, active, league_id=None, season=None, roster_id=None):
    if not active:
        return ''
    if not weeks:
        return ('<section class="thq-section" id="upcoming-byes"><h2>Upcoming bye weeks</h2>'
                '<p>Future-week roster coverage is unavailable for this lineup snapshot.</p></section>')
    order = {'shortfall': 0, 'unknown': 1, 'conditional': 2, 'covered': 3, 'no_gap': 4}
    priority = sorted(weeks, key=lambda row: (order[row['state']], row['week']))
    names = {str(player['id']): escape(player.get('name') or 'Unnamed player') for player in players}
    pickup_links = []
    for row in priority:
        if row['state'] != 'shortfall' or not (league_id and season and roster_id):
            continue
        week = row['week']
        query = urlencode(dict(bye_week=week, market_league=league_id, season=season, from_team=roster_id,
                               availability='day_traders_free_agent'))
        needs = _slots(dict.fromkeys(row['unfilled']))
        pickup_links.append(f'<a class="thq-action" id="bye-pickup-{week}" href="/market?{escape(query)}">'
                            f'Find Week {week} {needs} cover</a>')

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
        + ('<div class="thq-actions">' + ''.join(pickup_links) + '</div>' if pickup_links else '') +
        '<details class="thq-strength-detail"><summary>See weeks and possible moves</summary>'
        '<p>This plan uses the latest prepared roster and NFL schedule. It shows who fits together under your league’s rules. '
        'Check player availability again before setting your Sleeper lineup.</p>'
        + ''.join(detail(row, leading=index == 0) for index, row in enumerate(priority)) + '</details></section>'
    )


def bye_pickup_panel(row, ownership, *, origin, league_id, roster_id):
    cards = []
    shortage = len(row['unfilled'])
    for candidate in row['pickups']['candidates']:
        pid = candidate['player_id']
        if ownership.resolve(pid)['state'] != 'FREE_AGENT':
            continue
        catalog = ownership.players[pid]
        name = escape(str(catalog.get('full_name') or catalog.get('name') or pid))
        positions = _slots(candidate['positions'])
        slot, gap = _slot_name(candidate['slot']), _slot_name(candidate['gap'])
        fit = (f'Can fill one {gap} opening by starting at {slot} and moving eligible roster players.'
               if slot != gap else f'Can fill one {gap} opening.')
        points = candidate['points']
        projection = 'Sleeper projection unavailable.' if points is None else f'Sleeper projection: {points:.2f} pts.'
        if points is not None and candidate['projection_freshness'] in {'Aging', 'Stale'}:
            projection += f" Projection freshness: {candidate['projection_freshness'].lower()}."
        status = (_status_dependency(name, candidate['status'])
                  if candidate['status'] != 'active' else '')
        href = '/players/' + quote(pid, safe='') + '?' + urlencode(
            dict(from_market=origin, market_league=league_id, front_office=roster_id))
        cards.append(f'<article class="card"><h3><a href="{escape(href)}">{name}</a></h3>'
                     f'<p>{positions} · Unrostered in this league</p><p>{fit} {projection}</p>'
                     + (f'<p>{status}</p>' if status else '') + '</article>')
    if not cards:
        cards.append('<p>No confirmed unrostered player has a supported lineup fit in the prepared evidence.</p>')
    coverage = (f'Each result covers one opening. This roster has {shortage}, so one pickup cannot fill them all.'
                if shortage > 1 else 'Each result can cover the opening in a legal lineup.')
    return (f'<section id="bye-pickup-results" class="ux-section"><h2>Week {row["week"]} bye cover</h2>'
            f'<p>Unfilled slots: {_slots(row["unfilled"])}.</p>'
            + (f'<p>{coverage}</p>' if row['pickups']['candidates'] else '')
            + '<p>These fits use the prepared roster and NFL schedule. Verify who can play and whether waivers '
              'or locks apply in Sleeper. Use Sleeper for all lineup changes, adds, drops, and claims.</p>'
            + f'<p>{_status_age(row)}</p><div class="market-grid">{"".join(cards)}</div>'
            '<p><a href="/market?availability=day_traders_free_agent">Browse all Market free agents</a></p></section>')
