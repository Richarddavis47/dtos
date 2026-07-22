"""League-relative Team Intelligence grading and classification regressions."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.core.team_intelligence import CompetitiveWindow, build_team_intelligence


def decision(roster_id: int, strength: int, *, games: int = 0, picks: int | None = None) -> SimpleNamespace:
    pick_count = strength // 12 if picks is None else picks
    players = tuple({"id": f"{roster_id}-{index}", "player_id": f"{roster_id}-{index}", "age": 21 + (index % 11), "roster_slot": "Starter" if index < 7 else "Bench"} for index in range(12))
    profile = SimpleNamespace(
        roster_id=roster_id, wins=games, losses=0, ties=0, players=players,
        picks=tuple({"round": 1 if index < max(1, pick_count // 3) else 2 if index % 2 else 3} for index in range(pick_count)),
        draft_pick_count=pick_count, young_player_count=sum(player["age"] <= 24 for player in players),
        known_ages=tuple(player["age"] for player in players),
    )
    evaluation = SimpleNamespace(confidence=80)
    return SimpleNamespace(profile=profile, current_outlook=evaluation, future_outlook=evaluation, depth=evaluation, asset_health=evaluation)


def league_inputs(strengths: tuple[int, ...], *, games: int = 0):
    decisions = {index: decision(index, strength, games=games) for index, strength in enumerate(strengths, 1)}
    rooms = {index: {position: max(1, min(100, strength + adjustment)) for position, adjustment in {"QB": 5, "RB": -3, "WR": 3, "TE": -5}.items()} for index, strength in enumerate(strengths, 1)}
    players = {
        index: {f"{index}-{player}": SimpleNamespace(player_id=f"{index}-{player}", dynasty_value=max(1, min(100, strength + player)), rebuilder_value=max(1, min(100, strength + player)), trade_liquidity=max(1, min(100, strength)), risk="Low") for player in range(12)}
        for index, strength in enumerate(strengths, 1)
    }
    metrics = {
        index: {
            "Total Dynasty Value": strength * 12,
            "Starting-Lineup Dynasty Value": strength * 7,
            "Projected Weekly Starter Points": strength * 1.5,
            "Projected Floor": strength,
            "Projected Ceiling": strength * 2,
            "Market Liquidity": strength,
            "Contender Value": strength * 12,
            "Rebuild Value": strength * 12,
        }
        for index, strength in enumerate(strengths, 1)
    }
    return decisions, rooms, players, metrics


class TeamIntelligenceTests(unittest.TestCase):
    def test_elite_roster_cannot_receive_failing_grade(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((95, 85, 75, 65, 55, 45, 35, 25, 15, 5)))
        self.assertEqual(cards[1].overall.rank, 1)
        self.assertIn(cards[1].overall.grade, {"A+", "A"})
        self.assertNotEqual(cards[1].overall.grade, "F")

    def test_identical_teams_receive_identical_grades_and_ranks(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((60, 60, 60)))
        signatures = {(card.overall.score, card.overall.grade, card.overall.percentile, card.overall.rank) for card in cards.values()}
        self.assertEqual(signatures, {(50, "B+", 50, 1)})

    def test_weak_team_cannot_outrank_stronger_team(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((90, 50, 10)))
        self.assertLess(cards[1].overall.rank, cards[2].overall.rank)
        self.assertLess(cards[2].overall.rank, cards[3].overall.rank)
        self.assertTrue(cards[1].explanation)

    def test_preseason_uses_projection_label_not_standings(self) -> None:
        cards, summary = build_team_intelligence(*league_inputs((80, 60, 40), games=0))
        self.assertTrue(all(card.preseason for card in cards.values()))
        self.assertEqual(summary.season_label, "Preseason Projection")
        self.assertTrue(all(0 <= card.projected_wins <= 14 for card in cards.values()))
        self.assertTrue(all(5 <= card.playoff_odds <= 95 for card in cards.values()))
        self.assertTrue(all(1 <= card.championship_odds <= 60 for card in cards.values()))

    def test_completed_games_switch_season_label(self) -> None:
        cards, summary = build_team_intelligence(*league_inputs((80, 60, 40), games=1))
        self.assertFalse(any(card.preseason for card in cards.values()))
        self.assertEqual(summary.season_label, "Current Season")

    def test_homepage_counts_equal_card_classification_totals(self) -> None:
        cards, summary = build_team_intelligence(*league_inputs((95, 85, 75, 65, 55, 45, 35, 25, 15, 5)))
        contenders = sum(card.current_window in {CompetitiveWindow.ELITE_CONTENDER, CompetitiveWindow.CONTENDER} for card in cards.values())
        rebuilders = sum(card.current_window in {CompetitiveWindow.REBUILDING, CompetitiveWindow.FULL_REBUILD} for card in cards.values())
        self.assertEqual(summary.contenders, contenders)
        self.assertEqual(summary.rebuilders, rebuilders)

    def test_percentiles_are_bounded_and_ranks_are_complete(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((90, 70, 50, 30, 10)))
        self.assertTrue(all(0 <= card.overall.percentile <= 100 for card in cards.values()))
        self.assertEqual(sorted(card.overall.rank for card in cards.values()), [1, 2, 3, 4, 5])

    def test_position_grades_feed_overall_model(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((90, 60, 30)))
        card = cards[1]
        self.assertEqual(set(card.positions), {"QB", "RB", "WR", "TE"})
        self.assertTrue(all(grade.reasons for grade in card.positions.values()))
        self.assertGreater(card.overall.score, cards[3].overall.score)

    def test_power_rankings_are_deterministic(self) -> None:
        inputs = league_inputs((88, 72, 61, 43))
        first = build_team_intelligence(*inputs)
        second = build_team_intelligence(*inputs)
        self.assertEqual(first, second)

    def test_confidence_propagates_from_existing_evaluators(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((80, 50, 20)))
        self.assertTrue(all(card.confidence == 80 for card in cards.values()))

    def test_current_windows_are_mutually_exclusive_and_standardized(self) -> None:
        cards, _ = build_team_intelligence(*league_inputs((95, 85, 75, 65, 55, 45, 35, 25, 15, 5)))
        allowed = set(CompetitiveWindow)
        self.assertTrue(all(card.current_window in allowed for card in cards.values()))
        self.assertEqual(len(cards), sum(1 for card in cards.values() if card.current_window in allowed))

    def test_draft_capital_and_flexibility_are_independent(self) -> None:
        decisions, rooms, players, metrics = league_inputs((70, 70))
        decisions[1] = decision(1, 70, picks=12)
        decisions[2] = decision(2, 70, picks=1)
        cards, _ = build_team_intelligence(decisions, rooms, players, metrics)
        self.assertGreater(cards[1].draft_capital.score, cards[2].draft_capital.score)
        self.assertNotEqual(cards[1].roster_flexibility.rank, cards[2].roster_flexibility.rank)


if __name__ == "__main__":
    unittest.main()
