"""Raw-source historical week verification; disposable storage only.

Default mode asserts the corrected contract. --observe records a baseline without
claiming it passes; neither mode reads or rewrites production assessments.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter

from tools.validation.verify_fois_historical import (
    isolated_environment, source_case, add_quote, semantic_scores,
)


CASES = (
    ('scout_cross_week', {}, 3, (10, 5)),
    ('latest_complete', {}, 4, (8, 14)),
    ('latest_worse_than_earlier', {}, 4, (20, 14)),
    ('no_common_week', {}, None, (None, None)),
    ('supported_zero', {}, 3, (0, 0)),
    ('missing_positions', {}, None, (None, None)),
    ('missing_identity', {}, None, (None, None)),
    ('unchanged_player_missing_latest', {}, 3, (10, 5)),
    ('partial_all_weeks', {}, None, (None, None)),
    ('rec_flex', {'slots': ('REC_FLEX',), 'traded_position': 'TE'}, 3, (10, 5)),
    ('superflex', {'slots': ('SUPER_FLEX',), 'traded_position': 'QB'}, 3, (10, 5)),
    ('flex_superflex', {'slots': ('REC_FLEX', 'SUPER_FLEX')}, 3, (18, 13)),
    ('different_scoring', {'slots': ('REC_FLEX', 'SUPER_FLEX'), 'pass_td': 6}, 3, (22, 17)),
    ('decision_boundary', {}, 2, (7, 4)),
    ('conflicting_observations', {}, None, (None, None)),
)


def week_source(index, name, parameters):
    league, source, current, outgoing, incoming = source_case(index, **parameters)
    old, new = outgoing[0], incoming[0]
    reserve, qb = list(current['normalized_players'])[2:4]
    extra = [reserve, qb] if name in ('flex_superflex', 'different_scoring') else [reserve] if name in ('unchanged_player_missing_latest', 'partial_all_weeks') else []
    for roster, team, players in zip(source['rosters'], current['teams'], ([new, *extra], [old])):
        roster['players'], roster['starters'] = players, players
        team['players'] = [p for p in team['players'] if p['id'] in players]
    old_points, new_points = {old: 10}, {new: 5}
    for player in extra:
        old_points[player] = 2 if player == reserve else 2 * parameters.get('pass_td', 4)
    if name == 'partial_all_weeks':
        old_points.pop(reserve)
    if name == 'supported_zero':
        old_points[old], new_points[new] = 0, 0
    def matchup(roster, points):
        return {'roster_id': roster, 'matchup_id': 1, 'players_points': points,
                'starters': list(points), 'points': sum(points.values())}
    source['matchups'] = {'3': [matchup(1, old_points), matchup(2, new_points)],
                          '4': [matchup(2, {new: 14})]}
    if name == 'latest_complete':
        source['matchups']['4'].append(matchup(1, {old: 8}))
    if name == 'latest_worse_than_earlier':
        source['matchups']['3'][1]['players_points'][new] = 50
        source['matchups']['3'][1]['points'] = 50
        source['matchups']['4'].append(matchup(1, {old: 20}))
    if name == 'no_common_week':
        source['matchups']['3'] = [matchup(1, old_points)]
    if name == 'conflicting_observations':
        source['matchups']['3'].append(matchup(3, {new: 99}))
    if name in ('missing_positions', 'missing_identity'):
        current['normalized_players'][old].pop('position', None)
        for team in current['teams']:
            for player in team['players']:
                if player['id'] == old:
                    player.pop('position', None)
        if name == 'missing_identity':
            current['normalized_players'].pop(old)
            for team in current['teams']:
                team['players'] = [p for p in team['players'] if p['id'] != old]
    if name == 'decision_boundary':
        source['transactions'] = {'3': source['transactions']['5']}
        source['matchups']['2'] = [matchup(1, {old: 7}), matchup(2, {new: 4})]
    return league, source, current, old, new


def run(root, observe=False):
    from src.core.history_context import canonical_history_store
    from src.core.history_context.store import sleeper_season_cache
    from src.core.intelligence_memory import intelligence_checkpoint_store
    from src.core.historical_intelligence import HistoricalIntelligenceService
    from src.core.historical_franchise_state import HistoricalFranchiseStateService
    from src.core.historical_transaction_intelligence import HistoricalTransactionIntelligenceService
    from src.core.fois.history import load_results_history
    from src.core.fois.repository import FOISRepository
    from src.core.fois.service import FOISService
    from src.core.fois.process_execution import generate_fois_isolated, shutdown_fois_executor_sync, compact_fois_input
    import psutil

    report = {'environment': 'isolated raw source; not live historical grade acceptance',
              'mode': 'baseline observation' if observe else 'corrected assertions', 'cases': []}
    worker = None
    try:
        for index, (name, parameters, expected_week, expected_points) in enumerate(CASES, 101):
            league, source, current, old, new = week_source(index, name, parameters)
            sleeper_season_cache.write(sleeper_season_cache.normalize(league, 2025, source))
            canonical_history_store.update_current(league, current)
            for asset in (old, new):
                add_quote(intelligence_checkpoint_store, asset)
            # Older and post-decision quotes must not change fair decision-time prices.
            add_quote(intelligence_checkpoint_store, new, value=300, timestamp='2025-09-20T00:00:00+00:00')
            add_quote(intelligence_checkpoint_store, new, value=999, timestamp='2025-10-02T00:00:00+00:00')
            history = HistoricalIntelligenceService(canonical_history_store, checkpoint_reader=intelligence_checkpoint_store)
            states = HistoricalFranchiseStateService(history)
            event = history.transaction_history(league)[0]
            started = perf_counter()
            before, after = states.around_event(league, '1', event.event_id)
            assessment = HistoricalTransactionIntelligenceService(history, states).evaluate_trade(league, event.event_id)
            selection_ms = (perf_counter() - started) * 1000
            process = assessment.sides[0].process
            dimension = next(d for d in process.dimensions if d.name == 'lineup_impact')
            points = (before.lineup.optimal_points, after.lineup.optimal_points)
            weeks = (before.lineup.evidence_week, after.lineup.evidence_week)
            expected_class = 'sound_process' if name in ('latest_complete', 'supported_zero') else 'defensible_optional'
            good = (weeks == (expected_week, expected_week) and points == expected_points
                    and dimension.evidence_available == (expected_week is not None)
                    and process.classification.value == expected_class and process.market_comparable
                    and process.known_incoming_value == process.known_outgoing_value == 500)
            if not observe:
                assert good, (name, weeks, points, asdict(process))
                assert dimension.evidence_week == expected_week
                assert dimension.evidence_reason == (None if expected_week else 'no_common_supported_historical_week')
                if expected_week:
                    assert dimension.source_references
                if name == 'scout_cross_week':
                    assert 'earlier complete common week' in dimension.explanation
            metrics = {}
            full_service = FOISService(FOISRepository(root / f'{league}-full.db'),
                history_loader=lambda selected: load_results_history(canonical_history_store, selected, metrics=metrics))
            started = perf_counter()
            full = full_service._generate_sync(deepcopy(current))
            full_ms = (perf_counter() - started) * 1000
            cache = root / 'cache.json'
            cache.write_text(json.dumps({'data': current}))
            started = perf_counter()
            spawned, _, execution = asyncio.run(generate_fois_isolated(current,
                FOISRepository(root / f'{league}-spawn.db'), cache_file=cache))
            spawn_ms = (perf_counter() - started) * 1000
            worker = execution['worker_pid']
            assert worker != os.getpid()
            assert semantic_scores(full) == semantic_scores(spawned), (name, 'full/spawn score mismatch')
            loaded = load_results_history(canonical_history_store, league)
            trade = loaded['1']['trades'][0]
            assert trade['process_classification'] == process.classification.value
            # Selected week, totals and reasons must survive the actual worker's
            # assessment handoff, not only a parent reconstruction helper.
            if not observe:
                for scores in (full, spawned):
                    category = next(category for category in asdict(scores[0])['category_scores']
                                    if category['category_key'] == 'trading_asset_management')
                    exported = category['details']['process']['lineup_evidence']
                    assert exported['weeks'] == ({str(expected_week): 1} if expected_week else {}), (name, exported)
                    assert exported['before_points'] == ({'minimum': expected_points[0], 'maximum': expected_points[0]} if expected_week else None)
                    assert exported['after_points'] == ({'minimum': expected_points[1], 'maximum': expected_points[1]} if expected_week else None)
                    assert exported['missing_reasons'] == ({dimension.evidence_reason: 1} if dimension.evidence_reason else {})
            report['cases'].append({'name': name, 'passed': good, 'weeks': weeks, 'points': points,
                'impact': asdict(dimension), 'classification': process.classification.value,
                'confidence': process.confidence.value, 'market_comparable': process.market_comparable,
                'full_spawn_parity': True, 'selection_ms': round(selection_ms, 3),
                'full_ms': round(full_ms, 3), 'spawn_wall_ms': round(spawn_ms, 3),
                'execution': {key: value for key, value in execution.items() if key != 'prepared_evidence'},
                'source_queries': states.metrics()['source_record_queries'], 'history_metrics': metrics,
                'identity_bytes': len(json.dumps(compact_fois_input(current)['normalized_players']))})
        if not observe:
            repository = FOISRepository(root / 'prior-contract.db')
            for score in full:
                repository.save(replace(score, evidence_integrity_version='fois-evidence-integrity-1'), 'prior-contract-source')
            with repository._connection() as connection:
                rows_before = [tuple(row) for row in connection.execute('SELECT * FROM fois_scores_v2 ORDER BY score_key')]
                snapshots_before = [tuple(row) for row in connection.execute('SELECT * FROM fois_snapshot_history ORDER BY 1')]
            preserved_full = FOISService(repository, history_loader=lambda selected: load_results_history(canonical_history_store, selected))._generate_sync(deepcopy(current))
            preserved_spawn, _, _ = asyncio.run(generate_fois_isolated(current, repository, cache_file=cache))
            assert all(not score.evidence_revalidated and score.evidence_integrity_version == 'fois-evidence-integrity-1' for score in (*preserved_full, *preserved_spawn))
            with repository._connection() as connection:
                assert rows_before == [tuple(row) for row in connection.execute('SELECT * FROM fois_scores_v2 ORDER BY score_key')]
                assert snapshots_before == [tuple(row) for row in connection.execute('SELECT * FROM fois_snapshot_history ORDER BY 1')]
            report['prior_contract_assessments_unchanged_full_and_spawn'] = True
    finally:
        shutdown_fois_executor_sync()
    report['worker_reaped'] = worker is not None and not psutil.pid_exists(worker)
    assert report['worker_reaped']
    report['parent_rss_bytes'] = psutil.Process().memory_info().rss
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--observe', action='store_true', help='Record prior-source behavior without claiming corrected acceptance')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='dtos-week-verification-') as directory:
        root = Path(directory)
        isolated_environment(root)
        report = run(root, args.observe)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, default=str) + '\n')
    print(json.dumps({'cases': len(report['cases']), 'corrected_expectations_pass': all(c['passed'] for c in report['cases']),
                      'mode': report['mode'], 'worker_reaped': report['worker_reaped']}))


if __name__ == '__main__':
    main()
