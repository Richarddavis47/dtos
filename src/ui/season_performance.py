"""Small season-results disclosure, separate from roster projections."""
from html import escape

from services.matchup_season import number, remaining_regular_opponents
from services.season_performance import season_performance
from services.standings import playoff_position, standings_order
from src.ui.intelligence_presentation import league_is_preseason, record_evidence


def _peer_record(view):
    record = view['peer_record']
    weeks = record['weeks']
    expected = view['expected_weeks']
    coverage = f"{len(weeks)}/{len(expected)} completed regular-season weeks used." if expected else ''
    summary = (
        f"Wins: {record['wins']} · Losses: {record['losses']} · Ties: {record['ties']}."
        if weeks else "No comparison available. This needs a completed week with scores for every team."
    )
    skipped = sorted(set(expected) - set(weeks))
    gaps = ' Skipped weeks without complete league scores: ' + ', '.join(map(str, skipped)) + '.' if skipped else ''
    retained = ' Includes retained scores after a failed refresh.' if record['retained_weeks'] else ''
    return ('<details><summary>How often did we outscore the rest of the league?</summary>'
            f'<p>{summary} {coverage}{gaps}{retained}</p>'
            '<p>Each week, your Sleeper score is compared once with each other team’s score. '
            'These comparisons are separate from your official record and any league median game.</p></details>')

def _playoff_race(data, roster_id):
    order = standings_order(data)
    position = playoff_position(data, order)
    teams = {team["roster_id"]: team for team in order["teams"]}
    kind = position["kind"]
    qualified = roster_id in position["qualifiers"]
    started = not league_is_preseason(data)

    def name(rid):
        return escape(str(teams[rid].get("team_name") or f"Franchise {rid}"))

    def record_line(label, rid):
        team = teams[rid]
        record = record_evidence(team.get("wins"), team.get("losses"), team.get("ties"), season_started=started)
        pf = number(team.get("points_for")) if started else None
        points = f"{pf:.2f} Points For" if pf is not None else "Points For unavailable"
        return f"<li>{label}: {name(rid)} · {escape(record)} · {points}</li>"

    facts = []
    if kind == "bracket":
        status = "In the published championship bracket." if qualified else "Outside the published championship bracket."
    elif kind in {"standard", "divisions"}:
        status = "Currently in a playoff position." if qualified else "Currently outside the playoff positions."
    elif position["cutoff_tied"]:
        status = "Playoff position unresolved at the cutoff tie."
    else:
        status = "Playoff position unavailable."
    if roster_id in teams:
        facts.append(record_line("This franchise", roster_id))
    for rid in position["cutoff_ids"]:
        facts.append(record_line("Tied at cutoff" if position["cutoff_tied"] else "Current cutoff", rid))
    if kind == "divisions" and roster_id in teams:
        leader = position["division_leaders"][teams[roster_id]["division"]]
        if qualified:
            route = "division leader" if roster_id == leader else "at-large position"
            status += f" Qualification route: {route}."
        facts.append(record_line("Current division leader", leader))
        cutoff = position["at_large_cutoff_id"]
        if cutoff is not None:
            facts.append(record_line("Current at-large cutoff", cutoff))

    schedule = remaining_regular_opponents(data, roster_id)
    weeks = schedule["weeks"]
    planned = schedule["matches"]
    if weeks is None:
        coverage = "Remaining regular-season weeks are unavailable for this calendar."
    elif not weeks:
        coverage = "No regular-season weeks remain on the prepared calendar."
    else:
        coverage = f"{len(planned)}/{len(weeks)} remaining regular-season opponents confirmed."
        if schedule["gaps"]:
            coverage += " Opponents unavailable for weeks " + ", ".join(map(str, schedule["gaps"])) + "."
    games = "".join(f'<li><a href="/matchups?week={week}">Week {week}: {name(opponent)}</a></li>'
                    for week, opponent in planned.items())
    return ('<details><summary>Playoff race</summary>'
            f'<p><strong>{status}</strong> {escape(position["reason"] or "")}</p>'
            + (f'<ul>{"".join(facts)}</ul>' if facts else '')
            + f'<p>{coverage}</p>' + (f'<ul>{games}</ul>' if games else '')
            + '<p><a href="/league#standings-evidence">Review standings</a></p></details>')


