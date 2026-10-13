"""Canonical publisher, retained readers and actual history route contracts."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tests import test_historical_tracker_phase2 as fixtures
from src.core.history_context.playoffs import admitted_playoff_result
from src.ui.badges import champion_badge, defending_champion


class PlayoffParticipantIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TrackerPhase2Tests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def publish(self, rows):
        facts = copy.deepcopy(self.fixture.fixture.sources[0])
        facts['winners_bracket'] = rows
        facts['losers_bracket'] = []
        self.fixture.publish(facts)
        response = self.fixture.client.get('/api/history/seasons/2026/playoffs')
        self.assertEqual(response.status_code, 200)
        return facts, response.json()['playoffs']['result']

    def test_duplicate_participants_fail_closed_before_identity_set_conversion(self):
        for first, second in [(1, 1), (1, '1'), ('1', 1)]:
            with self.subTest(first=first, second=second):
                row = {'m': 1, 'p': 1, 't1': first, 't2': second, 'w': 1, 'l': 2}
                facts, result = self.publish([row])
                self.assertIsNone(result['champion_roster_id'])
                self.assertIsNone(result['runner_up_roster_id'])
                self.assertEqual(result['placements'], {})
                self.assertIn('bracket_participant_identity_conflict', result['reason_codes'])
                self.assertEqual(self.fixture.fixture.cache.read(fixtures.DAY, 2026).facts['winners_bracket'], facts['winners_bracket'])
                brackets = self.fixture.fixture.store.optional_records(fixtures.DAY, 'playoff_bracket', season=2026)[1]
                self.assertEqual(brackets[0]['payload']['retained_participant_evidence'], {'t1': first, 't2': second})
                for url in ('/history/2026', '/api/history/seasons/2026', '/api/history/franchises/1', '/trades/history/' + fixtures.ROOT):
                    self.assertEqual(self.fixture.client.get(url).status_code, 200, url)
                self.assertTrue(self.fixture.fixture.store.optional_records(fixtures.DAY, 'season_standing', season=2026)[1])

    def test_known_contradictions_and_malformed_participants_withhold_outcomes(self):
        cases = [({'t1': 1, 't2': 2, 'w': 3, 'l': 2}, 'bracket_outcome_identity_conflict'),
                 ({'t1': 1, 't2': 2, 'w': 1, 'l': 3}, 'bracket_outcome_identity_conflict'),
                 ({'t1': 1, 't2': 2, 'w': 1, 'l': 1}, 'bracket_outcome_identity_conflict'),
                 ({'t1': {'roster': 1}, 't2': 2, 'w': 1, 'l': 2}, 'bracket_participant_identity_malformed_or_unsupported'),
                 ({'t1': 1, 't2': [2], 'w': 1, 'l': 2}, 'bracket_participant_identity_malformed_or_unsupported'),
                 ({'t1': 'bad', 't2': 2, 'w': 1, 'l': 2}, 'bracket_participant_identity_malformed_or_unsupported'),
                 ({'t1': True, 't2': 2, 'w': 1, 'l': 2}, 'bracket_participant_identity_malformed_or_unsupported'),
                 ({'t1': 999, 't2': 2, 'w': 1, 'l': 2}, 'bracket_participant_identity_malformed_or_unsupported')]
        for fields, reason in cases:
            with self.subTest(fields=fields):
                _, result = self.publish([{'m': 1, 'p': 1, **fields}])
                self.assertIsNone(result['champion_roster_id'])
                self.assertIsNone(result['runner_up_roster_id'])
                self.assertEqual(result['placements'], {})
                self.assertIn(reason, result['reason_codes'])
                self.assertEqual(self.fixture.client.get('/history/2026').status_code, 200)

    def test_absent_null_partial_and_valid_participants_remain_distinct(self):
        for fields in ({}, {'t1': None, 't2': None}, {'t1': 1, 't2': None}, {'t1': 1, 't2': 2}):
            with self.subTest(fields=fields):
                _, result = self.publish([{'m': 1, 'p': 1, 'w': 1, 'l': 2, **fields}])
                self.assertEqual(result['champion_roster_id'], 1)
                self.assertEqual(result['runner_up_roster_id'], 2)
                self.assertEqual(result['placements'], {'1': 1, '2': 2})
                self.assertNotIn('bracket_participant_identity_conflict', result['reason_codes'])
        _, pending = self.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': None, 'l': None}])
        self.assertIsNone(pending['champion_roster_id'])
        self.assertEqual(pending['placements'], {})
        self.assertIn('championship_unresolved', pending['reason_codes'])

    def test_resolved_dependencies_retain_duplicate_participant_conflict(self):
        rows = [{'m': 1, 'r': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2},
                {'m': 2, 'r': 1, 't1': 1, 't2': 3, 'w': 1, 'l': 3},
                {'m': 3, 'r': 2, 'p': 1, 't1': {'w': 1}, 't2': {'w': 2}, 'w': 1, 'l': 2}]
        _, result = self.publish(rows)
        _, reversed_result = self.publish(list(reversed(rows)))
        self.assertEqual(result, reversed_result)
        self.assertIsNone(result['champion_roster_id'])
        self.assertEqual(result['placements'], {})
        self.assertIn('bracket_participant_identity_conflict', result['reason_codes'])

    def test_conflicting_and_invalid_placement_cannot_certify_champion(self):
        final = {'m': 1, 'r': 2, 'p': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}
        for extra in ({'m': 2, 'p': 2, 't1': 3, 't2': 4, 'w': 3, 'l': 4},
                      {'m': 2, 'p': 3, 't1': 1, 't2': 4, 'w': 1, 'l': 4}):
            _, result = self.publish([final, extra])
            self.assertIsNone(result['champion_roster_id'])
            self.assertIsNone(result['runner_up_roster_id'])
            self.assertNotIn('1', result['placements'])
            self.assertNotIn('2', result['placements'])
        for placement in (True, 'bad', -1, {'rank': 1}, [1]):
            _, result = self.publish([{**final, 'p': placement}])
            self.assertIsNone(result['champion_roster_id'])
            self.assertEqual(result['placements'], {})
            self.assertIn('placement_identity_malformed_or_unsupported', result['reason_codes'])

    def test_retained_result_consumer_revalidates_duplicate_and_placement_context(self):
        original = {'championship_roster_ids': ['1', '1'], 'champion_roster_id': 1,
                    'runner_up_roster_id': 2, 'placements': {'1': 1, '2': 2}, 'reason_codes': []}
        retained = copy.deepcopy(original)
        admitted = admitted_playoff_result(retained)
        self.assertIsNone(admitted['champion_roster_id'])
        self.assertEqual(admitted['placements'], {})
        self.assertIn('bracket_participant_identity_conflict', admitted['reason_codes'])
        self.assertEqual(admitted, admitted_playoff_result(admitted))
        self.assertEqual(retained, original)
        for placements in ({'1': 2, '2': 1}, {'1': 1, '2': 2, '3': 1}):
            result = admitted_playoff_result({**original, 'championship_roster_ids': ['1', '2'], 'placements': placements})
            self.assertIsNone(result['champion_roster_id'])
            self.assertNotIn('1', result['placements'])
            self.assertNotIn('2', result['placements'])

    def test_valid_multiround_byes_and_multiweek_metadata_are_preserved(self):
        rows = [{'m': 1, 'r': 1, 't1': 3, 't2': 6, 'w': 3, 'l': 6},
                {'m': 2, 'r': 1, 't1': 4, 't2': 5, 'w': 5, 'l': 4},
                {'m': 3, 'r': 2, 't1': 1, 't2': {'w': 1}, 'w': 1, 'l': 3},
                {'m': 4, 'r': 2, 't1': 2, 't2': {'w': 2}, 'w': 5, 'l': 2},
                {'m': 5, 'r': 3, 'p': 1, 't1': {'w': 3}, 't2': {'w': 4}, 'w': 5, 'l': 1}]
        facts, result = self.publish(rows)
        self.assertEqual(result['champion_roster_id'], 5)
        self.assertEqual(result['placements'], {'1': 5, '2': 1})
        self.assertEqual(result['first_round_bye_roster_ids'], ['1', '2'])
        self.assertEqual(result['semifinal_roster_ids'], ['1', '2', '3', '5'])
        facts['league']['settings']['playoff_round_type'] = 2
        self.fixture.publish(facts)
        repeated = self.fixture.client.get('/api/history/seasons/2026/playoffs').json()['playoffs']['result']
        self.assertEqual(result, repeated)

    def test_existing_checkpoint_reads_qualify_conflict_without_rewriting_history(self):
        from src.core.history_context.recovery import HistoricalCheckpoints, FAMILIES
        self.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}])
        store = self.fixture.fixture.store
        rows = store.optional_records(fixtures.DAY, None, season=2026, limit=None)[1]
        rows = [copy.deepcopy(row) for row in rows if row['entity_type'] in FAMILIES]
        for row in rows:
            if row['entity_type'] == 'playoff_bracket':
                row['payload'].update(t1=1, t2=1)
            if row['entity_type'] == 'playoff_result':
                row['payload'].update(championship_roster_ids=['1', '1'])
        checkpoints = HistoricalCheckpoints(self.fixture.fixture.cache.root)
        checkpoints.preserve(league=fixtures.DAY, season=2026, source_league=fixtures.DAY,
                             source_checksum='retained-prior-admission-fixture', records=rows,
                             families={row['entity_type'] for row in rows})
        path = checkpoints.path(fixtures.DAY, 2026)
        before = path.read_bytes()
        self.fixture.fixture.cache.delete(fixtures.DAY, 2026)
        for _ in range(2):
            response = self.fixture.client.get('/api/history/seasons/2026/playoffs')
            self.assertEqual(response.status_code, 200)
            result = response.json()['playoffs']['result']
            self.assertIsNone(result['champion_roster_id'])
            self.assertEqual(result['placements'], {})
            self.assertIn('bracket_participant_identity_conflict', result['reason_codes'])
            self.assertEqual(self.fixture.client.get('/history/2026').status_code, 200)
            self.assertEqual(path.read_bytes(), before)

    def test_conflicted_trophy_is_absent_and_other_league_isolated(self):
        data = {**self.fixture.data, 'league': {**self.fixture.data['league'], 'season': '2027'}}
        facts, _ = self.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 1, 'w': 1, 'l': 2}])
        facts['league']['status'] = 'complete'
        self.fixture.publish(facts)
        cache = self.fixture.fixture.cache
        self.assertIsNone(defending_champion(data, cache))
        self.assertEqual(champion_badge(defending_champion(data, cache), 1), '')
        facts['winners_bracket'][0]['t2'] = 2
        self.fixture.publish(facts)
        self.assertEqual(defending_champion(data, cache), (2026, 1))
        other = {**data, 'league': {**data['league'], 'league_id': fixtures.ARK}}
        self.assertNotEqual(defending_champion(other, cache), (2026, 1))

    def test_numeric_production_order_keeps_scores_roles_and_intervals_unchanged(self):
        facts = copy.deepcopy(self.fixture.fixture.sources[0])
        facts['matchups'] = {str(week): [{'roster_id': 4, 'players': ['13346'],
            'starters': ['13346'] if week == 1 else [], 'players_points': {'13346': value}}]
            for week, value in [(1, 10), (10, 0), (2, 20), (11, None)]}
        self.fixture.publish(facts)
        result = self.fixture.graph().recipient_production('13346', fixtures.DAY + ':franchise:4')
        self.assertEqual([r['week'] for r in result['observed_weeks']], [1, 2, 10, 11])
        self.assertEqual(result['observed_roster_points'], 30)
        self.assertEqual(result['started_points'], 10)
        self.assertEqual(result['bench_points'], 20)
        self.assertEqual(result['missing_score_observations'], 1)
        response = self.fixture.client.get('/trades/history/' + fixtures.ROOT)
        self.assertEqual(response.status_code, 200)
        import re
        endpoint = re.search('data-production-endpoint="([^"]+)"', response.text).group(1)
        from html import unescape
        fragment = self.fixture.client.get(unescape(endpoint))
        self.assertEqual(fragment.status_code, 200)
        positions = [fragment.text.index('2026 Week ' + str(w) + ' ·') for w in (1, 2, 10, 11)]
        self.assertEqual(positions, sorted(positions))

    def test_fois_retained_profiles_are_not_regenerated(self):
        from tests.test_history_final_source import HistoryFinalSourceTests
        with patch('src.core.fois.service.FOISService._generate_sync', side_effect=AssertionError('No historical grade regeneration')):
            test = HistoryFinalSourceTests('test_fois_profile_links_only_supported_participant_trade_references')
            test.fixture = self.fixture
            test.test_fois_profile_links_only_supported_participant_trade_references()


if __name__ == '__main__':
    unittest.main()
