"""Evidence-week admission, real spawn regression and non-destructive guards."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.core.historical_franchise_state import (
    HistoricalFranchiseStateService, EvidenceCoverage, ReconstructionAvailability,
)
from src.core.historical_intelligence import HistoricalIntelligenceService
from src.core.historical_transaction_intelligence.service import (
    HistoricalTransactionIntelligenceService, _lineup_comparison_reason,
)
from tests.test_historical_franchise_state import FixtureStore
from tests.test_historical_transaction_intelligence import checkpoint


class HistoricalWeekAdmissionTests(unittest.TestCase):
    def states(self):
        history = HistoricalIntelligenceService(FixtureStore(), (checkpoint('player-old', '2025-09-20T00:00:00Z', 500),))
        service = HistoricalFranchiseStateService(history)
        before, after = service.around_event('league-a', '1', history.transaction_history('league-a')[0].event_id)
        def supported(state, points):
            coverage = dict(state.coverage)
            coverage['lineup'] = EvidenceCoverage(ReconstructionAvailability.COMPLETE, 90)
            players = tuple(replace(asset, position=asset.position or 'WR') for asset in state.players)
            return replace(state, players=players, coverage=coverage,
                           lineup=replace(state.lineup, optimal_points=points, evidence_week=4,
                                          source_references=('controlled-week-4',)))
        return supported(before, 10), supported(after, 14)

    def test_numeric_cross_week_is_rejected_independently_of_selection(self):
        before, after = self.states()
        after = replace(after, lineup=replace(after.lineup, evidence_week=3))
        process = HistoricalTransactionIntelligenceService._process(before, after)
        dimension = next(d for d in process.dimensions if d.name == 'lineup_impact')
        self.assertFalse(dimension.evidence_available)
        self.assertIsNone(dimension.before_points)
        self.assertEqual(dimension.evidence_reason, 'no_common_supported_historical_week')

    def test_context_rules_boundary_and_coverage_are_required(self):
        before, after = self.states()
        self.assertIsNone(_lineup_comparison_reason(before, after))
        variants = (
            replace(after, league_id='another-league'),
            replace(after, franchise_id='league-a:franchise:2'),
            replace(after, scoring_settings={'rec': 999}),
            replace(after, roster_positions=('QB',)),
            replace(after, boundary=replace(after.boundary, week=3)),
            replace(after, lineup=replace(after.lineup, evidence_week=after.boundary.week)),
            replace(after, players=tuple(replace(p, position=None) for p in after.players)),
            replace(after, coverage={}),
            replace(after, lineup=replace(after.lineup, source_references=())),
        )
        for invalid in variants:
            with self.subTest(state=invalid.state_id):
                self.assertIsNotNone(_lineup_comparison_reason(before, invalid))
                impact = next(d for d in HistoricalTransactionIntelligenceService._process(before, invalid).dimensions if d.name == 'lineup_impact')
                self.assertFalse(impact.evidence_available)

    def test_complete_zero_is_supported_missing_is_not(self):
        before, after = self.states()
        before = replace(before, lineup=replace(before.lineup, optimal_points=0))
        after = replace(after, lineup=replace(after.lineup, optimal_points=0))
        self.assertIsNone(_lineup_comparison_reason(before, after))
        self.assertIsNotNone(_lineup_comparison_reason(before, replace(after, lineup=replace(after.lineup, optimal_points=None))))

    def test_incomplete_submitted_evidence_is_not_zero_or_key_error(self):
        from tests.test_fois_evidence_integrity import IdentityStore
        from src.core.historical_franchise_state import HistoricalBoundary
        store = IdentityStore({'wr': {'position': 'WR'}, 'kicker': {'position': 'K'}})
        store.rows = [store._row('league-a', 'player_week', key, payload, week=4,
                                player_id=player, franchise_id='league-a:franchise:1')
                      for key, player, payload in (
                          ('wr', 'wr', {'points': 12}),
                          ('k1', 'kicker', {'points': 2, 'starter': True}),
                          ('k2', 'kicker', {'points': 3, 'starter': True}))]
        lineup, _ = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))._lineup_and_production(
            'league-a', 'league-a:franchise:1', HistoricalBoundary(2025, week=5), {'wr', 'kicker'}, ('WR',))
        self.assertEqual(lineup.optimal_points, 12)
        self.assertIsNone(lineup.actual_points)

    def test_historical_confidence_can_affect_rank_without_direct_fit_term(self):
        from services.trade_search_policy import rank_key
        row = {'evaluation': {'recommendation': 'FAIR / OPTIONAL', 'values': {'ratio': 1},
                              'provenance': {'evaluation_id': 'same'},
                              'dimensions': {'confidence': {'assessment': 'MEDIUM'},
                                             'historical_counterparty_evidence': {'score': 0}}}}
        direct = deepcopy(row)
        direct['evaluation']['dimensions']['historical_counterparty_evidence']['score'] = 3
        self.assertEqual(rank_key(row), rank_key(direct))
        supported = deepcopy(direct)
        from types import SimpleNamespace
        from src.core.trade_intelligence.confidence import evidence_confidence
        market = {'availability': 'full', 'sent': {'priced_assets': 1, 'asset_count': 1},
                  'received': {'priced_assets': 1, 'asset_count': 1}}
        strategy = {'horizons': {}, 'projection_coverage_complete': True,
                    'competitive_window': 'Contending', 'roster_capacity': {}}
        proposal = SimpleNamespace(assets_sent=(), assets_received=())
        profile = evidence_confidence(market, {'active': strategy, 'partner': strategy},
                    {'confidence': 'HIGH', 'evidence_references': ['supported-history']}, proposal, {})
        self.assertEqual(profile['assessment'], 'HIGH')
        supported['evaluation']['dimensions']['confidence'] = profile
        self.assertLess(rank_key(supported), rank_key(row))

    def test_prior_integrity_assessment_preserved_without_storage_rewrite(self):
        from src.core.fois.engine import FOISEngine
        from src.core.fois.facts import FOISFacts, SeasonResult
        from src.core.fois.repository import FOISRepository
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / 'retained.db')
            score = FOISEngine().evaluate(FOISFacts('league', 'league:franchise:1', 'manager',
                (SeasonResult(2024, 10, 4, 2, playoff=True),)))
            original = replace(score, evidence_integrity_version='fois-evidence-integrity-1')
            self.assertTrue(repository.save(original, 'prior-source'))
            with repository._connection() as connection:
                prior = [tuple(r) for r in connection.execute('SELECT * FROM fois_scores_v2')]
                snapshots = [tuple(r) for r in connection.execute('SELECT * FROM fois_snapshot_history')]
            self.assertFalse(repository.save(replace(score, overall_score=99), 'new-corrected-source'))
            retained = repository.get('league', 'league:franchise:1', score.model_version)
            self.assertFalse(retained.evidence_revalidated)
            self.assertEqual(retained.evidence_integrity_version, original.evidence_integrity_version)
            self.assertEqual(retained.generated_at, original.generated_at)
            with repository._connection() as connection:
                self.assertEqual(prior, [tuple(r) for r in connection.execute('SELECT * FROM fois_scores_v2')])
                self.assertEqual(snapshots, [tuple(r) for r in connection.execute('SELECT * FROM fois_snapshot_history')])

    def test_lineage_conflict_contract_is_narrow_and_keeps_first_write(self):
        from src.core.intelligence_memory.store import IntelligenceCheckpointStore
        from src.core.intelligence_memory.models import ExactPickLineage
        with tempfile.TemporaryDirectory() as directory:
            store = IntelligenceCheckpointStore(Path(directory) / 'memory.db')
            original = ExactPickLineage('first', 'league', 'draft', 2027, 4, 31, '1', '2', 'player')
            self.assertTrue(store.put_exact_lineage(original))
            self.assertFalse(store.put_exact_lineage(replace(original, original_roster_id='3', selecting_roster_id='4')))
            with store._connect() as connection:
                saved = connection.execute('SELECT * FROM exact_pick_lineage').fetchone()
                self.assertEqual(saved['original_roster_id'], '2')
                self.assertEqual(saved['selecting_roster_id'], '1')
            for invalid in (replace(original, season=2028), replace(original, round=3), replace(original, selected_player_id='other')):
                with self.assertRaisesRegex(ValueError, 'Conflicting'):
                    store.put_exact_lineage(invalid)

    def test_integrated_raw_source_full_and_actual_spawn_week_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'verification.json'
            result = subprocess.run([sys.executable, '-m', 'tools.validation.verify_historical_weeks', '--output', str(output)],
                                    capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(len(report['cases']), 15)
            self.assertTrue(all(c['passed'] and c['full_spawn_parity'] for c in report['cases']))
            scout = report['cases'][0]
            self.assertEqual(scout['weeks'], [3, 3])
            self.assertEqual(scout['points'], [10, 5])
            self.assertEqual(scout['classification'], 'defensible_optional')
            self.assertTrue(scout['market_comparable'])
            self.assertTrue(report['worker_reaped'])
            self.assertTrue(report['prior_contract_assessments_unchanged_full_and_spawn'])
