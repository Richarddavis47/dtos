"""Small season-results disclosure, separate from roster projections."""
from html import escape

from services.season_performance import season_performance


def season_panel(data, roster_id, *, compact=False):
    view = season_performance(data, roster_id)
    def points(value):
        return f'{value:.2f}' if value is not None else 'Unknown'
    supported = len(view['weeks'])
    heading = 'Season so far'
    lead = (f"{points(view['average'])} points per observed completed team week · "
            f"{supported}/{len(view['expected_weeks'])} regular-season weeks covered."
            if view['average'] is not None else view['reason'])
    if view['retained']:
        lead += ' Includes retained results after a failed refresh.'
    if compact:
        return (f'<section class="card"><h3>{heading}</h3><p>{escape(lead)}</p>'
                f'<a href="/teams/{roster_id}#season-so-far">Review season results</a></section>')
    comparison = (f"League average: {points(view['league_average'])} over the same weeks, "
                  "counting each franchise once per week."
                  if view['league_average'] is not None else
                  'League comparison withheld: complete matched team coverage is unavailable.')
    recent = ' · '.join(f"Week {r['week']}: {points(r['points'])}" for r in view['recent'])
    details = (f"Season {view['season']}. Supported weeks: "
               + (', '.join(str(r['week']) for r in view['weeks']) or 'None')
               + '. Native Sleeper team totals include explicit custom-point overrides. '
               'These observed regular-season samples are separate from official cumulative standings, '
               'playoff results and the current roster’s projected optimal lineup. '
               'Repeated games or median matchups do not add another scoring observation. '
               'Recent scoring describes results, not future roster strength. '
               + (view['reason'] or '')
               + f" Source retrieved: {view['observed_at'] or 'Unknown'}. Generation: {view['generation'] or 'Unknown'}.")
    return (f'<section id="season-so-far" class="card"><h2>{heading}</h2><p>{escape(lead)}</p>'
            f'<p>{escape(comparison)}</p>' + (f'<p>Recent completed weeks: {escape(recent)}</p>' if recent else '')
            + '<p>Past team results are separate from this week’s projected lineup.</p>'
            + f'<details><summary>Weeks, coverage and sources</summary><p>{escape(details)}</p></details>'
            + '<a href="/matchups">Review matchups</a></section>')
