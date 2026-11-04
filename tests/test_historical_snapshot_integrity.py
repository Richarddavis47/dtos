"""Published retained snapshot races and actual missing-scoring HTTP views."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from threading import Event
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.history import create_history_router
from tests import test_historical_player_evidence as evidence


class HistoricalSnapshotIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = evidence.HistoricalPlayerEvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.cache = self.fixture.store, self.fixture.cache

    def source(self, index=0, score=None):
        data, source = evidence.active_source(index)
        facts = {'league': deepcopy(data['league']), 'matchups': {'5': deepcopy(source['week5'])}}
        if score is not None:
            for side in facts['matchups']['5']:
                if '11563' in side['players_points']:
                    side['players_points']['11563'] = score
        return data, self.cache.normalize(data['league']['league_id'], 2026, facts)

    def test_repeated_actual_publication_replacement_never_mixes_facts_and_checksum(self):
        for index in (0, 1):
            _, a = self.source(index, 7.92)
            _, b = self.source(index, 123.45)
            read = self.cache.read
            for iteration in range(10):
                with self.subTest(league=a.league_id, iteration=iteration):
                    self.cache.write(a)
                    captures = []
                    def replace_after_capture(league, season):
                        snapshot = read(league, season)
                        captures.append(snapshot.checksum)
                        # Exact Scout interleaving: A is already decoded; publish
                        # B before the retained projector can obtain provenance.
                        if len(captures) == 1:
                            self.cache.write(b)
                        return snapshot
                    with patch.object(self.cache, 'read', side_effect=replace_after_capture):
                        rows = self.store._season_records(a.league_id, 2026, {'player_week'}, '11563')
                    row = next(r for r in rows if r['entity_type'] == 'player_week')
                    pair = (row['payload']['fantasy_points'], row['payload']['source_generation'])
                    self.assertIn(pair, ((7.92, a.checksum), (123.45, b.checksum)))
                    self.assertNotEqual(pair, (7.92, b.checksum))
                    self.assertEqual(row['league_id'], a.league_id)
                    self.assertEqual(row['week'], 5)
                    self.assertEqual(row['player_id'], '11563')
                    self.assertEqual(row['payload']['source_league_id'], a.league_id)
                    self.assertEqual(row['franchise_id'], f"{a.league_id}:franchise:{row['payload']['roster_id']}")
                    self.assertEqual(read(a.league_id, 2026).checksum, b.checksum)

    def test_concurrent_publisher_can_finish_while_captured_reader_is_paused(self):
        _, a = self.source(score=7.92)
        _, b = self.source(score=123.45)
        self.cache.write(a)
        captured, replaced = Event(), Event()
        original = self.cache.read
        def paused_read(league, season):
            snapshot = original(league, season)
            captured.set()
            self.assertTrue(replaced.wait(5), 'Publisher blocked by retained reader')
            return snapshot
        def publish():
            self.assertTrue(captured.wait(5))
            try:
                self.cache.write(b)
            finally:
                replaced.set()
        with ThreadPoolExecutor(max_workers=2) as workers, patch.object(self.cache, 'read', side_effect=paused_read):
            writer = workers.submit(publish)
            reader = workers.submit(self.store._season_records, a.league_id, 2026, {'player_week'}, '11563')
            rows = reader.result(timeout=10)
            writer.result(timeout=10)
        row = next(r for r in rows if r['entity_type'] == 'player_week')
        self.assertEqual((row['payload']['fantasy_points'], row['payload']['source_generation']), (7.92, a.checksum))

    def test_normal_reads_keep_exact_published_generation_without_rechecking_mutable_index(self):
        for index in (0, 1):
            _, snapshot = self.source(index)
            self.cache.write(snapshot)
            path = self.cache.path(snapshot.league_id, 2026)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(self.cache, 'checksum_index', side_effect=AssertionError('second generation read')):
                for _ in range(3):
                    rows = self.store._season_records(snapshot.league_id, 2026, {'player_week'})
                    players = [r for r in rows if r['entity_type'] == 'player_week']
                    self.assertEqual(len(players), (285, 273)[index])
                    self.assertTrue(all(r['payload']['source_generation'] == snapshot.checksum for r in players))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def http(self, data):
        app = FastAPI()
        app.include_router(create_history_router(league_id=data['league']['league_id'],
            require_data=lambda: data, page=lambda title, body: HTMLResponse(body)))
        return TestClient(app)

    def test_unavailable_scoring_route_never_interpolates_null_metrics(self):
        for case in ('missing', 'incompatible'):
            with self.subTest(case=case):
                data, snapshot = self.source()
                self.cache.write(snapshot)
                if case == 'missing':
                    data['scoring_settings'] = data['league']['scoring_settings'] = {}
                else:
                    data['scoring_settings'] = {'rec': 999}
                self.store.update_current(evidence.DAY, data)
                with self.http(data) as client:
                    response = client.get('/history/player/11563')
                self.assertEqual(response.status_code, 200)
                self.assertIn('Bo Nix', response.text)
                self.assertIn('2026', response.text)
                self.assertIn('Historical scoring unavailable for this season', response.text)
                self.assertNotIn('None', response.text)
                self.assertNotIn('7.92 points', response.text)
                self.assertIn('Back to connected Player Dossier', response.text)

    def test_zero_and_supported_metrics_remain_numeric_without_null_consistency(self):
        for score in (0, 7.92):
            with self.subTest(score=score):
                data, snapshot = self.source(score=score)
                data['season_matchups'] = {}
                self.store.update_current(evidence.DAY, data)
                self.cache.write(snapshot)
                with self.http(data) as client:
                    response = client.get('/history/player/11563')
                self.assertEqual(response.status_code, 200)
                self.assertIn(f'{float(score)} points', response.text.replace('</b>', ''))
                self.assertNotIn('None', response.text)
                self.assertNotIn('Historical scoring unavailable for this season', response.text)
                if score == 0:
                    self.assertIn('Consistency Unavailable', response.text)


if __name__ == '__main__':
    unittest.main()
