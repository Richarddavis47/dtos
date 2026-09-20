"""Compact scoped strength display; no generic grade or hidden partial total."""
from html import escape


def strength_panel(profile: dict | None) -> str:
    if not profile:
        return '<section class="thq-section"><h2>Projected Team Strength</h2><p>Compatible multi-week evidence is not prepared.</p></section>'
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
        note = f'Partial supported subtotal: {partial:.2f}; not a complete horizon.' if total is None and partial is not None else 'Sum of complete weekly optimal lineups.'
        rank = row.get('league_rank')
        cards.append(f'<article class="thq-kpi"><span>{escape(label)}</span><b>{value}</b><p>{coverage}</p><small>{note}</small>'
                     + (f'<p>{escape(label)} rank: #{rank}</p>' if rank is not None else '<p>Comparable league rank unavailable</p>') + '</article>')
    weeks = ''.join(f'<tr><td>{week}</td><td>{"Unavailable" if row["optimal"]["projected_points"] is None else format(row["optimal"]["projected_points"], ".2f")}</td>'
                    f'<td>{len(row["known_bye_player_ids"]) if row["bye_evidence_availability"] == "supported" else "Unavailable"}</td>'
                    f'<td>{row["reserve_capacity"]["supported_slots"]} supported reserve slots</td></tr>'
                    for week, row in sorted(profile['weekly'].items(), key=lambda item: int(item[0])))
    return ('<section class="thq-section"><h2>Projected Team Strength</h2><p>Optimal supported lineups, not submitted starters. '
            'Playoff window is opponent-independent and does not imply qualification.</p><div class="thq-intel">'
            + ''.join(cards) + '</div><details><summary>Weekly coverage and depth</summary><table><thead><tr><th>Week</th><th>Optimal points</th>'
            '<th>Known NFL-bye players</th><th>Reserve coverage</th></tr></thead><tbody>' + weeks + '</tbody></table></details></section>')
