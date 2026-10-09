"""Independent raw-source verification, always using disposable storage.

This tool cannot read or replace production assessments. It exercises the real
season adapter, sparse quote store, historical evaluator and FOIS spawn worker.
Passing fixtures validate contracts, not retained live grades.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter


def isolated_environment(root: Path) -> None:
    for key, filename in {
        'DTOS_CACHE_FILE': 'cache.json', 'DTOS_FOIS_DB_FILE': 'fois.sqlite3',
        'DTOS_HISTORY_DB_FILE': 'history.sqlite3', 'DTOS_METADATA_DB_FILE': 'metadata.sqlite3',
        'DTOS_INTELLIGENCE_CHECKPOINT_FILE': 'checkpoints.sqlite3',
        'DTOS_PROJECTION_DB_FILE': 'projections.sqlite3', 'DTOS_ACCOUNT_DB_FILE': 'accounts.sqlite3',
        'DTOS_GLOBAL_EVIDENCE_FILE': 'global.sqlite3', 'DTOS_DATA_WAREHOUSE_FILE': 'warehouse.json',
        'DTOS_SLEEPER_SEASON_CACHE_ROOT': 'seasons', 'DTOS_HISTORY_STORAGE_ROOT': 'history',
    }.items():
        os.environ[key] = str(root / filename)
    os.environ['SLEEPER_LEAGUE_ID'] = 'verification-only'
    os.environ['DTOS_DURABLE_HISTORY_REQUIRED'] = '0'


def source_case(index: int, *, slots=('WR',), missing_positions=False,
                partial=False, zero=False, pass_td=4, incoming_count=1,
                outgoing_count=1, trade_count=1, pick=False, traded_position='WR', retired_current=False):
    """Sleeper-shaped source records, independent of prior author fixtures."""
    league = f'verification-{index}'
    ids = [str(900000 + index * 100 + n) for n in range(30)]
    old, new, reserve, qb, other = ids[:5]
    outgoing = [old, *ids[5:5 + outgoing_count - 1]]
    incoming = [new, *ids[17:17 + incoming_count - 1]]
    final = [*incoming, reserve, qb]
    counterparty = [*outgoing, other]
    identities = {pid: {'name': f'Verification player {pid}', 'position': 'QB' if pid == qb else 'WR',
                        'provider_ids': {'sleeper': pid}, 'birth_date': '2000-01-01',
                        'unused_catalog_payload': 'x' * 2000}
                  for pid in [*outgoing, *incoming, reserve, qb, other]}
    for pid in outgoing + incoming:
        identities[pid]['position'] = traded_position
    if missing_positions:
        for row in identities.values():
            row.pop('position')
    instant = datetime(2025, 10, 1, tzinfo=timezone.utc)
    trades = [{'type': 'trade', 'status': 'complete', 'transaction_id': f'trade-{league}-{n}',
               'created': int(instant.timestamp() * 1000) + n * 1000,
               'status_updated': int(instant.timestamp() * 1000) + n * 1000,
               'roster_ids': [1, 2],
               'adds': {**dict.fromkeys(incoming, 1), **dict.fromkeys(outgoing, 2)},
               'drops': {**dict.fromkeys(incoming, 2), **dict.fromkeys(outgoing, 1)},
               'draft_picks': [{'season': str(2027 + k), 'round': 4, 'roster_id': 2,
                                'previous_owner_id': 2, 'owner_id': 1} for k in range(int(pick))]}
              for n in range(trade_count)]
    if trade_count > 1:
        all_outgoing, all_incoming = [], []
        for n, transaction in enumerate(trades):
            new_outgoing = [str(int(pid) + n * 10000) for pid in outgoing]
            new_incoming = [str(int(pid) + n * 10000) for pid in incoming]
            for original, shifted in zip(outgoing + incoming, new_outgoing + new_incoming):
                identities[shifted] = deepcopy(identities[original])
            transaction['adds'] = {**dict.fromkeys(new_incoming, 1), **dict.fromkeys(new_outgoing, 2)}
            transaction['drops'] = {**dict.fromkeys(new_incoming, 2), **dict.fromkeys(new_outgoing, 1)}
            for p in transaction['draft_picks']:
                p['season'] = str(int(p['season']) + n * 10)
            all_outgoing.extend(new_outgoing)
            all_incoming.extend(new_incoming)
        outgoing, incoming = all_outgoing, all_incoming
        final, counterparty = [*incoming, reserve, qb], [*outgoing, other]
    own_points = {**dict.fromkeys(outgoing, 22), reserve: 10, qb: 4 * pass_td}
    their_points = {**dict.fromkeys(incoming, 14), other: 8}
    if zero:
        own_points = dict.fromkeys(own_points, 0)
        their_points = dict.fromkeys(their_points, 0)
    if partial:
        own_points.pop(reserve)
    rules = {'playoff_week_start': 15, 'playoff_teams': 2, 'draft_rounds': 4}
    league_row = {'league_id': league, 'name': league, 'season': '2025', 'status': 'complete',
                  'total_rosters': 2, 'roster_positions': list(slots), 'settings': rules,
                  'scoring_settings': {'pass_td': pass_td, 'rec': 1}}
    users = [{'user_id': 'manager-one', 'display_name': 'Verification One'},
             {'user_id': 'manager-two', 'display_name': 'Verification Two'}]
    rosters = [{'roster_id': n, 'owner_id': users[n-1]['user_id'], 'players': players,
                'starters': players[:len(slots)],
                'settings': {'wins': 7, 'losses': 7, 'ties': 0, 'rank': n, 'fpts': 1000}}
               for n, players in ((1, final), (2, counterparty))]
    facts = {'league': league_row, 'users': users, 'rosters': rosters,
             'matchups': {'4': [{'roster_id': n, 'matchup_id': 1, 'players_points': points,
                                'starters': list(points)[:len(slots)], 'points': sum(points.values())}
                               for n, points in ((1, own_points), (2, their_points))]},
             'transactions': {'5': trades}, 'drafts': [], 'draft_picks': [],
             'traded_picks': [dict(p) for t in trades for p in t['draft_picks']],
             'winners_bracket': [], 'losers_bracket': []}
    current = {'league': {**league_row, 'season': '2026', 'status': 'in_season'},
               'league_settings': {'roster_positions': list(slots), 'scoring_settings': {'pass_td': pass_td, 'rec': 1}, 'settings': rules},
               'normalized_players': identities,
               'teams': [{'roster_id': n, 'owner_id': users[n-1]['user_id'],
                          'owner': users[n-1]['display_name'], 'name': f'Team {n}',
                          'players': [{'id': pid, **identities[pid]} for pid in players],
                          'picks': [], 'settings': rosters[n-1]['settings']}
                         for n, players in ((1, final), (2, counterparty))]}
    if retired_current:
        for team in current['teams']:
            team['players'] = [p for p in team['players'] if p['id'] not in outgoing]
    return league, facts, current, outgoing, incoming


def add_quote(store, asset, *, value=500, timestamp='2025-09-30T00:00:00+00:00',
              version='verified-1000-v1', provider='DynastyProcess', concept='external_market_normalized_index',
              scale='0-1000', context='verification-scoring', suffix=''):
    from src.core.intelligence_memory.models import (
        IntelligenceCheckpoint, SourceObservation, CheckpointTrigger, ProvenanceType, EvidenceCompleteness,
    )
    identity = f'{asset}:{timestamp}:{version}:{suffix}'
    row = SourceObservation(provider, value, timestamp, 'controlled-source', 0,
                            version, value, {'comparison_semantics': {
                                'value_concept': concept, 'value_scale': scale,
                                'format_key': 'controlled-superflex-ppr', 'methodology': 'controlled-v1'}})
    store.put_sparse(IntelligenceCheckpoint(identity, f'player:{asset}', 'player', timestamp, 2025,
        CheckpointTrigger.SEASON_START, ProvenanceType.LIVE_CAPTURED, market_value=value,
        confidence=90, evidence_completeness=EvidenceCompleteness.COMPLETE,
        normalization_version=version), market_context_id=context, provider_evidence=(row,))


def semantic_scores(scores):
    result = []
    for score in scores:
        row = asdict(score)
        row.pop('generated_at', None)
        row.pop('brain_snapshot_id', None)  # independently generated provenance clocks
        result.append(row)
    return sorted(result, key=lambda row: row['franchise_id'])


def run(root: Path):
    # Imports intentionally follow environment setup, including in spawn children.
    from src.core.history_context import canonical_history_store
    from src.core.history_context.store import sleeper_season_cache
    from src.core.fois.history import load_results_history
    from src.core.fois.repository import FOISRepository
    from src.core.fois.service import FOISService
    from src.core.fois.process_execution import generate_fois_isolated, shutdown_fois_executor_sync, compact_fois_input
    from src.core.intelligence_memory import intelligence_checkpoint_store
    from src.core.historical_intelligence import HistoricalIntelligenceService
    from src.core.historical_franchise_state import HistoricalFranchiseStateService
    from src.core.historical_transaction_intelligence import HistoricalTransactionIntelligenceService
    import psutil

    cases = [
        ('original_full_identity', {}, 'compatible', (22, 14)),
        ('missing_positions', {'missing_positions': True}, 'compatible', (None, None)),
        ('partial_week', {'partial': True}, 'compatible', (None, None)),
        ('supported_zero', {'zero': True}, 'zero', (0, 0)),
        ('rec_flex_superflex', {'slots': ('REC_FLEX', 'SUPER_FLEX')}, 'compatible', (38, 30)),
        ('historical_player_absent_current_rosters', {'retired_current': True}, 'compatible', (22, 14)),
        ('rec_flex_accepts_te', {'slots': ('REC_FLEX', 'SUPER_FLEX'), 'traded_position': 'TE'}, 'compatible', (38, 30)),
        ('wrrb_flex_excludes_te', {'slots': ('WRRB_FLEX', 'SUPER_FLEX'), 'traded_position': 'TE'}, 'compatible', (32, 26)),
        ('different_scoring', {'slots': ('WRRB_FLEX', 'SUPER_FLEX'), 'pass_td': 6}, 'compatible', (46, 38)),
        ('unsupported_slot', {'slots': ('WR', 'UNKNOWN')}, 'compatible', (None, None)),
        ('mixed_normalization', {}, 'mixed', (22, 14)),
        ('different_provider', {}, 'provider', (22, 14)),
        ('different_concept', {}, 'concept', (22, 14)),
        ('different_scale', {}, 'scale', (22, 14)),
        ('future_only', {}, 'future', (22, 14)),
        ('missing_player_price', {}, 'missing', (22, 14)),
        ('latest_eligible_quote', {}, 'latest', (22, 14)),
        ('missing_exact_pick_price', {'pick': True}, 'compatible', (22, 14)),
        ('one_twelve_asset_package', {'incoming_count': 12}, 'unpriced', (22, 14)),
        ('independent_packages', {'trade_count': 5}, 'unpriced', None),
        ('one_for_two_packages', {'trade_count': 5, 'outgoing_count': 2}, 'unpriced', None),
        ('multi_asset_packages', {'trade_count': 5, 'incoming_count': 2, 'outgoing_count': 2}, 'unpriced', None),
        ('player_plus_pick_packages', {'trade_count': 5, 'pick': True}, 'unpriced', None),
        ('pick_heavy_packages', {'trade_count': 5, 'pick': 3}, 'unpriced', None),
    ]
    output = {'environment': 'isolated deterministic raw source; not live historical grade acceptance', 'cases': []}
    try:
        for index, (name, parameters, pricing, expected) in enumerate(cases, 1):
            league, source, current, outgoing, incoming = source_case(index, **parameters)
            sleeper_season_cache.write(sleeper_season_cache.normalize(league, 2025, source))
            canonical_history_store.update_current(league, current)
            if pricing != 'unpriced':
                for asset in outgoing + incoming:
                    if pricing == 'missing' and asset in incoming:
                        continue
                    values = {}
                    if asset in incoming:
                        values = {'mixed': {'version': 'raw-10000-v0', 'value': 5000},
                                  'provider': {'provider': 'FantasyCalc'},
                                  'concept': {'concept': 'intrinsic_utility'},
                                  'scale': {'scale': '0-10000'},
                                  'future': {'timestamp': '2025-10-02T00:00:00+00:00'}}.get(pricing, {})
                    if pricing == 'zero':
                        values['value'] = 0
                    add_quote(intelligence_checkpoint_store, asset, **values)
                if pricing == 'latest':
                    add_quote(intelligence_checkpoint_store, incoming[0], value=550, timestamp='2025-10-01T00:00:00+00:00')
                    add_quote(intelligence_checkpoint_store, incoming[0], value=999, timestamp='2025-10-02T00:00:00+00:00')
            history = HistoricalIntelligenceService(canonical_history_store, checkpoint_reader=intelligence_checkpoint_store)
            states = HistoricalFranchiseStateService(history)
            event = history.transaction_history(league)[0]
            before, after = states.around_event(league, '1', event.event_id)
            assessment = HistoricalTransactionIntelligenceService(history, states).evaluate_trade(league, event.event_id)
            process = assessment.sides[0].process
            points = (before.lineup.optimal_points, after.lineup.optimal_points)
            if expected is not None:
                assert points == expected, (name, points, expected)
            impact = next(d for d in process.dimensions if d.name == 'lineup_impact')
            assert impact.evidence_available == (points[0] is not None and points[1] is not None), (name, asdict(impact))
            comparable = pricing in ('compatible', 'zero', 'latest') and not parameters.get('pick')
            assert process.market_comparable == comparable, (name, asdict(process))
            if pricing == 'latest':
                assert process.known_incoming_value == 550
            metrics = {}
            service = FOISService(FOISRepository(root / f'{league}-full.db'), history_loader=lambda selected: load_results_history(canonical_history_store, selected, metrics=metrics))
            started = perf_counter()
            full = service._generate_sync(deepcopy(current))
            full_ms = (perf_counter() - started) * 1000
            cache = root / 'cache.json'
            cache.write_text(json.dumps({'data': current}))
            spawned, _, execution = asyncio.run(generate_fois_isolated(current, FOISRepository(root / f'{league}-spawn.db'), cache_file=cache))
            assert execution['worker_pid'] != os.getpid()

            if semantic_scores(full) != semantic_scores(spawned):
                left, right = semantic_scores(full)[0], semantic_scores(spawned)[0]
                print(json.dumps({'differing_fields': [key for key in left if left[key] != right[key]]}))
                raise AssertionError((name, 'full/spawn semantic mismatch'))
            loaded = load_results_history(canonical_history_store, league)
            assert len(loaded['1']['trades']) == parameters.get('trade_count', 1)
            behavior = spawned[0].gm_behavioral_profile
            assert behavior['league_id'] == league
            assert behavior['transaction_count'] == parameters.get('trade_count', 1)
            price = next(d for d in behavior['dimensions'] if d['key'] == 'price_behavior')
            if not comparable:
                assert price['sample_count'] == 0, (name, price)
            if name == 'one_twelve_asset_package':
                for dimension in behavior['dimensions']:
                    assert dimension['sample_count'] <= 1, (name, dimension)
                    assert dimension['confidence'] == 'low'
                position = next(d for d in behavior['dimensions'] if d['key'] == 'positional')
                assert position['supporting_asset_counts']['acquire_WR'] == 12
            package_matches = []
            if parameters.get('trade_count') == 5:
                from types import SimpleNamespace
                from src.core.trade_intelligence.evidence_context import build_trade_evidence_context, assess_historical_fit
                from src.core.trade_intelligence.package_shape import package_shape
                from src.core.fois.facts import TradeFact
                for side, row in enumerate(spawned, 1):
                    bp = row.gm_behavioral_profile
                    preference = next(d for d in bp['dimensions'] if d['key'] == 'package_preference')
                    fact = TradeFact(**loaded[str(side)]['trades'][0])
                    def assets(types):
                        return tuple(SimpleNamespace(kind=kind, position=None, asset_id=f'{kind}:{n}') for n, kind in enumerate(types))
                    context = build_trade_evidence_context({'league': {'league_id': league}, 'gm_behavioral_intelligence': {str(side): bp}})
                    match = assess_historical_fit(context, partner_roster_id=side, active_roster_id=99, partner_receives=assets(fact.incoming_asset_types), active_receives=assets(fact.outgoing_asset_types))
                    assert preference['tendency'] == package_shape(fact.incoming_asset_types, fact.outgoing_asset_types)
                    assert 'PACKAGE_STYLE_MATCH' in match['reason_codes'] and match['evidence_references']
                    assert preference['confidence'] == 'medium'
                    assert match['confidence'] == bp['overall_confidence'].upper()
                    wrong_types = ('player',) * (3 if preference['tendency'] == 'one_for_one' else 1)
                    wrong = assess_historical_fit(context, partner_roster_id=side, active_roster_id=99, partner_receives=assets(wrong_types), active_receives=assets(('player',)))
                    assert 'PACKAGE_STYLE_MATCH' not in wrong['reason_codes']
                    assert match['score'] > wrong['score']  # qualitative counterparty context, not a hard gate
                    crossed = build_trade_evidence_context({'league': {'league_id': 'different-league'}, 'gm_behavioral_intelligence': {str(side): bp}})
                    rejected = assess_historical_fit(crossed, partner_roster_id=side, active_roster_id=99, partner_receives=assets(fact.incoming_asset_types), active_receives=assets(fact.outgoing_asset_types))
                    assert rejected['score'] == 0 and not rejected['evidence_references']
                    package_matches.append({'side': side, 'shape': preference['tendency'], 'match_score': match['score'], 'wrong_score': wrong['score'], 'confidence': match['confidence']})
            output['cases'].append({'name': name, 'passed': True, 'lineup': points, 'package_matches': package_matches,
                'classification': process.classification.value, 'market_comparable': process.market_comparable,
                'market_reason': process.market_unavailable_reason, 'independent_transactions': behavior['transaction_count'],
                'price_sample': price['sample_count'], 'full_ms': round(full_ms, 3),
                'execution': {key: value for key, value in execution.items() if key != 'prepared_evidence'},
                'full_history_metrics': metrics, 'identity_bytes': len(json.dumps(compact_fois_input(current)['normalized_players']))})
        worker = execution['worker_pid']
    finally:
        shutdown_fois_executor_sync()
    output['worker_reaped'] = not psutil.pid_exists(worker)
    assert output['worker_reaped']
    output['preservation'] = verify_preservation(root, intelligence_checkpoint_store)
    output['parent_rss_bytes'] = psutil.Process().memory_info().rss
    return output



def verify_preservation(root, store):
    from src.core.intelligence_memory.models import PickLineage
    from src.core.intelligence_memory.service import IntelligenceMemoryService
    from src.core.intelligence_memory.pipeline import CheckpointPipeline
    from src.core.fois.repository import FOISRepository
    from src.core.fois.process_execution import generate_fois_isolated, shutdown_fois_executor_sync
    from src.core.fois.service import FOISService
    from src.core.fois.history import load_results_history
    from src.core.history_context import canonical_history_store

    legacy = PickLineage('ambiguous-original', 'PICK-2027-R4-ORIG1', 2027, 4, '1')
    store.put_lineage(legacy)
    with store._connect() as connection:
        old_lineage = [tuple(row) for row in connection.execute('SELECT * FROM pick_lineage')]
    pipeline = CheckpointPipeline(IntelligenceMemoryService(store))
    for league in ('exact-league-one', 'exact-league-two'):
        data = {'league': {'league_id': league, 'season': '2027'}, 'teams': [],
                'drafts': [{'draft_id': 'local-draft', 'season': '2027'}]}
        picks = [{'draft_id': 'local-draft', 'pick_no': selection, 'round': 4,
                  'roster_id': 1, 'original_roster_id': 2 if selection == 31 else None,
                  'player_id': str(100 + selection)} for selection in (31, 32)]
        pipeline.ingest_drafts(data, picks, observed_at='2027-09-01T00:00:00+00:00')
        pipeline.ingest_drafts(data, picks, observed_at='2027-09-01T00:00:00+00:00')
        pipeline.ingest_drafts(data, [{**picks[0], 'pick_no': None}], observed_at='2027-09-01T00:00:00+00:00')
    with store._connect() as connection:
        assert old_lineage == [tuple(row) for row in connection.execute('SELECT * FROM pick_lineage')]
        rows = connection.execute('SELECT * FROM exact_pick_lineage').fetchall()
        assert len(rows) == 4
        assert len({row['lineage_id'] for row in rows}) == 4
        assert {row['league_id'] for row in rows} == {'exact-league-one', 'exact-league-two'}
        assert all(row['selecting_roster_id'] == '1' for row in rows)
        assert all(row['original_roster_id'] == ('2' if row['selection'] == 31 else None) for row in rows)
    repository = FOISRepository(root / 'retained.db')
    league, _, data, _, _ = source_case(1)
    canonical_history_store.update_current(league, data)
    service = FOISService(repository, history_loader=lambda selected: load_results_history(canonical_history_store, selected))
    service._generate_sync(deepcopy(data))
    with repository._connection() as connection:
        for row in connection.execute('SELECT score_key,payload FROM fois_scores_v2').fetchall():
            payload = json.loads(row['payload'])
            payload.pop('evidence_integrity_version')
            connection.execute('UPDATE fois_scores_v2 SET payload=? WHERE score_key=?', (json.dumps(payload), row['score_key']))
        connection.commit()
        original = [tuple(row) for row in connection.execute('SELECT * FROM fois_scores_v2 ORDER BY score_key')]
        historical = [tuple(row) for row in connection.execute('SELECT * FROM fois_snapshot_history ORDER BY 1')]
    full = service._generate_sync(deepcopy(data))
    assert all(row.evidence_integrity_version is None for row in full)
    cache = root / 'cache.json'
    cache.write_text(json.dumps({'data': data}))
    try:
        spawned, _, _ = asyncio.run(generate_fois_isolated(data, repository, cache_file=cache))
        assert all(row.evidence_integrity_version is None for row in spawned)
    finally:
        shutdown_fois_executor_sync()
    with repository._connection() as connection:
        assert original == [tuple(row) for row in connection.execute('SELECT * FROM fois_scores_v2 ORDER BY score_key')]
        assert historical == [tuple(row) for row in connection.execute('SELECT * FROM fois_snapshot_history ORDER BY 1')]
    return {'exact_selections': 4, 'legacy_lineage_unchanged': True,
            'retained_assessments_unchanged_full_and_spawn': True, 'retained_snapshots_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='dtos-fois-independent-') as directory:
        root = Path(directory)
        isolated_environment(root)
        result = run(root)
    encoded = json.dumps(result, indent=2, default=str)
    if arguments.output:
        arguments.output.write_text(encoded + '\n')
    print(json.dumps({'cases': len(result['cases']), 'passed': all(c['passed'] for c in result['cases']), 'worker_reaped': result['worker_reaped']}))


if __name__ == '__main__':
    main()
