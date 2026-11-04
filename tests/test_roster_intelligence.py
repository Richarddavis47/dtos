"""Active roster adapter regressions after retirement of generic scalar grades."""
import unittest
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from src.core.intelligence.roster_grading import PlayerGradingEvidence, grade_roster_evidence
from tests.test_trade_intelligence import fixture_data


class RosterIntelligenceTests(unittest.TestCase):
    def test_evidence_order_does_not_change_dimensions(self):
        players = (PlayerGradingEvidence('a', 100, 90, 20, 70, 80),
                   PlayerGradingEvidence('b', 50, 60, 10, 60, 80))
        args = dict(league_id='a', roster_id=1, generation='g', actual_starter_ids=('a',),
                    optimal_starter_ids=('a',), actual_points=20, optimal_points=20, legal_backup_points=10)
        self.assertEqual(grade_roster_evidence(players=players, **args),
                         grade_roster_evidence(players=tuple(reversed(players)), **args))

    def test_price_cannot_establish_overall_identity(self):
        row = grade_roster_evidence(league_id='a', roster_id=1, generation='g',
            players=(PlayerGradingEvidence('a', 1000, None, None, None, 0),),
            actual_starter_ids=(), optimal_starter_ids=(), actual_points=None,
            optimal_points=None, legal_backup_points=None)
        self.assertIsNone(row.overall_grade)
        self.assertEqual(row.competitive_window, 'Unavailable')
        self.assertIsNone(row.dimensions['Optimal projected lineup'].value)

    def test_orchestrator_supplies_explicit_roster_report(self):
        result = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache()).analyze(fixture_data(), 1)
        self.assertEqual(set(result.roster.rooms), {'QB', 'RB', 'WR', 'TE'})
        for room in result.roster.rooms.values():
            self.assertIsNone(room.overall.score)
            self.assertIsNone(room.league_rank)
            self.assertTrue(room.reasoning)
        self.assertIn('Evidence Dimensions', result.roster.metrics)

    def test_player_cards_do_not_manufacture_grades(self):
        result = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache()).analyze(fixture_data(), 1)
        for player in result.roster.players.values():
            self.assertIsNone(player.dynasty_value)
            self.assertIsNone(player.contender_value)
            self.assertIsNone(player.overall_score)
            self.assertEqual(player.overall_grade, 'Unavailable')
            self.assertTrue(player.recommended_action)

    def test_league_comparisons_do_not_change_with_selected_franchise(self):
        data = fixture_data()
        engine = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache())
        first, second = engine.analyze(data, 1), engine.analyze(data, 2)
        self.assertEqual(first.context.evidence_generation, second.context.evidence_generation)
        self.assertNotEqual(first.context.snapshot_key, second.context.snapshot_key)
        self.assertEqual(first.roster.team_intelligence, second.roster.team_intelligence)
        self.assertEqual(first.roster.league_metrics, second.roster.league_metrics)
