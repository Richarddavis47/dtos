"""Season navigation and disclosure over prepared matchup evidence."""
from html import escape
from urllib.parse import urlencode


def _points(value):
    return "Unavailable" if value is None else f"{value:.2f}"


def render_desk(desk):
    if not desk:
        return ''
    mode = desk['mode']
    label = {'pregame': 'Pregame', 'live': 'In progress', 'postgame': 'Postgame'}[mode]
    text = desk.get('preview_line') or (desk.get('recap') or {}).get('text') or 'Supported commentary unavailable.'
    content = f'<p>{escape(text)}</p>'
    if mode == 'pregame':
        content += '<p>Comparison uses source-listed lineup projections, separately from the optimal lineup shown above.</p>'
        content += ''.join(f'<p>{escape(angle["text"])}</p>' for angle in desk.get('angles', []))
    elif mode == 'live':
        content += f'<p>Periodically refreshed score evidence · observed {escape(str(desk.get("observed_at") or "Unavailable"))}. This is retrieval time; provider update time is unavailable.</p>'
        content += '<p>Players remaining, win probability and lead-change history are unavailable.</p>'
    else:
        for row in desk.get('contributors', []):
            players = ', '.join(escape(pid) for pid in row['player_ids'])
            content += f'<p>Roster {row["roster_id"]}: leading submitted-player score {_points(row["actual"])} · player IDs {players}.</p>'
        content += '<p>Historical legal bench alternatives and pregame expectations are unavailable here; no lineup-mistake or projected-upset claim is made.</p>'
    banter = desk.get('smack_talk')
    if banter:
        content += f'<details><summary>Optional banter</summary><p>{escape(banter["text"])}</p></details>'
    return f'<section class="card season-matchup" data-desk-mode="{mode}"><details><summary>Matchup Desk · {label}</summary>{content}</details></section>'


def week_navigation(calendar: dict, selected: int, overview: list | None = None) -> str:
    weeks = sorted(set(calendar.get("regular_season_weeks") or []) | {
        w for group in calendar.get("playoff_rounds") or [] for w in group
    } | {selected})
    links = []
    for label, candidates in (("Previous week", [w for w in weeks if w < selected]),
                              ("Next week", [w for w in weeks if w > selected])):
        if candidates:
            target = candidates[-1] if label.startswith("Previous") else candidates[0]
            links.append(f'<a class="button" href="/matchups?week={target}">{label}</a>')
    current = calendar.get('current_week')
    if current in weeks and current != selected:
        links.append(f'<a class="button" href="/matchups?week={current}">Current week</a>')
    options = "".join(f'<option value="{w}"{" selected" if w == selected else ""}>Week {w}</option>' for w in weeks)
    week_links = "".join(f'<a href="/matchups?week={w}" aria-label="Browse Week {w}"'
                       f'{" aria-current=page" if w == selected else ""}>Week {w}</a>' for w in weeks)
    schedule = ''.join(f'<li><a href="/matchups?week={item["week"]}">Week {item["week"]}</a> '
                       f'{escape(item["summary"])}</li>' for item in overview or [])
    return ('<link rel="stylesheet" href="/static/css/matchups.css">'
            '<nav class="season-week-nav" aria-label="Matchup week navigation">'
            + "".join(links) + '<form action="/matchups" method="get">'
            f'<label for="matchup-week">Week</label><select id="matchup-week" name="week">{options}</select>'
            '<button type="submit">Go to week</button></form></nav>'
            f'<details class="season-overview"><summary>Season schedule · browse a week</summary><div>{week_links}</div><ul>{schedule}</ul></details>')


def _team_identity(side, *, linked=False):
    name = escape(str(side['team']))
    avatar = str(side.get('avatar') or '')
    image = (f'<img class="matchup-avatar" src="https://sleepercdn.com/avatars/thumbs/{escape(avatar)}" alt="" loading="lazy">'
             if avatar and all(c.isalnum() or c in {'-', '_'} for c in avatar) else '<span class="matchup-avatar initials" aria-hidden="true">' + name[:1] + '</span>')
    title = f'<a href="/teams/{side["roster_id"]}">{name}</a>' if linked else name
    own = '<span class="ds-badge ds-you">You</span>' if side.get('is_viewer') else ''
    return f'<div class="matchup-team">{image}<div><b>{title}</b>{own}<small>{escape(str(side.get("owner") or ""))}</small></div></div>'


