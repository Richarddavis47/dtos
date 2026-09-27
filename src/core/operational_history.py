"""Bounded operational diagnostics, not historical player/decision evidence.

Keep 64 meaningful transitions per provider and 64 calibration transitions.
Observation-only refreshes retain the original entry, so replay is byte stable.
Unknown semantic fields participate in comparison; only named observation fields
and calibration's previous-state display are excluded from current-state identity.
"""
from collections import defaultdict, deque
import json

TRANSITION_LIMIT = 64


def _identity(row, *, calibration=False):
    state = {key: value for key, value in row.items() if key != 'timestamp'}
    if calibration:
        state.pop('before_metrics', None)
        state['after_metrics'] = {
            key: value for key, value in (state.get('after_metrics') or {}).items()
            if key != 'last_calibration_timestamp'
        }
    return json.dumps(state, sort_keys=True, separators=(',', ':'))


def provider_history(existing, observations):
    groups = defaultdict(lambda: deque(maxlen=TRANSITION_LIMIT))
    last = {}
    for row in (*existing, *observations):
        provider = row.get('provider_id')
        identity = _identity(row)
        if last.get(provider) != identity:
            groups[provider].append(row)
            last[provider] = identity
    return sorted((row for group in groups.values() for row in group),
                  key=lambda row: (str(row.get('timestamp') or ''), str(row.get('provider_id') or '')))


def calibration_history(existing, observation):
    retained = deque(maxlen=TRANSITION_LIMIT)
    last = None
    for row in (*existing, observation):
        identity = _identity(row, calibration=True)
        if identity != last:
            retained.append(row)
            last = identity
    return list(retained)
