import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.attention_changes import pick_changes
from services.home_attention import attention_state
from src.ui.home_attention import attention_panel


class PickChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'metadata.db'
        self.now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        self.pick = {'league_id': 'A', 'year': 2027, 'round': 1, 'original_roster_id': 2,
                     'current_owner_id': 1, 'projected_range': 'MID',
                     'projected_range_confidence': 'MEDIUM', 'range_method': 'm'}
        self.data = {'league': {'league_id': 'A'}, 'teams': [{'roster_id': 1}], 'pick_ledger': [self.pick]}
        self.events = [{'observed_at': '2026-09-19T00:00:00Z', 'state': {
            'projected_range': 'EARLY', 'projected_range_confidence': 'MEDIUM', 'range_method': 'm', 'exact_slot': None}},
            {'observed_at': '2026-09-20T00:00:00Z', 'state': {
            'projected_range': 'MID', 'projected_range_confidence': 'MEDIUM', 'range_method': 'm', 'exact_slot': None}}]

    def save(self):
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS metadata(namespace TEXT,key TEXT,value TEXT)')
            con.execute('DELETE FROM metadata')
            con.execute('INSERT INTO metadata VALUES(?,?,?)', ('pick_range_history', '["A",2027,1,2]', json.dumps({'events': self.events})))

    def read(self):
        return pick_changes(self.data, 1, self.path, now=self.now)

    def test_real_pair_preserves_identity_and_read_only_replay(self):
        self.save()
        before = self.path.read_bytes()
        rows, coverage = self.read()
        self.assertEqual(coverage, 'available')
        self.assertTrue(rows[0]['qualifies'])
        self.assertEqual(rows[0]['original_franchise'], 2)
        for _ in range(100):
            self.assertEqual(self.read()[0], rows)
        self.assertEqual(self.path.read_bytes(), before)
        state = attention_state(self.data, 1, None, change_rows=rows + rows, change_coverage=coverage)
        self.assertEqual(len(state['items']), 1)
        self.assertEqual(state['deduplicated'], 1)
        self.assertIn('Comparable pick evidence change', attention_panel(state))
        self.assertNotIn('Unsupported required slots', attention_panel(state))

    def test_methodology_stale_and_bad_time_are_filtered(self):
        for field, value, expected in [('range_method', 'old', 'METHODOLOGY_BOUNDARY')]:
            self.events[0]['state'][field] = value
            self.save()
            self.assertEqual(self.read()[0][0]['reason'], expected)
        self.events[0]['state']['range_method'] = 'm'
        self.events[1]['observed_at'] = 'bad'
        self.save()
        self.assertEqual(self.read()[0][0]['reason'], 'INVALID_TIME_BOUNDARY')
        self.events[0]['observed_at'] = '2026-09-01T00:00:00Z'
        self.events[1]['observed_at'] = '2026-09-02T00:00:00Z'
        self.save()
        self.assertEqual(self.read()[0][0]['reason'], 'OUTSIDE_RECENT_WINDOW')

    def test_unknown_is_coverage_not_price(self):
        self.events[0]['state']['projected_range'] = 'UNKNOWN'
        self.save()
        row = self.read()[0][0]
        self.assertEqual(row['reason'], 'PICK_RANGE_COVERAGE_CHANGED')
        self.assertIn('not a value gain', row['why'])

    def test_confidence_only_not_range_change(self):
        self.events[0]['state'].update(projected_range='MID', projected_range_confidence='LOW')
        self.save()
        self.assertEqual(self.read()[0][0]['reason'], 'CONFIDENCE_ONLY_NOT_MATERIAL')

    def test_absence_no_initialization_or_cross_league(self):
        self.assertEqual(self.read(), ([], 'history_unavailable'))
        self.assertFalse(self.path.exists())
        self.save()
        self.data['league']['league_id'] = 'B'
        self.assertEqual(self.read()[0], [])

    def test_single_or_superseded_state_not_change(self):
        self.events = self.events[-1:]
        self.save()
        self.assertEqual(self.read()[0], [])
