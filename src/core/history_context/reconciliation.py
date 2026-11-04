"""Bounded season reconciliation over already-fetched Sleeper facts."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

from .playoffs import playoff_facts
from .results import matchup_result, number, standing_points


def reconcile_season(facts: Mapping[str, Any]) -> dict:
    """Compare source standings with observed regular head-to-head results.

    Differences remain visible. Additional median results are not silently
    invented or used to force agreement with the source standing totals.
    """
    league = facts.get('league') or {}
    settings = league.get('settings') or {}
    start = number(settings.get('playoff_week_start'))
    rosters = facts.get('rosters') or []
    roster_ids = [str(row['roster_id']) for row in rosters]
    if len(set(roster_ids)) != len(roster_ids):
        raise ValueError('Duplicate source roster identity.')
    derived = {key: {'wins': 0, 'losses': 0, 'ties': 0, 'games': 0, 'points_for': 0.0} for key in roster_ids}
    gaps = []
    for week, rows in (facts.get('matchups') or {}).items():
        if rows is None:
            gaps.append({'week': int(week), 'reason': 'matchups_unavailable'})
            continue
        if start is None:
            continue
        if start > 0 and int(week) >= start:
            continue
        grouped = defaultdict(list)
        for row in rows:
            if row.get('matchup_id') is not None:
                grouped[str(row['matchup_id'])].append(row)
        for sides in grouped.values():
            result = matchup_result(sides, playoff_week=start, week=int(week))
            if result['result_availability'] != 'observed':
                gaps.append({'week': int(week), 'reason': 'matchup_result_incomplete'})
                continue
            for roster_id, score in result['team_points'].items():
                if roster_id not in derived:
                    raise ValueError('Matchup references an unknown source roster.')
                row = derived[roster_id]
                row['games'] += 1
                row['points_for'] += score
                outcome = 'ties' if result['tie'] else 'wins' if str(result['winner']) == roster_id else 'losses'
                row[outcome] += 1
    comparisons = []
    for roster in rosters:
        key = str(roster['roster_id'])
        source_settings = roster.get('settings') or {}
        source = {field: number(source_settings.get(field)) for field in ('wins', 'losses', 'ties')}
        source['points_for'] = standing_points(source_settings, 'fpts')
        observed = derived[key] if start is not None else None
        if observed is not None:
            observed['points_for'] = round(observed['points_for'], 2)
        differences = [field for field in source if source[field] is not None
                       and observed is not None and abs(source[field] - observed[field]) > .011]
        comparisons.append({'roster_id': key, 'source': source, 'head_to_head': observed,
                            'comparison_availability': 'observed' if observed is not None else 'unavailable',
                            'differences': differences})
    transactions = [row for bucket in (facts.get('transactions') or {}).values() for row in bucket or []]
    ids = [str(row.get('transaction_id')) for row in transactions]
    picks = [(str(row.get('draft_id')), str(row.get('pick_no'))) for row in facts.get('draft_picks') or []]
    return {'season': league.get('season'), 'source_status': league.get('status'),
            'franchise_count': len(rosters), 'standings': comparisons, 'gaps': gaps,
            'postseason': playoff_facts(facts.get('winners_bracket') or []),
            'transaction_types': dict(Counter(row.get('type') for row in transactions)),
            'transaction_statuses': dict(Counter(row.get('status') for row in transactions)),
            'duplicate_transaction_ids': len(ids) - len(set(ids)),
            'draft_selection_count': len(picks), 'duplicate_draft_selection_ids': len(picks) - len(set(picks)),
            'limitations': ['head_to_head_does_not_invent_additional_median_results',
                           'in_season_standings_are_not_final', 'missing_playoff_start_prevents_regular_result_derivation']}
