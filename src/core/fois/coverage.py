"""Coverage of prepared historical decisions, never a quality grade.

Counts describe retained evaluator output only. A non-null owner is seasonal
attribution evidence, not proof of an exact intra-season tenure boundary.
"""
from __future__ import annotations

from typing import Any, Mapping
from collections import Counter
from datetime import datetime


def _dated(value: Any) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).tzinfo is not None
    except ValueError:
        return False


def decision_evaluability(row: Mapping[str, Any], category: str) -> dict[str, Any]:
    """Classify retained evidence, independently of the magnitude of quality.

    Partial means a supported evaluation exists but its required context is
    incomplete. Activity/identity alone never makes process evaluable.
    """
    checks = {
        'manager_attribution': row.get('owner_id') not in (None, ''),
        'decision_timestamp': _dated(row.get('occurred_at')),
    }
    if category == 'trading':
        checks.update(
            package_identity=bool(row.get('incoming_asset_ids') or row.get('outgoing_asset_ids')),
            decision_market_complete=row.get('market_coverage_ratio') == 1,
        )
    elif category == 'drafting':
        checks.update(exact_selection=bool(row.get('draft_id')) and bool(row.get('player_id'))
                      and row.get('pick_number') is not None,
                      draft_time_evidence=row.get('draft_time_evidence_available') is True,
                      historical_format=row.get('historical_format_available') is True)
    elif category == 'waivers':
        checks.update(action_identity=bool(row.get('adds') or row.get('drops')),
                      decision_time_evidence=row.get('decision_time_evidence_available') is True,
                      historical_context=row.get('historical_context_available') is True)
    # Do not infer player/roster coverage from Market coverage or a score.
    declared = (row.get('process_evidence') or {}).get('historical_process_dimensions')
    if category == 'trading':
        checks['historical_context'] = bool(declared) and all(
            item.get('evidence_available') is True for item in declared)
    process_present = row.get('process_score') is not None
    process_state = ('evaluable' if all(checks.values()) else 'partially_evaluable') if process_present else 'insufficient'
    if category == 'trading' and not process_present and any(
            item.get('evidence_available') is True and item.get('assessment')
            for item in declared or ()):
        # A supported scoped conclusion survives an unavailable package grade.
        process_state = 'partially_evaluable'
    outcome_present = row.get('outcome_score') is not None
    outcome_state = ('evaluable' if row.get('outcome_maturity') == 'mature' else 'partially_evaluable') if outcome_present else 'insufficient'
    evaluation = row.get('decision_evaluation')
    if evaluation:
        process_state = evaluation['process']['evaluability']
        outcome_state = evaluation['outcome']['evaluability']
        # Scoped assessments need no legacy numeric score or adapter booleans.
        # Preserve the evaluator's actual limitations, independently per side.
        return {'process': process_state, 'outcome': outcome_state,
                'process_requirements': {},
                'missing_process_requirements': list(evaluation['process'].get('reasons', ())),
                'missing_outcome_requirements': list(evaluation['outcome'].get('reasons', ())),
                'process_confidence': evaluation['process'].get('confidence', 'unavailable'),
                'outcome_confidence': evaluation['outcome'].get('confidence', 'unavailable')}
    return {'process': process_state, 'outcome': outcome_state,
            'process_requirements': checks,
            'missing_outcome_requirements': ['NO_OUTCOME_EVIDENCE'] if not outcome_present else [],
            'process_confidence': 'not_reported', 'outcome_confidence': 'not_reported',
            'missing_process_requirements': [key for key, available in checks.items() if not available]}


def decision_coverage(history: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {'attribution_basis': 'retained_owner_evidence',
                              'intra_season_timing_proven': False}
    for category, key in (('trading', 'trades'), ('drafting', 'drafts'), ('waivers', 'waivers')):
        rows = tuple(history.get(key) or ())
        attributed = tuple(row for row in rows if row.get('owner_id') not in (None, ''))
        classified = [decision_evaluability(row, category) for row in attributed]
        coverage = [row.get('market_coverage_ratio') for row in attributed]
        result[category] = {
            'discovered': len(rows), 'attributed': len(attributed),
            'unattributed': len(rows) - len(attributed),
            'process_evaluable': sum(item['process'] == 'evaluable' for item in classified),
            'outcome_evaluable': sum(item['outcome'] == 'evaluable' for item in classified),
            'process_partially_evaluable': sum(item['process'] == 'partially_evaluable' for item in classified),
            'outcome_partially_evaluable': sum(item['outcome'] == 'partially_evaluable' for item in classified),
            'process_insufficient': sum(item['process'] == 'insufficient' for item in classified),
            'outcome_insufficient': sum(item['outcome'] == 'insufficient' for item in classified),
            'market_coverage_measured': sum(value is not None for value in coverage),
            'market_coverage_complete': sum(value == 1 for value in coverage),
            # The active adapter does not yet expose a canonical player-evidence
            # coverage denominator. Do not equate Market or process with it.
            'decision_time_player_coverage': None,
            'availability': 'partial' if any(
                item['process'] != 'insufficient' or item['outcome'] != 'insufficient'
                for item in classified) else 'insufficient',
        }
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            group = (str(row.get('owner_id') or 'UNATTRIBUTED'), str(row.get('season') or 'UNKNOWN'))
            groups.setdefault(group, []).append(decision_evaluability(row, category))
        result[category]['by_manager_season'] = [
            {'owner_id': owner, 'season': season, 'decisions': len(values),
             'process_states': dict(Counter(item['process'] for item in values)),
             'outcome_states': dict(Counter(item['outcome'] for item in values)),
             'process_confidence': dict(Counter(item['process_confidence'] for item in values)),
             'outcome_confidence': dict(Counter(item['outcome_confidence'] for item in values)),
             'missing_outcome_requirements': dict(Counter(
                 reason for item in values for reason in item['missing_outcome_requirements'])),
             'missing_process_requirements': dict(Counter(
                 reason for item in values for reason in item['missing_process_requirements']))}
            for (owner, season), values in sorted(groups.items())]
    return result
