import json
from pathlib import Path
import tempfile
import unittest

from src.core.history_context.metadata import MinimalMetadataStore
from src.core.intelligence.pick_context import record_range_history, prepare_pick_context


class RangeHistoryTests(unittest.TestCase):
    def test_history_cap_is_explicit_and_replay_after_cap_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory)/'m.sqlite3')
            for i in range(132):
                record_range_history(store, [self.pick('EARLY' if i % 2 else 'LATE')], league_id='A', observed_at=str(i))
            with store.connection() as connection:
                value = json.loads(connection.execute("SELECT value FROM metadata WHERE namespace='pick_range_history'").fetchone()[0])
            self.assertEqual(len(value['events']), 128)
            self.assertEqual(value['discarded_transitions'], 4)
            self.assertEqual(record_range_history(store, [self.pick('EARLY')], league_id='A', observed_at='replay'), 0)

    def pick(self, band='UNKNOWN', method='v1'):
        return dict(year=2027, round=1, original_roster_id=2, current_owner_id=1,
                    projected_range=band, projected_range_confidence='LOW', range_method=method)

    def test_100_unchanged_saves_zero_growth(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'metadata.sqlite3'
            store = MinimalMetadataStore(path)
            self.assertEqual(record_range_history(store, [self.pick()], league_id='A', observed_at='first'), 1)
            before = {p.name: p.stat().st_size for p in path.parent.iterdir()}
            for i in range(100):
                self.assertEqual(record_range_history(store, [self.pick()], league_id='A', observed_at=str(i)), 0)
            self.assertEqual(before, {p.name: p.stat().st_size for p in path.parent.iterdir()})
            with store.connection() as connection:
                rows = connection.execute("SELECT value FROM metadata WHERE namespace='pick_range_history'").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(json.loads(rows[0][0])['events']), 1)

    def test_return_transition_method_boundary_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory)/'m.sqlite3')
            for pick in (self.pick(), self.pick('EARLY'), self.pick(), self.pick(method='v2')):
                record_range_history(store, [pick], league_id='A', observed_at='t')
            record_range_history(store, [self.pick()], league_id='B', observed_at='t')
            with store.connection() as connection:
                rows = connection.execute("SELECT value FROM metadata WHERE namespace='pick_range_history' ORDER BY key").fetchall()
            history = json.loads(rows[0][0])['events']
            self.assertEqual(len(history), 4)
            self.assertEqual(history[-1]['reasons'], ['METHODOLOGY_CHANGED'])
            self.assertEqual(len(json.loads(rows[1][0])['events']), 1)

    def test_preparation_restores_original_ownership_without_market_forecast(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory)/'m.sqlite3')
            data = {'league': {'league_id': 'A'}, 'pick_ledger': [self.pick('EARLY')],
                    'teams': [{'roster_id': 1}, {'roster_id': 2}]}
            result = prepare_pick_context(data, store, observed_at='t')
            self.assertEqual(result['semantic_history_writes'], 1)
            self.assertEqual(data['pick_ledger'][0]['projected_range'], 'UNKNOWN')
            self.assertEqual(len(data['teams'][0]['picks_owned']), 1)
            self.assertEqual(len(data['teams'][1]['picks_traded_away']), 1)
            self.assertEqual(prepare_pick_context(data, store, observed_at='later')['semantic_history_writes'], 0)
