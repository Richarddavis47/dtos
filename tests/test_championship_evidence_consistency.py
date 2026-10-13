"""Canonical publication, season HTTP and shared trophy consumer agreement."""
from __future__ import annotations

import copy
import hashlib
import json
import statistics
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_historical_tracker_phase2 as fixtures
from src.ui.badges import defending_champion, champion_badge
from services.history import season_archive_section


class ChampionshipEvidenceConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TrackerPhase2Tests()
        self.fixture.setUp()
        self.fixture.data['league'] = {**self.fixture.data['league'], 'season': '2027',
                                      'previous_league_id': fixtures.DAY}
        self.fixture.fixture.store.update_current(fixtures.DAY, self.fixture.data)
        self.fixture.stack.enter_context(patch('services.history.sleeper_season_cache', self.fixture.fixture.cache))

    def tearDown(self):
        self.fixture.tearDown()

    def publish(self, rows, *, status='complete', source=None):
        facts = copy.deepcopy(self.fixture.fixture.sources[0])
        facts['league'].update(status=status, league_id=source or fixtures.DAY)
        facts['winners_bracket'] = rows
        self.fixture.publish(facts)
        return facts

    def result(self):
        response = self.fixture.client.get('/api/history/seasons/2026/playoffs')
        self.assertEqual(response.status_code, 200)
        return response.json()['playoffs']['result']

    def test_exact_scout_roster_999_reproduction(self):
        facts = self.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 999, 'w': 1, 'l': 999}])
        result = self.result()
        self.assertIsNone(result['champion_roster_id'])
        self.assertIsNone(result['runner_up_roster_id'])
        self.assertIn('bracket_participant_identity_malformed_or_unsupported', result['reason_codes'])
        self.assertIsNone(defending_champion(self.fixture.data))
        for url in ('/history/2026', '/api/history/seasons/2026', '/api/history/franchises/1'):
            self.assertEqual(self.fixture.client.get(url).status_code, 200)
        self.assertEqual(self.fixture.fixture.cache.read(fixtures.DAY, 2026).facts['winners_bracket'], facts['winners_bracket'])

    def test_valid_and_conflicting_admitted_history_and_badges_agree(self):
        for fields, champion in [({'t1': 1, 't2': 2, 'w': 1, 'l': 2}, 1),
                                 ({'t1': 1, 't2': 1, 'w': 1, 'l': 2}, None),
                                 ({'t1': 1, 't2': 2, 'w': 3, 'l': 2}, None),
                                 ({'t1': 1, 't2': 2, 'w': 1, 'l': 3}, None),
                                 ({'t1': 1, 't2': 2, 'w': 1, 'l': 1}, None),
                                 ({'t1': {'roster': 1}, 't2': 2, 'w': 1, 'l': 2}, None),
                                 ({'t1': 1, 't2': 2, 'w': None, 'l': None}, None)]:
            with self.subTest(fields=fields):
                self.publish([{'m': 1, 'p': 1, **fields}])
                self.assertEqual(self.result()['champion_roster_id'], champion)
                badge = defending_champion(self.fixture.data)
                self.assertEqual(badge, (2026, champion) if champion else None)
                self.assertEqual(bool(champion_badge(badge, 1)), champion == 1)

    def test_missing_bracket_historical_rosters_and_unfinished_season_withhold_trophy(self):
        self.publish([])
        self.assertIsNone(defending_champion(self.fixture.data))
        final = [{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}]
        self.publish(final, status='in_season')
        self.assertIsNone(defending_champion(self.fixture.data))
        facts = self.publish(final)
        facts['rosters'] = []
        self.fixture.publish(facts)
        self.assertIsNone(defending_champion(self.fixture.data))
        self.assertIsNone(self.result()['champion_roster_id'])

    def test_foreign_historical_source_cannot_use_matching_current_roster(self):
        self.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}], source='unrelated-league')
        self.assertIsNone(defending_champion(self.fixture.data))
        self.fixture.data['league']['previous_league_id'] = 'unrelated-league'
        self.assertEqual(defending_champion(self.fixture.data), (2026, 1))
        del self.fixture.data['league']['previous_league_id']
        self.assertIsNone(defending_champion(self.fixture.data))

    def test_multi_round_multiweek_byes_and_season_observed_managers(self):
        rows = [{'m': 1, 'r': 1, 't1': 3, 't2': 6, 'w': 3, 'l': 6},
                {'m': 2, 'r': 1, 't1': 4, 't2': 5, 'w': 5, 'l': 4},
                {'m': 3, 'r': 2, 't1': 1, 't2': {'w': 1}, 'w': 1, 'l': 3},
                {'m': 4, 'r': 2, 't1': 2, 't2': {'w': 2}, 'w': 5, 'l': 2},
                {'m': 5, 'r': 3, 'p': 1, 't1': {'w': 3}, 't2': {'w': 4}, 'w': 5, 'l': 1}]
        facts = self.publish(rows)
        expected = self.result()
        self.assertEqual(expected['first_round_bye_roster_ids'], ['1', '2'])
        self.assertEqual(defending_champion(self.fixture.data), (2026, 5))
        facts['league']['settings']['playoff_round_type'] = 2
        self.fixture.data['teams'][4]['owner'] = 'Different current manager'
        self.fixture.publish(facts)
        self.assertEqual(self.result(), expected)
        self.assertEqual(defending_champion(self.fixture.data), (2026, 5))

    def test_a_b_a_and_warm_read_source_correction_no_durable_growth(self):
        rows = [{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}]
        self.publish(rows)
        data = self.fixture.data
        other = copy.deepcopy(data)
        other['league'].update(league_id=fixtures.ARK, previous_league_id=None)
        for sample, expected in ((data, (2026, 1)), (other, None), (data, (2026, 1))):
            self.assertEqual(defending_champion(sample), expected)
        self.publish([{'m': 1, 'p': 1, 't1': 1, 't2': 999, 'w': 1, 'l': 999}])
        self.assertIsNone(defending_champion(data))
        root = Path(self.fixture.fixture.temp.name)
        def signature():
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob('*') if p.is_file()}
        self.result()
        before = signature()
        with patch('services.history._build_season_archive_section', side_effect=AssertionError('Unchanged reads must reuse the bounded section')):
            for _ in range(20):
                self.assertIsNone(defending_champion(data))
                self.assertIsNone(season_archive_section(fixtures.DAY, 2026, 'playoffs')['result']['champion_roster_id'])
        self.assertEqual(signature(), before)

    def test_captured_day_2025_champion_and_arkham_absence(self):
        source = json.loads((Path(__file__).parent / 'fixtures/championship_prior_source.json').read_text())
        data = self.fixture.data
        data['league'] = source['day']
        self.fixture.fixture.cache.write(self.fixture.fixture.cache.normalize(fixtures.DAY, 2025,
            {key: source[key] for key in ('league', 'rosters', 'users', 'winners_bracket')}))
        self.fixture.fixture.store.update_current(fixtures.DAY, data)
        response = self.fixture.client.get('/api/history/seasons/2025/playoffs')
        self.assertEqual(response.status_code, 200)
        result = response.json()['playoffs']['result']
        self.assertEqual((result['champion_roster_id'], result['runner_up_roster_id']), (1, 8))
        self.assertEqual(defending_champion(data), (2025, 1))
        durations = []
        for _ in range(50):
            start = time.perf_counter()
            self.assertEqual(defending_champion(data), (2025, 1))
            durations.append((time.perf_counter() - start) * 1000)
        target = Path('.validation/championship-consistency')
        target.mkdir(parents=True, exist_ok=True)
        (target / 'championship-read-performance.json').write_text(json.dumps({
            'evidence': 'local source-capture replay, warmed canonical/badge reads; excludes network and browser',
            'samples': len(durations), 'median_ms': statistics.median(durations), 'maximum_ms': max(durations)}, indent=2))
        other = {**data, 'league': source['arkham']}
        self.assertIsNone(defending_champion(other))
