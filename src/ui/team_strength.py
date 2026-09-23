"""Compact scoped strength display; no generic grade or hidden partial total."""
from html import escape
from urllib.parse import quote


def strength_panel(profile: dict | None, *, league_id: str | None = None, roster_id: int | None = None,
                   players: list[dict] | None = None) -> str:
    if not profile:
        return '<section class="thq-section"><h2>Projected Team Strength</h2><p>Compatible multi-week evidence is not prepared.</p></section>'
    explanation = ''
    if league_id is not None and roster_id is not None:
        from services.team_fois_explanations import team_strength_explanation
        from src.ui.explanations import explanation_panel
        explanation = explanation_panel(team_strength_explanation(profile, league_id=league_id, roster_id=roster_id))
    names = {str(player['id']): str(player.get('name') or player['id']) for player in players or []}

    def player_link(pid):
        return f'<a href="/players/{quote(str(pid), safe="")}">{escape(names.get(str(pid), str(pid)))}</a>'

    cards = []
    labels = {'current_week': 'Current-week strength', 'next_n': 'Next-N strength',
              'rest_of_regular_season': 'Rest of regular season', 'playoff_window': 'Playoff-window strength'}
    for key, label in labels.items():
        row = profile['horizons'][key]
        supported, requested = row['weeks_supported'], row['weeks_requested']
        total = row['total']
        value = 'Unavailable' if total is None else f'{total:.2f} points'
        coverage = f'{len(supported)}/{len(requested)} weeks' if requested is not None else 'Calendar unavailable'
        partial = row.get('supported_week_subtotal')
        note = (f'Partial supported subtotal: {partial:.2f}; not a complete horizon.' if partial is not None
                else 'Complete projection unavailable for this horizon.') if total is None else 'Sum of complete weekly optimal lineups.'
        rank = row.get('league_rank')
        confidence = row.get('source_confidence_range')
        confidence_note = ('Source evidence support: ' + escape('–'.join(map(str, confidence)))
                           + '; not an outcome probability.') if confidence else 'Source confidence unavailable.'
        cards.append(f'<article class="thq-kpi"><span>{escape(label)}</span><b>{value}</b><p>{coverage}</p><small>{note}</small>'
                     + (f'<p>{escape(label)} rank: #{rank}</p>' if rank is not None else '<p>Comparable league rank unavailable</p>')
                     + f'<p>{confidence_note}</p></article>')
    current_weeks = profile['horizons']['current_week'].get('weeks_requested') or []
    current_week = current_weeks[0] if len(current_weeks) == 1 else None
    weekly = profile.get('weekly') or {}
    current = weekly.get(current_week) or weekly.get(str(current_week)) or {}
    optimal = current.get('optimal') or {}
    entries = optimal.get('entries') or []
    lineup_html = '<p>Current-week optimal lineup is unavailable.</p>'
    if entries:
        selected = {str(entry['asset_id']) for entry in entries}
        submitted = profile.get('actual_submitted_starter_ids')
        comparison = 'Submitted-lineup comparison unavailable.'
        if submitted is not None:
            actual = set(map(str, submitted))
            if selected == actual and optimal.get('available'):
                comparison = 'These players match the submitted starters.'
            else:
                incoming = ', '.join(player_link(pid) for pid in sorted(selected - actual)) or 'None'
                outgoing = ', '.join(player_link(pid) for pid in sorted(actual - selected)) or 'None'
                comparison = f'In the supported optimal lineup, not submitted: {incoming}. Submitted, not in this optimal lineup: {outgoing}.'
        rows = ''.join(f'<li>{escape(str(entry["slot"]))} · {player_link(entry["asset_id"])} · '
                       f'{escape(str(entry["projected_points"]))} projected points</li>' for entry in entries)
        availability = 'Complete legal projected lineup.' if optimal.get('available') else 'Partial lineup only; missing evidence prevents a complete team projection.'
        lineup_html = f'<p>Week {current_week} · {availability}</p><p>{comparison}</p><ul class="thq-optimal">{rows}</ul>'
    lineup_html = ('<details class="thq-strength-detail"><summary>Current-week optimal lineup · compare submitted starters</summary>'
                   + lineup_html + '<p>This is a projection comparison. DTOS has not changed your Sleeper lineup.</p></details>')
    pressure = []
    for week, row in sorted(weekly.items(), key=lambda item: int(item[0])):
        byes = row.get('previous_optimal_players_on_known_bye') or []
        if not byes:
            continue
        entering = row.get('optimal_entries_since_previous_week') or []
        delta = row.get('total_change_since_previous_week')
        pressure.append(f'<li>Week {week}: prior optimal starters on a known NFL bye: '
                        + ', '.join(player_link(pid) for pid in byes)
                        + '. Entering this week’s optimal lineup: '
                        + (', '.join(player_link(pid) for pid in entering) or 'None supported')
                        + f'. Whole-lineup projected change: {escape(str(delta)) if delta is not None else "Unavailable"}.</li>')
    depth = ('<h3>Upcoming bye / depth context</h3><ul>' + ''.join(pressure[:3]) + '</ul>'
             '<p>Whole-lineup changes are not attributed only to byes. Reserve coverage is not an injury forecast.</p>') if pressure else (
             '<h3>Upcoming bye / depth context</h3><p>No supported prior-optimal-starter bye transition is identified in this prepared horizon. '
             'This does not establish that no depth risk exists.</p>')
    if len(pressure) > 3:
        depth += f'<p>{len(pressure) - 3} additional supported transitions appear in weekly detail.</p>'
    depth = '<div class="thq-depth">' + depth + '</div>'
    weeks = ''.join(f'<tr><td>{week}</td><td>{"Unavailable" if row["optimal"]["projected_points"] is None else format(row["optimal"]["projected_points"], ".2f")}</td>'
                    f'<td>{len(row["known_bye_player_ids"]) if row["bye_evidence_availability"] == "supported" else "Unavailable"}</td>'
                    f'<td>{row["reserve_capacity"]["supported_slots"]} supported reserve slots</td></tr>'
                    for week, row in sorted(profile['weekly'].items(), key=lambda item: int(item[0])))
    return ('<section class="thq-section"><h2>Projected Team Strength</h2><p>Optimal supported lineups, not submitted starters. '
            'Playoff window is opponent-independent and does not imply qualification.</p>' + lineup_html
            + '<div class="thq-intel">' + ''.join(cards) + '</div>' + depth + explanation
            + '<details class="thq-strength-detail"><summary>Weekly coverage and depth</summary><div class="thq-table-scroll" tabindex="0" role="region" aria-label="Weekly coverage and depth table"><table><thead><tr><th>Week</th><th>Optimal points</th>'
            '<th>Known NFL-bye players</th><th>Reserve coverage</th></tr></thead><tbody>' + weeks + '</tbody></table></div>'
            + ('<ul>' + ''.join(pressure) + '</ul>' if pressure else '') + '</details></section>')
