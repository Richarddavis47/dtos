"""Evidence trust contracts; source fixtures are not live grade validation."""
from __future__ import annotations

import concurrent.futures
import json
import multiprocessing
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from src.core.fois.process_execution import compact_fois_input
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.historical_franchise_state import HistoricalFranchiseStateService, HistoricalBoundary
from src.core.historical_intelligence import HistoricalIntelligenceService, GlobalMarketCheckpoint
from src.core.historical_transaction_intelligence import HistoricalTransactionIntelligenceService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.models import ExactPickLineage, PickLineage
from src.core.trade_intelligence.package_shape import package_shape
from src.core.trade_intelligence.evidence_context import build_trade_evidence_context, assess_historical_fit
from src.core.trade_intelligence.models import TradeAsset
from src.core.fois.cycles import CompetitiveCycleAnalyzer
from tests.test_historical_franchise_state import FixtureStore
from tests.test_gm_behavioral_intelligence_v1126 import trade, profile, dimension
from tests.test_fois_results import season


class IdentityStore(FixtureStore):
    def __init__(self, identities, league='league-a'):
        super().__init__(league)
        self.identities = identities
        self.rows[0]['payload']['roster_positions'] = ['WR']
        self.rows = [row for row in self.rows if row['entity_type'] != 'pick_snapshot']
        for row in self.rows:
            if row['entity_type'] == 'trade':
                row['payload']['draft_picks'] = []
        self.rows.append(self._row(league, 'player_week', '4:2:player-new',
            {'points': 50, 'starter': True}, week=4, player_id='player-new',
            franchise_id=f'{league}:franchise:2'))

    def identity_for_provider_id(self, player_id):
        row = self.identities.get(player_id)
        return {'metadata': row} if row else None


def quote(asset, value=500, **overrides):
    values = dict(asset_id=asset, occurred_at='2025-09-20T00:00:00Z', provider='canonical',
        normalized_value=value, confidence=90, classification='event_relevant', reason_codes=('trade',),
        market_context_id='league-scoring-a', normalization_version='canonical-1000-v1',
        value_concept='canonical_market', comparison_identity=('normalized-market', '0-1000', 'test-format', 'test-method', 'canonical'))
    values.update(overrides)
    return GlobalMarketCheckpoint.create(**values)


def historical_probe(data):
    store = IdentityStore(data.get('normalized_players') or {})
    history = HistoricalIntelligenceService(store, [quote('player-old'), quote('player-new'), quote('player-stay')])
    states = HistoricalFranchiseStateService(history)
    event = history.transaction_history(store.league)[0]
    result = HistoricalTransactionIntelligenceService(history, states).evaluate_trade(store.league, event.event_id)
    before, after = states.around_event(store.league, '1', event.event_id)
    return (asdict(before.lineup), asdict(after.lineup), asdict(result.sides[0].process))


class HistoricalLineupIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.data = {'normalized_players': {key: {'position': 'WR', 'name': key, 'birth_date': '2000-01-01T00:00:00Z', 'unused_blob': 'x' * 1000}
            for key in ('player-old', 'player-new', 'player-stay')}}

    def test_full_and_spawned_compact_evidence_parity(self):
        compact = compact_fois_input(self.data)
        self.assertNotIn('unused_blob', compact['normalized_players']['player-old'])
        self.assertEqual(compact['normalized_players']['player-old']['birth_date'], self.data['normalized_players']['player-old']['birth_date'])
        with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn')) as pool:
            spawned = pool.submit(historical_probe, compact).result(timeout=30)
        full = historical_probe(self.data)
        self.assertEqual(full, spawned)
        self.assertEqual((full[0]['optimal_points'], full[1]['optimal_points']), (22, 50))
        impact = next(row for row in full[2]['dimensions'] if row['name'] == 'lineup_impact')
        self.assertTrue(impact['evidence_available'])
        self.assertIn('28.00', impact['explanation'])

    def test_missing_normalized_positions_is_not_supported_zero(self):
        result = historical_probe({})
        self.assertIsNone(result[0]['optimal_points'])
        self.assertIsNone(result[1]['optimal_points'])
        self.assertFalse(next(row for row in result[2]['dimensions'] if row['name'] == 'lineup_impact')['evidence_available'])

    def test_complete_supported_zero_is_available(self):
        store = IdentityStore(self.data['normalized_players'])
        for row in store.rows:
            if row['entity_type'] == 'player_week':
                row['payload']['points'] = 0
        states = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))
        result, _ = states._lineup_and_production('league-a', 'league-a:franchise:1',
            HistoricalBoundary(2025, week=5), {'player-old', 'player-stay'}, ('WR',))
        self.assertEqual(result.optimal_points, 0)
        self.assertFalse(result.reason_codes)

    def test_partial_weekly_coverage_fails_closed(self):
        store = IdentityStore(self.data['normalized_players'])
        store.rows = [row for row in store.rows if row.get('player_id') != 'player-stay']
        states = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))
        result, _ = states._lineup_and_production('league-a', 'league-a:franchise:1',
            HistoricalBoundary(2025, week=5), {'player-old', 'player-stay'}, ('WR',))
        self.assertIsNone(result.optimal_points)
        self.assertIn('incomplete_historical_player_week_coverage', result.reason_codes)

    def test_slot_eligibility_scoring_and_league_separation(self):
        for league, slots, positions, expected in (
            ('day', ('REC_FLEX', 'SUPER_FLEX'), ('WR', 'QB', 'RB'), 45),
            ('arkham', ('WRRB_FLEX', 'SUPER_FLEX'), ('RB', 'QB', 'TE'), 45),
            ('flex-first', ('FLEX', 'RB'), ('RB', 'WR', 'TE'), 45),
        ):
            with self.subTest(league=league):
                ids = ('p1', 'p2', 'p3')
                store = IdentityStore(dict(zip(ids, ({'position': pos} for pos in positions))), league)
                store.rows = [store._row(league, 'player_week', f'4:{pid}', {'points': value},
                    week=4, player_id=pid, franchise_id=f'{league}:franchise:1')
                    for pid, value in zip(ids, (30, 15, 10))]
                result, _ = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))._lineup_and_production(
                    league, f'{league}:franchise:1', HistoricalBoundary(2025, week=5), set(ids), slots)
                self.assertEqual(result.optimal_points, expected)
                self.assertEqual(len(set(result.optimal_starters)), 2)

    def test_unsupported_slot_does_not_disappear(self):
        store = IdentityStore(self.data['normalized_players'])
        result, _ = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))._lineup_and_production(
            'league-a', 'league-a:franchise:1', HistoricalBoundary(2025, week=5), {'player-old'}, ('WR', 'UNKNOWN'))
        self.assertIsNone(result.optimal_points)
        self.assertIn('unsupported_historical_lineup_slots', result.reason_codes)

    def test_conflicting_duplicate_production_fails_closed(self):
        store = IdentityStore(self.data['normalized_players'])
        store.rows.append(store._row('league-a', 'player_week', 'conflict', {'points': 999},
            week=4, player_id='player-old', franchise_id='league-a:franchise:2'))
        result, _ = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))._lineup_and_production(
            'league-a', 'league-a:franchise:1', HistoricalBoundary(2025, week=5), {'player-old'}, ('WR',))
        self.assertIsNone(result.optimal_points)