def season_panel(data, roster_id, *, compact=False):
    view = season_performance(data, roster_id)
    def points(value):
        return f'{value:.2f}' if value is not None else 'Unknown'
    supported = len(view['weeks'])
    heading = 'Season so far'
    lead = (f"{points(view['average'])} points per observed completed team week · "
            f"{supported}/{len(view['expected_weeks'])} regular-season weeks covered."
            if view['average'] is not None else view['reason'])
    if view['average'] is None and view['expected_weeks']:
        lead = f"Scoring unavailable · 0/{len(view['expected_weeks'])} completed regular-season weeks covered. " + lead
    if view['retained']:
        lead += ' Includes retained results after a failed refresh.'
    if compact:
        return (f'<section class="card"><h3>{heading}</h3><p>{escape(lead)}</p>'
                f'<a href="/teams/{roster_id}#season-so-far">Review season results</a></section>')
    comparison = (f"League average: {points(view['league_average'])} across {view['cohort_size']} franchises over the same {supported} observed weeks, "
                  "counting each franchise once per week."
                  if view['league_average'] is not None else
                  'League comparison withheld: complete matched team coverage is unavailable.')
    recent = ' · '.join(f"Week {r['week']}: {points(r['points'])}" + (' (retained)' if r['retained'] else '') for r in view['recent'])
    details = (f"Season {view['season']}. Supported weeks: "
               + (', '.join(str(r['week']) for r in view['weeks']) or 'None')
               + '. Missing or conflicting weeks: ' + (', '.join(map(str, view['missing'])) or 'None')
               + '. ' + '; '.join(f"Week {g['week']}: {g['reason']}" for g in view['gaps'])
               + '. Native Sleeper team totals include explicit score overrides. '
               'These observed regular-season samples are separate from official cumulative standings, '
               'the current roster’s projected optimal lineup. Recent postseason weeks require prepared bracket participation; byes are excluded. '
               'Repeated games or median matchups do not add another scoring observation. '
               'Recent scoring describes results, not future roster strength. '
               + (view['reason'] or '')
               + ' Week observations: ' + '; '.join(f"Week {r['week']}: {r['observed_at'] or 'Unknown retrieval time'}" + (' (retained)' if r['retained'] else '') for r in view['weeks'] + [item for item in view['recent'] if item.get('postseason')])
               + f" Publication retrieved: {view['observed_at'] or 'Unknown'}. Generation: {view['generation'] or 'Unknown'}.")
    short = (f"{points(view['average'])} pts/week" if view['average'] is not None else 'Scoring unavailable')
    if view['missing'] or view['recent_reason'] or any(r['points'] is None for r in view['recent']):
        short += ' · partial'
    if view['retained']:
        short += ' · retained'
    return (f'<details id="season-so-far" class="thq-strength-detail"><summary>{heading} · {escape(short)}</summary>'
            f'<div class="card"><p>{escape(lead)}</p>'
            f'<p>{escape(comparison)}</p>' + (f'<p>Recent completed weeks: {escape(recent)}</p>' if recent else '')
            + (f'<p>{escape(view["recent_reason"])}</p>' if view['recent_reason'] else '')
            + '<p>Past team results are separate from this week’s projected lineup.</p>'
            + _playoff_race(data, roster_id)
            + _peer_record(view)
            + f'<details><summary>Weeks, coverage and sources</summary><p>{escape(details)}</p></details>'
            + '<a href="/matchups">Review matchups</a></div></details>')
