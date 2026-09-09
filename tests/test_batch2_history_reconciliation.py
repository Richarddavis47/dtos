"""Source-to-canonical reconciliation without changing historical grading."""
import unittest
from unittest.mock import patch

from src.core.history_context.store import CanonicalHistoryStore
from src.core.historical_intelligence.service import HistoricalIntelligenceService


class Batch2HistoryReconciliationTests(unittest.TestCase):
    def test_unpaired_teams_do_not_become_a_fictitious_matchup(self):
        rows = self.records({'league': {}, 'matchups': {'17': [
            {'matchup_id': None, 'roster_id': 1, 'points': 100, 'players_points': {'a': 10}},
            {'matchup_id': None, 'roster_id': 2, 'points': 90, 'players_points': {'b': 9}},
        ]}})
        self.assertFalse(any(row['entity_type'] == 'matchup' for row in rows))
        self.assertEqual(sum(row['entity_type'] == 'player_week' for row in rows), 2)

    def test_standing_decimals_and_missing_matchup_are_not_discarded(self):
        rows = self.records({'league': {'settings': {'playoff_week_start': 15}},
            'rosters': [{'roster_id': 1, 'settings': {'fpts': 1234, 'fpts_decimal': 56}}],
            'matchups': {'15': [{'matchup_id': 1, 'roster_id': 1, 'points': None},
                                {'matchup_id': 1, 'roster_id': 2, 'points': 0}]}})
        standing = next(row['payload'] for row in rows if row['entity_type'] == 'season_standing')
        self.assertEqual(standing['points_for'], 1234.56)
        self.assertIsNone(standing['points_against'])
        matchup = next(row['payload'] for row in rows if row['entity_type'] == 'matchup')
        self.assertIsNone(matchup['winner'])
        self.assertIsNone(matchup['tie'])
        self.assertTrue(matchup['postseason_context'])

    def test_real_zero_tie_and_commissioner_override(self):
        from src.core.history_context.results import matchup_result
        sides = [{'roster_id': 1, 'points': 0}, {'roster_id': 2, 'points': 0}]
        self.assertTrue(matchup_result(sides, playoff_week=15, week=1)['tie'])
        sides[0]['custom_points'] = 5
        result = matchup_result(sides, playoff_week=15, week=1)
        self.assertEqual(result['winner'], 1)
        self.assertFalse(result['postseason_context'])

    def records(self, facts):
        store = CanonicalHistoryStore()
        with patch.object(store, "_facts", return_value=facts):
            return store._season_records("league-a", 2025)

    def test_multiple_drafts_keep_selection_and_franchise_identity(self):
        records = self.records({"league": {}, "draft_picks": [
            {"draft_id": "rookie", "pick_no": 1, "roster_id": 3, "player_id": "a"},
            {"draft_id": "supplemental", "pick_no": 1, "roster_id": 4, "player_id": "b"},
        ]})
        selections = [row for row in records if row["entity_type"] == "draft_pick"]
        self.assertEqual(len({row["record_key"] for row in selections}), 2)
        events = [HistoricalIntelligenceService._normalize(row) for row in selections]
        self.assertEqual(events[0].franchise_ids, ("league-a:franchise:3",))
        self.assertEqual(events[1].franchise_ids, ("league-a:franchise:4",))
        self.assertEqual(events[0].attributes["draft_id"], "rookie")

    def test_consolation_cannot_supply_champion(self):
        rows = self.records({"league": {}, "losers_bracket": [
            {"m": 1, "p": 1, "w": 9, "l": 10},
        ]})
        self.assertFalse(any(row["entity_type"] == "playoff_result" for row in rows))

    def test_faab_and_bid_evidence_survive_normalization(self):
        rows = self.records({"league": {}, "transactions": {"1": [{
            "transaction_id": "trade-a", "type": "trade", "status": "complete",
            "roster_ids": [1, 2], "waiver_budget": [{"sender": 1, "receiver": 2, "amount": 20}],
            "settings": {"waiver_bid": 0},
        }]}})
        event = HistoricalIntelligenceService._normalize(next(row for row in rows if row["entity_type"] == "trade"))
        self.assertEqual(event.attributes["waiver_budget"][0]["amount"], 20)
        self.assertEqual(event.attributes["settings"]["waiver_bid"], 0)
