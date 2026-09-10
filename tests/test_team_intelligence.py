"""Team grading contract: compare dimensions, not an interchangeable scalar."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from src.core.team_intelligence import build_team_intelligence
from src.core.intelligence.roster_grading import PlayerGradingEvidence, grade_roster_evidence


def inputs(strengths, games=0):
    decisions, grading = {}, {}
    for rid, strength in enumerate(strengths, 1):
        decisions[rid] = SimpleNamespace(profile=SimpleNamespace(
            wins=games, losses=0, ties=0, picks=({'round': 1},), known_ages=(25,)))
        grading[rid] = grade_roster_evidence(league_id='a', roster_id=rid, generation='g',
            players=(PlayerGradingEvidence(str(rid), strength * 10, strength, strength, 50, 80, 90, 85),),
            actual_starter_ids=(str(rid),), optimal_starter_ids=(str(rid),),
            actual_points=strength, optimal_points=strength, legal_backup_points=0)
    return decisions, grading


def build(strengths, games=0):
    decisions, grading = inputs(strengths, games)
    return build_team_intelligence(decisions, {}, {}, {}, grading=grading)


class TeamIntelligenceTests(unittest.TestCase):
    def test_strong_lineup_grade_does_not_manufacture_overall(self):
        cards, _ = build((95, 85, 75, 65, 55, 45, 35, 25, 15, 5))
        self.assertEqual(cards[1].starting_lineup.rank, 1)
        self.assertIn(cards[1].starting_lineup.grade, {'A+', 'A'})
        self.assertIsNone(cards[1].overall.score)

    def test_identical_dimensions_receive_identical_grades(self):
        cards, _ = build((60, 60, 60))
        self.assertEqual({(c.starting_lineup.score, c.starting_lineup.rank) for c in cards.values()}, {(50, 1)})

    def test_weak_lineup_cannot_outrank_stronger_lineup(self):
        cards, _ = build((90, 50, 10))
        self.assertEqual([cards[i].starting_lineup.rank for i in (1, 2, 3)], [1, 2, 3])

    def test_preseason_does_not_invent_probabilities_or_wins(self):
        cards, _ = build((80, 60, 40))
        for card in cards.values():
            self.assertTrue(card.preseason)
            self.assertIsNone(card.projected_wins)
            self.assertIsNone(card.playoff_odds)
            self.assertIsNone(card.championship_odds)

    def test_completed_games_preserve_actual_season_state(self):
        cards, _ = build((80, 60, 40), games=1)
        self.assertFalse(any(card.preseason for card in cards.values()))

    def test_missing_window_is_neither_contender_nor_rebuilder(self):
        cards, summary = build((95, 50, 5))
        self.assertTrue(all(c.current_window.value == 'Unavailable' for c in cards.values()))
        self.assertEqual((summary.contenders, summary.rebuilders), (0, 0))

    def test_dimension_percentiles_bounded_and_ranks_complete(self):
        cards, _ = build((90, 70, 50, 30, 10))
        self.assertTrue(all(0 <= c.starting_lineup.percentile <= 100 for c in cards.values()))
        self.assertEqual(sorted(c.starting_lineup.rank for c in cards.values()), [1, 2, 3, 4, 5])

    def test_market_cannot_fill_dynasty_or_position_grade(self):
        cards, _ = build((90, 60, 30))
        self.assertIsNotNone(cards[1].market_asset_strength.score)
        self.assertIsNone(cards[1].dynasty.score)
        self.assertTrue(all(p.score is None for p in cards[1].positions.values()))

    def test_unchanged_generation_is_deterministic(self):
        self.assertEqual(build((88, 72, 61, 43)), build((88, 72, 61, 43)))

    def test_unsupported_overall_confidence_is_not_inherited(self):
        cards, _ = build((80, 50, 20))
        self.assertTrue(all(c.confidence == 0 for c in cards.values()))

    def test_legacy_call_without_generation_is_rejected(self):
        decisions, _ = inputs((80, 50))
        with self.assertRaisesRegex(ValueError, 'legacy scalar fallback is retired'):
            build_team_intelligence(decisions, {}, {}, {})

    def test_pick_evidence_stays_independent_of_unknown_player_utility(self):
        decisions, grading = inputs((70, 70))
        decisions[1].profile.picks = tuple({'round': 1} for _ in range(12))
        cards, _ = build_team_intelligence(decisions, {}, {}, {}, grading=grading)
        self.assertGreater(cards[1].draft_capital.score, cards[2].draft_capital.score)
        self.assertIsNone(cards[1].future_outlook.score)
        grading[2] = replace(grading[2], generation='other')
        with self.assertRaisesRegex(ValueError, 'mixed-generation'):
            build_team_intelligence(decisions, {}, {}, {}, grading=grading)