def _player_cell(player, week, identity, state, *, starter=False):
    from src.ui import player_summary
    if player is None:
        return '<div class="matchup-player empty">No player in this row</div>'
    pid = player['player_id']
    known = player.get('identity_available', True) and pid and pid != '0' and all(c.isalnum() or c in {'-', '_'} for c in pid)
    content = player_summary(player_id=pid if known else '', name=player['name'], position=player.get('position'),
                             nfl_team=player.get('nfl_team'), context=player.get('status'))
    if known:
        query = urlencode({'week': week, 'matchup': identity})
        content = f'<a class="matchup-player-link" href="/players/{escape(pid)}?{escape(query)}" aria-label="Open {escape(player["name"])} player dossier">{content}</a>'
    else:
        content += '<small>Dossier unavailable</small>' if pid != '0' else ''
    projected = escape(str(player.get('projection_display') or _points(player['projection'])))
    actual = '' if state == 'pregame' else f'<span><small>Actual</small><b>{_points(player["actual"])}</b></span>'
    label = 'Pregame projection · Sleeper' if player['projection'] is not None else 'Projection unavailable'
    return (f'<div class="matchup-player{" battle-side" if starter else ""}">{content}<div class="matchup-player-points">'
            f'{actual}'
            f'<span data-dtos-semantic-field="pregame_projection" data-dtos-availability="{"available" if player["projection"] is not None else "unavailable"}" '
            f'data-dtos-value="{projected if player["projection"] is not None else ""}" '
            f'data-canonical-value="{player["projection"] if player["projection"] is not None else ""}"><small>{label}</small><b>{projected}</b></span></div></div>')


def _aligned_roster(sides, week, identity, state):
    sections = [('lineup', 'Submitted starters'), ('bench', 'Bench · non-scoring'), ('reserve', 'Injured Reserve · non-scoring'), ('taxi', 'Taxi squad · non-scoring')]
    body = '<p class="muted">Actual and Sleeper projected points are separate. Only submitted starters contribute to the official matchup score.</p>'
    for key, label in sections:
        groups = [side.get(key) or [] for side in sides]
        if key in {'reserve', 'taxi'} and not any(groups):
            continue
        body += f'<section class="matchup-roster" data-roster-section="{key}"><h3>{label}</h3>'
        if key == 'bench' and not all(side.get('roster_sections_available') for side in sides):
            body += '<small>Weekly source non-starters shown. Historical/upcoming IR and taxi assignments are unavailable; current assignments are not substituted.</small>'
        if not any(groups):
            body += '<p>No players listed in this source section.</p>'
        for index in range(max(map(len, groups), default=0)):
            rows = [group[index] if index < len(group) else None for group in groups]
            slot = next((p['slot'] for p in rows if p), '') if key == 'lineup' else ''
            cells = ''.join(_player_cell(p, week, identity, state, starter=key == 'lineup') for p in rows)
            body += f'<div class="matchup-roster-row"><div class="matchup-slot">{escape(slot)}</div><div class="matchup-pair">{cells}</div></div>'
        body += '</section>'
    return body