class HistoricalMarketIntegrityTests(unittest.TestCase):
    def evaluate(self, incoming=None, outgoing=None, extra=()):
        store = IdentityStore({key: {'position': 'WR'} for key in ('player-old', 'player-new', 'player-stay')})
        quotes = [quote('player-stay'), *(item for item in (incoming, outgoing) if item is not None), *extra]
        history = HistoricalIntelligenceService(store, quotes)
        states = HistoricalFranchiseStateService(history)
        event = history.transaction_history('league-a')[0]
        return HistoricalTransactionIntelligenceService(history, states).evaluate_trade('league-a', event.event_id).sides[0].process

    def test_compatible_prices_are_usable(self):
        result = self.evaluate(quote('player-new', 550), quote('player-old', 500))
        self.assertTrue(result.market_comparable)
        self.assertEqual(result.market_coverage_ratio, 1)
        self.assertTrue(next(row for row in result.dimensions if row.name == 'value_fairness').evidence_available)

    def test_incompatible_provider_normalization_context_and_concept(self):
        for field, value in (('provider', 'other'), ('normalization_version', 'raw-10000'),
                             ('market_context_id', 'other-scoring'), ('value_concept', 'intrinsic_utility'),
                             ('comparison_identity', ('normalized-market', 'raw-10000', 'test-format', 'test-method', 'canonical'))):
            with self.subTest(field=field):
                result = self.evaluate(quote('player-new', **{field: value}), quote('player-old'))
                self.assertFalse(result.market_comparable)
                self.assertTrue('incompatible' in result.market_unavailable_reason or 'not_market' in result.market_unavailable_reason)
                self.assertEqual(result.classification.value, 'insufficient_evidence')
                for name in ('package_quality', 'scarcity'):
                    self.assertFalse(next(row for row in result.dimensions if row.name == name).evidence_available)

    def test_unknown_comparison_metadata_fails_closed(self):
        result = self.evaluate(quote('player-new', normalization_version=None), quote('player-old'))
        self.assertFalse(result.market_comparable)
        self.assertIn('identity_unavailable', result.market_unavailable_reason)

    def test_missing_player_and_partial_package_are_not_fairness(self):
        result = self.evaluate(outgoing=quote('player-old'))
        self.assertFalse(result.market_comparable)
        self.assertIn('player-new', result.missing_asset_ids)
        self.assertLess(result.market_coverage_ratio, 1)

    def test_future_quote_is_not_eligible_and_latest_eligible_wins(self):
        result = self.evaluate(quote('player-new', 500), quote('player-old'), extra=(
            quote('player-new', 550, occurred_at='2025-09-30T00:00:00Z'),
            quote('player-new', 900, occurred_at='2025-10-02T00:00:00Z')))
        self.assertEqual(result.known_incoming_value, 550)
        result = self.evaluate(quote('player-new', occurred_at='2025-10-02T00:00:00Z'), quote('player-old'))
        self.assertFalse(result.market_comparable)

    def test_sparse_store_adapter_preserves_semantics_and_withholds_legacy(self):
        from tests.test_market_observation_producer_identity import prepared, checkpoint
        from src.core.intelligence_memory.pipeline import CheckpointPipeline
        with tempfile.TemporaryDirectory() as temp:
            store = IntelligenceCheckpointStore(Path(temp) / 'market.db')
            data, asset = prepared()
            evidence = CheckpointPipeline._market_observations(data, 'player:1')
            point = checkpoint('explicit', asset['layers']['market_value']['value'], '2026-09-01T00:00:00Z')
            store.put_sparse(point, market_context_id='same', provider_evidence=evidence)
            valid = store.global_market_checkpoints(asset_id='1')[0]
            self.assertEqual(valid.value_concept, 'canonical_market')
            self.assertEqual(valid.comparison_identity[:2], ('external_market_normalized_index', '0-1000'))
            store.put_sparse(replace(point, checkpoint_id='legacy', timestamp='2026-09-02T00:00:00Z'),
                market_context_id='same', provider_evidence=tuple(replace(row, metadata={}) for row in evidence))
            with store._connect() as connection:
                before = [tuple(row) for row in connection.execute('SELECT * FROM global_market_observations')]
            legacy = store.global_market_checkpoints(asset_id='1')[-1]
            self.assertIsNone(legacy.value_concept)
            self.assertEqual(legacy.comparison_identity, ())
            with store._connect() as connection:
                self.assertEqual(before, [tuple(row) for row in connection.execute('SELECT * FROM global_market_observations')])

    def test_exact_pick_and_player_share_supported_price_units_not_asset_identity(self):
        from copy import deepcopy
        from tests.test_market_observation_producer_identity import prepared
        from src.core.valuation.observation_identity import observation_evidence
        from src.core.historical_intelligence.market_comparison import retained_comparison_identity
        data, _ = prepared()
        player = data['market_data']['providers']['FantasyCalc']['1']
        pick = deepcopy(player)
        pick.update(pick_type='exact', year=2027, round=1, exact_slot=4)
        def identity(row):
            value = row['normalization_reference']['normalized_value']
            evidence = observation_evidence([('FantasyCalc', row, value)], canonical_value=value)
            return retained_comparison_identity(evidence['observations'][0]['metadata']['comparison_semantics'], ('FantasyCalc',))
        self.assertEqual(identity(player), identity(pick))
        changed = deepcopy(pick)
        changed['format_details']['num_teams'] = 10
        self.assertNotEqual(identity(player), identity(changed))

    def test_genuine_zero_prices_are_not_missing(self):
        result = self.evaluate(quote('player-new', 0), quote('player-old', 0))
        self.assertTrue(result.market_comparable)
        self.assertEqual(next(row for row in result.dimensions if row.name == 'value_fairness').assessment, 'balanced')


