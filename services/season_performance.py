"""Bounded read of prepared native Sleeper franchise scores; no acquisition."""
from statistics import mean

from services.matchup_season import METHOD, number
from src.core.intelligence.season_calendar import matchup_calendar
from src.core.player_value_projection.sleeper_actuals import scoring_identity


def season_performance(data, roster_id):
    league = data.get('league') or {}
    prepared = data.get('season_matchups') or {}
    calendar = matchup_calendar(league, data.get('week'), data.get('nfl_state'))
    result = dict(season=league.get('season'), weeks=[], recent=[], average=None,
                  league_average=None, expected_weeks=[], missing=[], retained=False,
                  observed_at=prepared.get('observed_at'), generation=prepared.get('semantic_generation'),
                  reason=None, recent_reason=None, gaps=[], cohort_size=None)
    if (calendar['availability'] != 'supported'
            or prepared.get('league_id') != str(league.get('league_id') or '')
            or prepared.get('season') != str(league.get('season') or '')
            or prepared.get('methodology') != METHOD
            or prepared.get('calendar_reference') != calendar['reference']
            or prepared.get('scoring_fingerprint') != scoring_identity(league.get('scoring_settings') or {})):
        result['reason'] = 'Compatible season team results are not prepared.'
        return result
    completed = (league.get('settings') or {}).get('last_scored_leg')
    expected = [w for w in calendar['regular_season_weeks'] if w <= completed]
    result['expected_weeks'] = expected
    teams = data.get('teams') or []
    ids = [t.get('roster_id') for t in teams]
    count = (league.get('settings') or {}).get('num_teams')
    cohort = (bool(ids) and all(type(i) is int and i > 0 for i in ids)
              and len(set(ids)) == len(ids) and type(count) is int and count == len(ids)
              and roster_id in ids)
    if type(roster_id) is not int or ids.count(roster_id) != 1:
        result['reason'] = 'The selected franchise is not uniquely identified in this league.'
        return result
    result['cohort_size'] = count if cohort else None
    comparisons = []
    for week in expected:
        evidence = (prepared.get('weeks') or {}).get(str(week)) or {}
        retained = evidence.get('availability') != 'available'
        rows = evidence.get('retained_rows') if retained else evidence.get('rows')
        scores = {}
        conflicts = set()
        for row in rows or []:
            if not isinstance(row, dict) or type(row.get('roster_id')) is not int:
                continue
            rid = row['roster_id']
            # An explicit invalid adjustment cannot silently become the base score.
            value = number(row.get('custom_points') if row.get('custom_points') is not None else row.get('points'))
            if rid in scores and scores[rid] != value:
                conflicts.add(rid)
            scores[rid] = value
        for rid in conflicts:
            scores[rid] = None
        score = scores.get(roster_id)
        if score is None:
            result['missing'].append(week)
            if not evidence:
                reason = 'Week not acquired'
            elif evidence.get('availability') != 'available':
                reason = 'Week retrieval failed or is unavailable; no supported retained team score'
            elif not rows:
                reason = 'Source returned an empty week; no team score established'
            elif roster_id in conflicts:
                reason = 'Conflicting team scores'
            else:
                reason = 'Team score missing or invalid'
            result['gaps'].append(dict(week=week, reason=reason))
        else:
            item = dict(week=week, points=score, retained=retained,
                        observed_at=evidence.get('observed_at'))
            result['weeks'].append(item)
            result['retained'] |= retained
            if cohort and all(scores.get(rid) is not None for rid in ids):
                comparisons.append(mean(scores[rid] for rid in ids))
        if week in expected[-3:]:
            result['recent'].append(dict(week=week, points=score, retained=retained))
    values = [row['points'] for row in result['weeks']]
    if values:
        result['average'] = mean(values)
        if len(comparisons) == len(values):
            result['league_average'] = mean(comparisons)
    result['reason'] = ('Some completed weeks are missing or conflicting.' if result['missing'] else
                        'No completed regular-season weeks are available.' if not values else None)
    _recent_postseason(prepared, calendar, completed, roster_id, result)
    return result


def _recent_postseason(prepared, calendar, completed, roster_id, result):
    """Reuse prepared bracket participation; a bye's placeholder zero is no game."""
    from services.matchup_season import _postseason

    weeks = [w for group in calendar['playoff_rounds'] for w in group if w <= completed]
    observations = []
    for week in weeks:
        context = _postseason(prepared, calendar, week, completed)
        matches = [pair for pair in context['pairs'] if roster_id in pair]
        bye = roster_id in context['byes']
        if not matches and bye:
            continue
        if len(matches) != 1 or bye:
            result['recent'] = []
            result['recent_reason'] = 'Recent postseason participation is not established by the prepared bracket.'
            return
        evidence = (prepared.get('weeks') or {}).get(str(week)) or {}
        retained = evidence.get('availability') != 'available'
        rows = evidence.get('retained_rows') if retained else evidence.get('rows')
        values = {number(row.get('custom_points') if row.get('custom_points') is not None else row.get('points'))
                  for row in rows or [] if row.get('roster_id') == roster_id}
        score = next(iter(values)) if len(values) == 1 and None not in values else None
        observations.append(dict(week=week, points=score, retained=retained,
                                 observed_at=evidence.get('observed_at'), postseason=True))
    if observations:
        result['recent'] = (result['recent'] + observations)[-3:]
        result['retained'] |= any(r['retained'] for r in observations)
