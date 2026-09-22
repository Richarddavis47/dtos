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


def _players(rows: list, week: int, period: str, state: str) -> str:
    items = []
    for player in rows:
        pid = player["player_id"]
        label = escape(player["name"])
        if pid and pid != '0' and all(c.isalnum() or c in {'-', '_'} for c in pid):
            label = f'<a class="matchup-player-link" href="/players/{escape(pid)}" aria-label="Open {label} player dossier">{label}</a>'
        # A dossier week deep-link is added only when its actual handler supports
        # it. Do not silently send a future context to a current-only consumer.
        projected = escape(str(player["projection_display"] or _points(player["projection"])))
        availability = 'unavailable' if player['projection'] is None else 'available'
        projection_label = f'Pregame projection: {projected}' if availability == 'available' else 'Projection unavailable'
        items.append(f'<li><div class="battle-side"><span>{escape(player["slot"])} · {label}</span>'
                     + (f'<div data-dtos-semantic-field="pregame_projection" data-dtos-availability="{availability}" '
                        f'data-dtos-value="{projected if availability == "available" else ""}">{projection_label} · Week {week} · Sleeper</div>' if period != "historical" else '')
                     + (f'<span>Actual: {_points(player["actual"])}</span>' if state != 'pregame' else '') + '</div></li>')
    return '<ul class="season-starters">' + ''.join(items) + '</ul>'