class BehavioralIntegrityTests(unittest.TestCase):
    def test_unpriced_partial_or_incomparable_trades_are_not_price_preferences(self):
        for coverage, comparable in ((0, False), (.5, False), (1, False)):
            rows = tuple(replace(trade(str(index)), known_incoming_value=0, known_outgoing_value=0,
                market_coverage_ratio=coverage, market_comparable=comparable) for index in range(5))
            result = profile(rows)
            self.assertEqual(dimension(result, 'price_behavior').sample_count, 0)
            self.assertEqual(dimension(result, 'price_behavior').tendency, 'insufficient_evidence')
            self.assertEqual(result.transaction_count, 5)
            self.assertEqual(dimension(result, 'package_style').sample_count, 5)

    def test_large_trade_counts_as_one_independent_decision(self):
        row = trade('one', incoming=tuple(f'player:{i}' for i in range(12)), incoming_types=('player',)*12,
            incoming_positions=('WR',)*12)
        result = profile((row, row))
        self.assertEqual(result.transaction_count, 1)
        for key in ('asset_direction', 'positional', 'package_style', 'package_preference'):
            item = dimension(result, key)
            self.assertEqual(item.sample_count, 1)
            self.assertEqual(item.confidence, 'low')
            self.assertEqual(item.tendency, 'insufficient_evidence')
        self.assertEqual(dimension(result, 'positional').supporting_asset_counts['acquire_WR'], 12)

    def test_zero_prices_with_complete_admission_can_support_balanced_behavior(self):
        rows = tuple(replace(trade(str(index)), known_incoming_value=0, known_outgoing_value=0,
            market_coverage_ratio=1, market_comparable=True) for index in range(5))
        self.assertEqual(dimension(profile(rows), 'price_behavior').tendency, 'balanced')

    def test_shared_package_roundtrip_both_orientations_and_all_classes(self):
        classes = [(("player",), ("pick",)), (("pick",), ("player",)), (("pick",), ("pick",)),
            (("player",), ("player",)), (("player",), ("player", "player")),
            (("player", "player"), ("player",)), (("player", "player"), ("player", "player")),
            (("player", "pick"), ("player",)), (("pick", "pick"), ("player",))]
        for incoming, outgoing in classes:
            with self.subTest(incoming=incoming, outgoing=outgoing):
                rows = tuple(trade(str(index), incoming=tuple(f'i{n}' for n in range(len(incoming))),
                    outgoing=tuple(f'o{n}' for n in range(len(outgoing))), incoming_types=incoming,
                    outgoing_types=outgoing, incoming_positions=(), outgoing_positions=(), partner='old-partner')
                    for index in range(6))
                result = profile(rows)
                self.assertEqual(dimension(result, 'package_preference').tendency, package_shape(incoming, outgoing))
                context = build_trade_evidence_context({'league': {'league_id': 'league-a'},
                    'gm_behavioral_intelligence': {'2': result.contract()}})
                def assets(types):
                    return tuple(TradeAsset(str(index), kind, kind, None, None, None, 500, None, 0, 1)
                                 for index, kind in enumerate(types))
                match = assess_historical_fit(context, partner_roster_id=2, active_roster_id=1,
                    partner_receives=assets(incoming), active_receives=assets(outgoing))
                self.assertIn('PACKAGE_STYLE_MATCH', match['reason_codes'])
                self.assertTrue(match['evidence_references'])
                wrong = assess_historical_fit(context, partner_roster_id=2, active_roster_id=1,
                    partner_receives=assets(('player',)), active_receives=assets(('player',) if package_shape(incoming, outgoing).startswith('multi_asset') else ('player',)*3))
                self.assertNotIn('PACKAGE_STYLE_MATCH', wrong['reason_codes'])

    def test_one_for_one_types_and_mixed_package_orientation_are_not_false_matches(self):
        self.assertNotEqual(package_shape(('player',), ('pick',)), package_shape(('pick',), ('player',)))
        self.assertNotEqual(package_shape(('player',), ('player',)), package_shape(('player',), ('pick',)))
        self.assertNotEqual(package_shape(('player', 'pick'), ('player',)), package_shape(('player',), ('player', 'pick')))

    def test_trade_count_and_observed_seasons_are_factual(self):
        for years in ((2025,)*5, (2015, 2017, 2019, 2022, 2025)):
            facts = FOISFacts('a', 'a:franchise:1', 'owner', (),
                trades=tuple(trade(str(index), season=year) for index, year in enumerate(years)))
            result = FOISEngine().evaluate(facts)
            self.assertIn(f'{len(set(years))} observed season', result.tendencies[0])
            self.assertNotIn('Selective', result.tendencies[0])

    def test_losing_season_does_not_establish_rebuild_intent(self):
        result = CompetitiveCycleAnalyzer().analyze((season(2025, wins=2, losses=12, finish=10, playoff=False),))
        self.assertEqual(result.timeline[0].state, 'poor_results')
        self.assertIn('not established', result.timeline[0].explanation)
        explicit = CompetitiveCycleAnalyzer().analyze((season(2025, wins=2, losses=12, finish=10, playoff=False, rebuilding=True),))
        self.assertEqual(explicit.timeline[0].state, 'rebuild')

    def test_zero_history_honesty_and_category_strengths(self):
        result = FOISEngine().evaluate(FOISFacts('a', 'a:franchise:1', 'owner', ()))
        self.assertIn('unavailable', result.category_scores[0].explanation.casefold())
        self.assertNotIn('None/100', result.category_scores[0].explanation)
        titles = FOISEngine().evaluate(FOISFacts('a', 'a:franchise:1', 'owner',
            tuple(season(2020+i, title=True) for i in range(3))))
        self.assertIsNone(titles.overall_score)
        self.assertTrue(titles.strengths)

    def test_intent_wording_does_not_fragment_observed_poor_results_duration(self):
        rows = tuple(season(2020 + index, wins=2, losses=12, finish=10, playoff=False,
                           rebuilding=index < 2) for index in range(4))
        result = CompetitiveCycleAnalyzer().analyze(rows)
        self.assertEqual(len(result.competitive_cycles), 1)
        self.assertEqual(result.competitive_cycles[0].duration, 4)
        self.assertEqual(result.competitive_cycles[0].cycle_type, 'rebuild_or_poor_results')

    def test_behavior_is_league_specific(self):
        a = profile(tuple(trade(str(i)) for i in range(5)), league='day', gm='same-owner')
        b = profile((), league='arkham', gm='same-owner')
        self.assertNotEqual(a.semantic_identity, b.semantic_identity)
        self.assertEqual(b.transaction_count, 0)


