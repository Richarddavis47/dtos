"""Canonical source facts, independent of FOIS grading and presentation."""
import unittest

from src.core.history_context.playoffs import playoff_facts


class PlayoffFactsTests(unittest.TestCase):
    def test_documented_dependency_forms_resolve_only_observed_results(self):
        semis = [{'m': 1, 'r': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2},
                 {'m': 2, 'r': 1, 't1': 3, 't2': 4, 'w': 4, 'l': 3}]
        final = {'m': 3, 'r': 2, 'p': 1, 't1': {'w': 1}, 't2': {'w': 2}, 'w': 4, 'l': 1}
        inline = playoff_facts(semis + [final])
        explicit = playoff_facts(semis + [{**final, 't1': 1, 't2': 4,
                                          't1_from': {'w': 1}, 't2_from': {'w': 2}}])
        self.assertEqual(inline, explicit)
        self.assertEqual(inline['semifinal_roster_ids'], ['1', '2', '3', '4'])
        semis[1]['w'] = None
        pending = playoff_facts(semis + [{**final, 'w': None, 'l': None}])
        self.assertEqual(pending['championship_roster_ids'], ['1'])
        self.assertIsNone(pending['champion_roster_id'])

    def test_six_team_byes_and_championship_dependencies(self):
        bracket = [
            {"m": 1, "r": 1, "t1": 3, "t2": 6, "w": 3, "l": 6},
            {"m": 2, "r": 1, "t1": 4, "t2": 5, "w": 5, "l": 4},
            {"m": 3, "r": 2, "t1": 1, "t2": 3, "w": 1, "l": 3},
            {"m": 4, "r": 2, "t1": 2, "t2": 5, "w": 5, "l": 2},
            {"m": 5, "r": 2, "t1": 6, "t2": 4, "w": 6, "l": 4, "p": 5},
            {"m": 6, "r": 3, "t1": 1, "t2": 5, "w": 5, "l": 1,
             "t1_from": {"w": 3}, "t2_from": {"w": 4}, "p": 1},
            {"m": 7, "r": 3, "t1": 3, "t2": 2, "w": 2, "l": 3, "p": 3},
        ]
        facts = playoff_facts(bracket)
        self.assertEqual(facts["qualified_roster_ids"], ["1", "2", "3", "4", "5", "6"])
        self.assertEqual(facts["semifinal_roster_ids"], ["1", "2", "3", "5"])
        self.assertEqual(facts["first_round_bye_roster_ids"], ["1", "2"])
        self.assertEqual(facts["champion_roster_id"], 5)
        self.assertEqual(facts["placements"], {"1": 5, "2": 1, "3": 2, "4": 3, "5": 6, "6": 4})
        self.assertEqual(facts["reason_codes"], [])
        self.assertEqual(facts, playoff_facts(list(reversed(bracket))))

    def test_missing_and_conflicting_championship_are_not_guessed(self):
        self.assertIsNone(playoff_facts([])["champion_roster_id"])
        facts = playoff_facts([{"m": 1, "p": 1, "w": 2}, {"m": 2, "p": 1, "w": 3}])
        self.assertIsNone(facts["champion_roster_id"])
        self.assertIn("championship_conflict", facts["reason_codes"])

    def test_incomplete_playoffs_do_not_invent_a_champion(self):
        facts = playoff_facts([{"m": 1, "p": 1, "t1": 1, "t2": None, "t2_from": {"w": 8}}])
        self.assertIsNone(facts["champion_roster_id"])
        self.assertEqual(facts["placements"], {})
        self.assertIn("semifinal_dependency_unavailable", facts["reason_codes"])

    def test_conflicting_match_identity_does_not_depend_on_row_order(self):
        bracket = [{"m": 1, "p": 1, "w": 1}, {"m": 1, "p": 1, "w": 2}]
        facts = playoff_facts(bracket)
        self.assertIsNone(facts['champion_roster_id'])
        self.assertEqual(facts, playoff_facts(list(reversed(bracket))))
        self.assertIn('bracket_match_identity_conflict', facts['reason_codes'])