def render_season_week(view: dict, *, matchup_id: str | None = None) -> str:
    week = view["week"]
    nav = week_navigation(view["calendar"], week, view.get("overview"))
    heading = f'Week {week} · {view["period"].title()}'
    description = 'Source-reported lineups and scores. Projections remain scoped to this week and league.'
    if view["period"] == "historical":
        description = 'Historical source lineups and scores. Current projections are never used as historical pregame evidence.'
    if view["round_weeks"]:
        heading += ' · Playoff round'
        description += ' One round, component weeks: ' + ', '.join(map(str, view["round_weeks"])) + '.'
        description += ' Round complete.' if view["round_complete"] else ' Round unresolved until all component weeks finish.'
    body = nav + f'<section class="card"><h2>{escape(heading)}</h2><p>{escape(description)}</p></section>'
    if not view["opponents_locked"]:
        return body + ('<section class="card"><h3>Playoff opponents not established</h3>'
                       '<p>Projected seeding is not a locked matchup. Playoff-window strength remains opponent-independent.</p>'
                       '<a href="/teams">View team strength</a></section>')
    byes = ''.join(f'<section class="card"><h3><a href="/teams/{side["roster_id"]}">{escape(side["team"])}</a></h3>'
                   '<p>First-round bye · qualified for the playoffs. No opponent or game score is assigned.</p></section>'
                   for side in view.get("byes") or [])
    if view["availability"] != "available":
        return body + byes + ('<section class="card"><h3>Week evidence unavailable</h3>'
                       '<p>This week has not been prepared successfully. Return to a supported week or use the normal league sync.</p></section>')
    if not view["groups"] and not byes:
        return body + '<section class="card"><h3>No source matchups published for this week</h3><p>No opponents or results are inferred.</p></section>'
    cards = []
    for identity, sides in sorted(view["groups"].items()):
        if matchup_id is not None and matchup_id != identity:
            continue
        content = []
        state = (view.get("states") or {}).get(identity, "pregame")
        status = {"final": "Final", "in-game": "In progress", "pregame": "Pregame"}[state]
        if view['round_weeks'] and not view['round_complete'] and state == 'final':
            status = 'Component week final · round unresolved'
        comparison = 'Projection unavailable' if state == 'pregame' else 'Score unavailable'
        if len(sides) == 2:
            values = [side.get('round_actual') if view['round_complete'] and view['round_weeks'] else
                      ((side.get('optimal') or {}).get('projected_points') if (side.get('optimal') or {}).get('available') else None)
                      if view['period'] == 'future' else side['projection'] if state == 'pregame' else side['actual'] for side in sides]
            if all(value is not None for value in values):
                if values[0] == values[1]:
                    comparison = 'Even projected matchup' if state == 'pregame' else 'Final tie' if state == 'final' else 'Scores level'
                else:
                    leader = sides[0 if values[0] > values[1] else 1]['team']
                    comparison = leader + (' wins the round' if view['round_complete'] and view['round_weeks'] else
                        ' leads this component week' if view['round_weeks'] and state == 'final' else
                        ' has the optimal projected edge' if view['period'] == 'future' else ' has the projected edge' if state == 'pregame' else ' wins' if state == 'final' else ' leads')
        for side in sides:
            rid = side["roster_id"]
            name = escape(side["team"])
            score = '' if state == 'pregame' else f'<p>{"Final score" if view["period"] == "historical" else "Actual score"}: <b>{_points(side["actual"])}</b></p>'
            projection = f'<p>Pregame projection · submitted/source lineup: <b>{_points(side["projection"])}</b></p>'
            if view['period'] == 'future':
                projection = f'<p>Source-listed lineup projection: <b>{_points(side["projection"])}</b> · not a future lineup submission.</p>'
            if view["period"] == "historical":
                projection = '<p>Historical pregame projection: Unavailable</p>'
            optimal = side.get('optimal') or {}
            if view['period'] != 'historical':
                projection += f'<p>Optimal legal lineup projection: <b>{_points(optimal.get("projected_points") if optimal.get("available") else None)}</b></p>'
                if not optimal:
                    projection += '<small>A compatible prepared optimal lineup is not available; no calculation is run on this page.</small>'
            if side.get('round_scores'):
                projection += '<p>Complete round score: <b>' + _points(side.get('round_actual')) + '</b></p>'
                projection += '<p>' + ' · '.join(f'Week {item["week"]}: {_points(item["actual"])}' for item in side['round_scores']) + '</p>'
            coverage = (f'{side["supported_slots"]}/{side["expected_slots"]} projected slots · {side["coverage"]}'
                        if view['period'] != 'historical' else 'Historical source lineup · pregame projection not retained here')
            subtotal = (f'<p>Known-starter subtotal: {_points(side["known_subtotal"])} — not a complete team projection.</p>'
                        if side["coverage"] == "partial" else '')
            lineup = ''
            if matchup_id is not None:
                lineup = _players(side['lineup'], week, view['period'], state) if side['lineup'] else '<p>Source starters unavailable; current roster is not substituted.</p>'
                if side.get('bench'):
                    lineup += '<details><summary>Source non-starters</summary><p>IR/taxi classification is unavailable in this weekly source.</p>' + _players(side['bench'], week, view['period'], state) + '</details>'
                if optimal.get('entries'):
                    entries = ''.join(f'<li>{escape(entry["slot"])} · <a class="matchup-player-link" href="/players/{escape(entry["asset_id"])}">{escape(entry["label"])}</a></li>' for entry in optimal['entries'])
                    lineup += f'<details><summary>Optimal projected starters</summary><p>Not the submitted lineup. Based on this week’s supported projections and current roster eligibility.</p><ul>{entries}</ul></details>'
            content.append(f'<section><h3><a href="/teams/{rid}">{name}</a></h3>{score}{projection}<small>{escape(coverage)}</small>{subtotal}{lineup}</section>')
        query = urlencode({"week": week})
        link = f'<a href="/matchups/{escape(identity)}?{query}">Open matchup · Week {week}</a>' if matchup_id is None else f'<a href="/matchups?{query}">All Week {week} matchups</a>'
        unassigned = '<p>Opponent unassigned. This alone does not establish a playoff bye or elimination.</p>' if len(sides) < 2 else ''
        bracket = (view.get('bracket_labels') or {}).get(identity, '')
        cards.append(f'<article class="card season-matchup"><h3>{status} · {escape(comparison)}</h3><small>{escape(bracket)}</small>'
                     f'<div class="season-sides">{"".join(content)}</div>{unassigned}{link}</article>')
    if not cards and not byes:
        cards.append('<section class="card"><h3>Matchup not published in this week</h3><p>Choose a matchup from the selected week.</p></section>')
    return body + byes + ''.join(cards) + f'<details><summary>Source and coverage</summary><p>Sleeper · observed {escape(str(view["observed_at"] or "Unavailable"))}. Observation is retrieval time, not a provider update timestamp.</p></details>'