class PersistedEvidencePreservationTests(unittest.TestCase):
    def test_automatic_generation_preserves_legacy_grade_but_prepares_current_behavior(self):
        with tempfile.TemporaryDirectory() as root:
            repo = FOISRepository(Path(root) / 'fois.sqlite3')
            service = FOISService(repo)
            data = {'league': {'league_id': 'a', 'season': '2026'},
                'teams': [{'roster_id': 1, 'owner_id': 'owner', 'owner': 'Owner', 'players': []}],
                'fois_history': {'1': {'seasons': [], 'trades': [], 'drafts': [], 'waivers': []}}}
            first = service._generate_sync(data)[0]
            with repo._connection() as connection:
                old = json.loads(connection.execute('SELECT payload FROM fois_scores_v2').fetchone()[0])
                old.pop('evidence_integrity_version')
                connection.execute('UPDATE fois_scores_v2 SET payload=?', (json.dumps(old),))
                connection.commit()
                before = tuple(connection.execute('SELECT * FROM fois_scores_v2').fetchone())
            data['fois_history']['1']['trades'] = [asdict(trade(str(index), owner='owner')) for index in range(5)]
            retained = service._generate_sync(data)[0]
            self.assertEqual(first.overall_score, retained.overall_score)
            self.assertIsNone(retained.evidence_integrity_version)
            self.assertEqual(service.status()['retained_assessments_not_revalidated'], 1)
            self.assertEqual(data['gm_behavioral_intelligence']['1']['transaction_count'], 5)
            with repo._connection() as connection:
                self.assertEqual(before, tuple(connection.execute('SELECT * FROM fois_scores_v2').fetchone()))

    def test_existing_legacy_scores_and_snapshots_remain_byte_identical(self):
        with tempfile.TemporaryDirectory() as root:
            repo = FOISRepository(Path(root) / 'fois.sqlite3')
            score = FOISEngine().evaluate(FOISFacts('a', 'a:franchise:1', 'owner', ()))
            repo.save(score, 'original')
            with repo._connection() as connection:
                old = json.loads(connection.execute('SELECT payload FROM fois_scores_v2').fetchone()[0])
                old.pop('evidence_integrity_version')
                connection.execute('UPDATE fois_scores_v2 SET payload=?', (json.dumps(old),))
                connection.commit()
                before = tuple(connection.execute('SELECT * FROM fois_scores_v2').fetchone())
                snapshots = [tuple(row) for row in connection.execute('SELECT * FROM fois_snapshot_history')]
            self.assertFalse(repo.save(replace(score, overall_score=99), 'corrected-input'))
            with repo._connection() as connection:
                self.assertEqual(before, tuple(connection.execute('SELECT * FROM fois_scores_v2').fetchone()))
                self.assertEqual(snapshots, [tuple(row) for row in connection.execute('SELECT * FROM fois_snapshot_history')])
            self.assertIn('NOT_REVALIDATED', ' '.join(repo.league('a', score.model_version)[0].warnings))

    def test_exact_lineage_rejects_fractional_or_missing_selection_identity(self):
        with tempfile.TemporaryDirectory() as root:
            store = IntelligenceCheckpointStore(Path(root) / 'intelligence.sqlite3')
            valid = ExactPickLineage('exact', 'a', 'draft', 2027, 1, 4, '2', None, 'player:new')
            for change in ({'selection': 1.04}, {'selection': True}, {'selection': 0}, {'league_id': ''}, {'lineage_id': ''}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    store.put_exact_lineage(replace(valid, **change))
            with store._connect() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM exact_pick_lineage').fetchone()[0], 0)

    def test_new_exact_lineage_is_league_draft_selection_scoped_and_legacy_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            store = IntelligenceCheckpointStore(Path(root) / 'intelligence.sqlite3')
            legacy = PickLineage('old', 'pick:2027:1:1', 2027, 1, '1', '1', 'player:old')
            store.put_lineage(legacy)
            with store._connect() as connection:
                before = tuple(connection.execute('SELECT * FROM pick_lineage').fetchone())
            for league, selection in (('day', 1), ('arkham', 1), ('day', 2)):
                row = ExactPickLineage(f'{league}:{selection}', league, 'draft', 2027, 1, selection,
                    '1', None, f'player:{selection}')
                self.assertTrue(store.put_exact_lineage(row))
                self.assertFalse(store.put_exact_lineage(row))
            with store._connect() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM exact_pick_lineage').fetchone()[0], 3)
                self.assertEqual(before, tuple(connection.execute('SELECT * FROM pick_lineage').fetchone()))
                self.assertIsNone(connection.execute('SELECT original_roster_id FROM exact_pick_lineage LIMIT 1').fetchone()[0])
            with self.assertRaises(ValueError):
                store.put_exact_lineage(ExactPickLineage('bad', '', 'draft', 2027, 1, 1, '1', None, 'player:x'))
