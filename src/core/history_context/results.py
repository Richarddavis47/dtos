"""Exact Sleeper scoring facts; no zero defaults for unavailable results."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def standing_points(settings: Mapping[str, Any], key: str) -> float | None:
    whole = number(settings.get(key))
    if whole is None:
        return None
    decimal = number(settings.get(f'{key}_decimal'))
    return round(whole + (decimal / 100 if decimal is not None else 0), 2)


def matchup_result(sides: Sequence[Mapping[str, Any]], *, playoff_week: Any, week: int) -> dict:
    scores = {str(side.get('roster_id')): number(side.get('custom_points')
              if side.get('custom_points') is not None else side.get('points')) for side in sides}
    complete = len(sides) == 2 and len(scores) == 2 and all(value is not None for value in scores.values())
    winner = loser = None
    tie = None
    if complete:
        first, second = sides
        a, b = scores[str(first['roster_id'])], scores[str(second['roster_id'])]
        tie = a == b
        if not tie:
            winner = (first if a > b else second)['roster_id']
            loser = (second if a > b else first)['roster_id']
    start = number(playoff_week)
    return {'franchises': [side.get('roster_id') for side in sides], 'team_points': scores,
            'winner': winner, 'loser': loser, 'tie': tie,
            'result_availability': 'observed' if complete else 'unavailable',
            'postseason_context': week >= start if start is not None and start > 0 else None}
