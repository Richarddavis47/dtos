"""Local-only measured replay of the same Shop input; no source or store writes."""
from contextlib import ExitStack
import inspect
import json
from time import perf_counter
from unittest.mock import patch

import psutil

from services import shop_asset_search
from src.core.intelligence import team_strength
from src.core.trade_intelligence import horizon_impact, lineup


def eager_reference():
    source = inspect.getsource(lineup.optimal_legal_lineup)
    lazy = '''                if current is None or candidate[0] > current[0] or (candidate[0] == current[0] and
                        tuple((entry.slot, entry.asset_id) for entry in candidate[1]) <
                        tuple((entry.slot, entry.asset_id) for entry in current[1])):'''
    eager = '''                candidate_key = tuple((entry.slot, entry.asset_id) for entry in candidate[1])
                current_key = tuple((entry.slot, entry.asset_id) for entry in current[1]) if current else ()
                if current is None or candidate[0] > current[0] or (candidate[0] == current[0] and candidate_key < current_key):'''
    assert lazy in source, 'Reference must match the audited optimization exactly'
    namespace = dict(vars(lineup))
    exec(source.replace(lazy, eager), namespace)
    return namespace['optimal_legal_lineup']


def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items()
                if k not in ('timings_seconds', 'timings', 'historical_context_duration_ms')}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def differences(left, right, path=''):
    if left == right:
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        return [difference for key in sorted(left.keys() | right.keys(), key=str)
                for difference in differences(left.get(key), right.get(key), path + '/' + str(key))]
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [difference for index, (a, b) in enumerate(zip(left, right))
                for difference in differences(a, b, path + '/' + str(index))]
    return [] if left == right else [{'path': path, 'optimized': left, 'reference': right}]


def measure(run, *, reference=False):
    metrics = {}
    process = psutil.Process()
    before = process.memory_info()
    def timed(name, function):
        def call(*args, **kwargs):
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                row = metrics.setdefault(name, {'calls': 0, 'seconds': 0.0})
                row['calls'] += 1
                row['seconds'] += perf_counter() - start
        return call
    with ExitStack() as stack:
        for module, name, label, function in (
            (shop_asset_search, 'discover', 'counterparty_discovery', shop_asset_search.discover),
            (shop_asset_search, 'rank_returns', 'result_selection', shop_asset_search.rank_returns),
            (team_strength, 'optimal_legal_lineup', 'optimal_lineup', eager_reference() if reference else lineup.optimal_legal_lineup),
            (horizon_impact, 'prepare_team_strength', 'multi_horizon_preparation', horizon_impact.prepare_team_strength),
        ):
            stack.enter_context(patch.object(module, name, timed(label, function)))
        start = perf_counter()
        result = run()
        metrics['search_seconds'] = perf_counter() - start
    start = perf_counter()
    encoded = json.dumps(result, default=str)
    metrics['serialization_seconds'] = perf_counter() - start
    metrics['serialized_bytes'] = len(encoded.encode())
    after = process.memory_info()
    metrics['memory'] = {'rss_before': before.rss, 'rss_after': after.rss,
                         'process_peak_wset': getattr(after, 'peak_wset', None),
                         'note': 'Process high-water mark includes source preparation and earlier searches, not isolated search peak.'}
    metrics['timing_note'] = 'Lineup time is nested within multi-horizon preparation and shared evaluation; do not add overlapping totals.'
    return result, metrics