def render_season_week(view: dict, *, matchup_id: str | None = None) -> str:
    week = view['week']
    nav = week_navigation(view['calendar'], week, view.get('overview'))
    heading = f'Week {week} · {view["period"].title()}'
    description = ('Historical source lineups and scores. Current projections are never used as historical pregame evidence.'
                   if view['period'] == 'historical' else 'Official scores and Sleeper submitted-lineup projections, kept separate.')
    if view['round_weeks']:
        heading += ' · Playoff round'
        description += ' Component weeks: ' + ', '.join(map(str, view['round_weeks'])) + '.'
        description += ' Round complete.' if view['round_complete'] else ' Round unresolved until all component weeks finish.'
    body = nav + f'<section class="card matchup-heading"><h2>{escape(heading)}</h2><p>{escape(description)}</p></section>'
    if not view['opponents_locked']:
        return body + '<section class="card"><h3>Playoff opponents not established</h3><p>Projected seeding is not a locked matchup. Playoff-window strength remains opponent-independent.</p><a href="/teams">View team strength</a></section>'
    byes = ''.join(f'<section class="card"><h3><a href="/teams/{side["roster_id"]}">{escape(side["team"])}</a></h3><p>First-round bye · qualified for the playoffs. No opponent or game score is assigned.</p></section>' for side in view.get('byes') or [])
    if view['availability'] != 'available':
        return body + byes + '<section class="card"><h3>Week evidence unavailable</h3><p>This week has not been prepared successfully. Return to a supported week or use the normal league sync.</p></section>'
    cards = []
    ordered = sorted(view['groups'].items(), key=lambda item: (not any(s.get('is_viewer') for s in item[1]), item[0]))
    for identity, sides in ordered:
        if matchup_id is not None and matchup_id != identity:
            continue
        state = view['states'].get(identity, 'pregame')
        status = {'final': 'Final', 'in-game': 'In progress', 'pregame': 'Pregame'}[state]
        if view['round_weeks'] and not view['round_complete'] and state == 'final':
            status = 'Component week final · round unresolved'
        comparison = 'Projection unavailable' if state == 'pregame' else 'Score unavailable'
        if len(sides) == 2:
            values = [s.get('round_actual') if view['round_complete'] and view['round_weeks'] else s['projection'] if state == 'pregame' else s['actual'] for s in sides]
            if all(v is not None for v in values):
                if values[0] == values[1]:
                    comparison = 'Even projected matchup' if state == 'pregame' else 'Final tie' if state == 'final' else 'Scores level'
                else:
                    leader = sides[0 if values[0] > values[1] else 1]['team']
                    comparison = leader + (' wins the round' if view['round_complete'] and view['round_weeks'] else ' leads this component week' if view['round_weeks'] and state == 'final' else ' has the projected edge' if state == 'pregame' else ' wins' if state == 'final' else ' leads')
        blocks = []
        for side in sides:
            actual = f'<span class="matchup-score"><small>{"Final score" if state == "final" else "Actual score"}</small><b>{_points(side["actual"])}</b></span>' if state != 'pregame' else ''
            projected = '<span class="matchup-projected"><small>Pregame projection · Sleeper submitted</small><b>' + _points(side['projection']) + '</b></span>'
            if view['period'] == 'historical':
                projected = '<small>Historical pregame projection: Unavailable</small>'
            elif view['period'] == 'future':
                projected += '<small>Source-listed lineup projection · future submission not established.</small>'
            blocks.append('<section class="matchup-card-side">' + _team_identity(side, linked=matchup_id is not None) + actual + projected + '</section>')
        coverage = ' · '.join(f'{s["team"]}: {s["supported_slots"]}/{s["expected_slots"]} projected slots' for s in sides)
        partial = '<small class="matchup-warning">Incomplete projection coverage · projected leader unavailable</small>' if state == 'pregame' and any(s['projection'] is None for s in sides) else ''
        unassigned = '<p>Opponent unassigned. This alone does not establish a playoff bye or elimination.</p>' if len(sides) < 2 else ''
        bracket = (view.get('bracket_labels') or {}).get(identity, '')
        bracket_label = f'<small>{escape(bracket)}</small>' if bracket else ''
        content = f'<div class="matchup-status">{status} · {escape(comparison)}</div>{bracket_label}<div class="season-sides">{"".join(blocks)}</div>{partial}{unassigned}'
        if matchup_id is None:
            label = 'Open Week ' + str(week) + ' matchup: ' + ' versus '.join(s['team'] for s in sides)
            content = f'<a class="matchup-card-link" aria-label="{escape(label)}" href="/matchups/{escape(identity)}?week={week}">{content}</a>'
        else:
            content = f'<a class="back" href="/matchups?week={week}">All Week {week} matchups</a>' + content + _aligned_roster(sides, week, identity, state)
        technical = '<details class="matchup-evidence"><summary>Lineup and projection evidence</summary><p>' + escape(coverage) + '</p>'
        if view['period'] != 'historical':
            for side in sides:
                optimal = side.get('optimal') or {}
                technical += f'<h4>{escape(side["team"])}</h4><p>Optimal legal lineup projection: <b>{_points(optimal.get("projected_points") if optimal.get("available") else None)}</b> · DTOS-derived; not the submitted lineup.</p>'
                if side['coverage'] == 'partial':
                    technical += f'<p>Known-starter subtotal: {_points(side["known_subtotal"])} — not a complete team projection.</p>'
                if optimal.get('entries'):
                    technical += '<p>Optimal projected starters · not the submitted lineup</p><ul>' + ''.join(f'<li>{escape(e["slot"])} · {escape(e["label"])}</li>' for e in optimal['entries']) + '</ul>'
        for side in sides:
            if side.get('round_scores'):
                technical += '<h4>' + escape(side['team']) + '</h4><p>Complete round score: <b>' + _points(side.get('round_actual')) + '</b></p>'
                technical += '<p>' + ' · '.join(f'Week {r["week"]}: {_points(r["actual"])}' for r in side['round_scores']) + '</p>'
        technical += '<p>No supported win probability or remaining-game estimate is available. Projected points are not odds.</p></details>'
        cards.append('<article class="card season-matchup">' + content + technical + '</article>')
    if not cards and not byes:
        cards.append('<section class="card"><h3>No source matchups published for this week</h3><p>Matchup not published in this week. Choose a supported week; no opponents or results are inferred.</p></section>')
    if view.get('viewer_roster_id') and not any(s.get('is_viewer') for sides in view['groups'].values() for s in sides) and not any(s['roster_id'] == view['viewer_roster_id'] for s in view.get('byes') or []):
        body += '<p class="matchup-warning">Your franchise has no published matchup in this week.</p>'
    return body + byes + ''.join(cards) + f'<details class="matchup-evidence"><summary>Source and coverage</summary><p>Sleeper · observed {escape(str(view["observed_at"] or "Unavailable"))}. Observation is retrieval time, not a provider update timestamp.</p><p>Projection generation: {escape(str(view["projection_generation"] or "Unavailable"))}</p></details>'
