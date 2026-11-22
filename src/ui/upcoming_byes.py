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
        '<details class="thq-strength-detail" id="bye-week-details" data-nav-disclosure><summary>See weeks and possible moves</summary>'
        '<p>This plan uses the latest prepared roster and NFL schedule. It shows who fits together under your league’s rules. '
        'Check player availability again before setting your Sleeper lineup.</p>'
        + ''.join(detail(row, leading=index == 0) for index, row in enumerate(priority)) + '</details></section>'
    )


def _pickup_ir_note(evidence, roster_space, player_name):
    def name(player_id):
        roster_name = evidence.get('names', {}).get(player_id)
        return escape(str(roster_name)) if roster_name else player_name(player_id)

    blocked = evidence['blockers']
    note = ''
    if blocked:
        subject = ', '.join(name(player_id) for player_id in blocked)
        verb = 'is' if len(blocked) == 1 else 'are'
        note = (f'<p><strong>Sleeper IR blocker</strong> · {subject} {verb} no longer eligible for IR. '
                'Sleeper blocks adds and waiver claims until this is resolved.')
        if 'capacity' in roster_space:
            open_spots = roster_space['capacity'] - roster_space['active']
            remaining = open_spots - len(blocked)
            if remaining < 0:
                note += ' You would need to make room to move everyone out of IR and add this pickup.'
            elif remaining == 0:
                note += ' Moving out of IR would use the last open active spot. You would then need to make room for this pickup.'
            else:
                spots = 'spot' if remaining == 1 else 'spots'
                note += f' If moved to the active roster, {remaining} active {spots} would remain.'
        note += '</p>'
    if evidence['limits']:
        limits = ' and '.join(escape(reason) + (f' for {name(pid)}' if pid else '')
                              for reason, pid in evidence['limits'])
        note += f'<p><strong>IR eligibility unconfirmed</strong> · {limits}. Check Sleeper before adding.</p>'
    return note


def bye_pickup_panel(row, ownership, *, origin, league_id, roster_id, roster_space, ir_evidence):
    cards = []
    shortage = len(row['unfilled'])
    fresh = row['availability_freshness'] == 'Fresh'
    slots = row['slots']
    recorded = row['pickups']['candidates']
    space_detail = roster_space.get('reason')
    if space_detail:
        space = 'Could not confirm an open spot.'
    else:
        active, capacity = roster_space['active'], roster_space['capacity']
        space = ('Open active spot' if active < capacity else 'Make room before adding')
        space += f' · {active} of {capacity} active spots used.'
        space_detail = 'Roster space reflects this Sleeper snapshot. IR and taxi vacancies do not count as active spots.'

    def player_name(player_id):
        catalog = ownership.players.get(player_id) or {}
        return escape(str(catalog.get('full_name') or catalog.get('name') or player_id))

    ir_note = _pickup_ir_note(ir_evidence, roster_space, player_name)
    for candidate in recorded:
        pid = candidate['player_id']
        if 'dependencies' not in candidate or ownership.resolve(pid)['state'] != 'FREE_AGENT':
            continue
        name = player_name(pid)
        positions = _slots(candidate['positions'])
        slot, gap = _slot_name(candidate['slot']), _slot_name(candidate['gap'])
        fit = (f'Can fill one {gap} opening by starting at {slot} and moving eligible roster players.'
               if slot != gap else f'Can fill one {gap} opening.')
        points = candidate['points']
        projection = 'Sleeper projection unavailable.' if points is None else f'Sleeper projection: {points:.2f} pts.'
        if points is not None and candidate['projection_freshness'] in {'Aging', 'Stale'}:
            projection += f" Projection freshness: {candidate['projection_freshness'].lower()}."
        dependencies = candidate['dependencies']
        conditional = bool(dependencies) or not fresh
        moves = []
        for destination, player, prior in candidate['moves']:
            label = player_name(player)
            target = _indexed_slot(slots, destination)
            instruction = (f'Start {label} at {target}.' if prior is None else
                           f'Move {label} from {_indexed_slot(slots, prior)} to {target}.')
            moves.append(f'<li>{instruction}</li>')
        moved_players = {player for _, player, _ in candidate['moves']}
        notes = ''
        for destination, player, status in dependencies:
            label = player_name(player)
            stays = f'{label} stays at {_indexed_slot(slots, destination)}. ' if player not in moved_players else ''
            notes += f'<li>{stays}{_status_dependency(label, status)}</li>'
        if conditional:
            fit = f'Conditional cover for one {gap} opening. This plan depends on player availability.'
        if not fresh:
            status_limit = row['availability_freshness'].lower()
            moved = ', '.join(player_name(player) for _, player, _ in candidate['moves'])
            notes += f'<li>Player status check is {status_limit}. Recheck the lineup, including {moved}.</li>'
        href = '/players/' + quote(pid, safe='') + '?' + urlencode(
            dict(from_market=origin, market_league=league_id, front_office=roster_id))
        cards.append(f'<article class="card"><h3><a href="{escape(href)}">{name}</a></h3>'
                     f'<p>{positions} · Unrostered in this league</p><p>{fit} {projection}</p>'
                     + f'<p><strong>Roster space</strong> · {escape(space)}</p>'
                     + ir_note
                     + f'<details{" open" if conditional else ""}><summary>Lineup moves and availability</summary>'
                     + f'<ul>{"".join(moves)}{notes}</ul></details></article>')
    has_cards = bool(cards)
    if not has_cards:
        reason = ('Lineup availability has not been prepared for this snapshot.'
                  if recorded and all('dependencies' not in candidate for candidate in recorded)
                  else 'No confirmed unrostered player has a supported lineup fit in the prepared evidence.')
        cards.append(f'<p>{reason}</p>')
    coverage = (f'This roster has {shortage} openings, so one pickup cannot fill them all.'
                if shortage > 1 else 'Each plan addresses one opening.')
    return (f'<section id="bye-pickup-results" class="ux-section"><h2>Week {row["week"]} bye cover</h2>'
            f'<p>Unfilled slots: {_slots(row["unfilled"])}.</p>'
            + (f'<p>{coverage} {escape(space_detail)}</p>' if has_cards else '')
            + '<p>These fits use the prepared roster and NFL schedule. Verify who can play and whether waivers '
              'or locks apply in Sleeper. Use Sleeper for all lineup changes, adds, drops, and claims.</p>'
            + f'<p>{_status_age(row)}</p><div class="market-grid">{"".join(cards)}</div>'
            '<p><a href="/market?availability=day_traders_free_agent">Browse all Market free agents</a></p></section>')
