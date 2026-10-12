"""Source publication, canonical admission and HTTP historical integrity controls."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from src.core.history_context.assets import reconcile_player_weeks
from src.core.historical_memory.graph import HistoricalAssetGraph
from tests import test_trade_timeline as fixtures

TRADE = "965057520920260608"


def publish_faab(fixture):
    facts = json.loads((Path(__file__).parent / "fixtures/trade_faab_source.json").read_text())
    fixture.cache.write(fixture.cache.normalize(fixtures.DAY, 2023, facts))
    fixture.data[fixtures.DAY]['players'].update(facts.get('player_identities') or {})
    fixture.store.update_current(fixtures.DAY, fixture.data[fixtures.DAY])
    return HistoricalAssetGraph(fixture.store, fixtures.DAY, fixture.data[fixtures.DAY], fixture.memory)


class HistoricalFaabConflictTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TradeTimelineTests()
        self.fixture.setUp()
        self.fixture.load()

    def tearDown(self):
        self.fixture.tearDown()

    def app(self):
        app = FastAPI()
        app.include_router(create_historical_assets_router(
            league_id=fixtures.DAY, require_data=lambda: self.fixture.data[fixtures.DAY],
            page=lambda title, body: HTMLResponse(body)))
        return app

    def scores(self, scores, rosters=None, week=1):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts["matchups"] = {str(week): [dict(roster_id=r, matchup_id=None,
            players=["score"], starters=["score"],
            players_points={} if s is None else {"score": s})
            for r, s in zip(rosters or [1] * len(scores), scores)]}
        self.fixture.cache.write(self.fixture.cache.normalize(fixtures.DAY, 2026, facts))
        return HistoricalAssetGraph(self.fixture.store, fixtures.DAY, self.fixture.data[fixtures.DAY], self.fixture.memory)

    def test_actual_three_party_trade_faab_route(self):
        graph = publish_faab(self.fixture)
        model = graph.trade_timeline(TRADE)
        movement = model["faab_movements"]
        self.assertEqual(len(movement), 1)
        self.assertEqual(movement[0]["amount"], 100)
        self.assertEqual(movement[0]["sent_by"]["name"], "Nasty Navel Lasers")
        self.assertEqual(movement[0]["received_by"]["name"], "zkobes")
        self.assertEqual(len(model["branches"]), 8)
        with patch("routes.historical_assets.historical_store", self.fixture.store), TestClient(self.app()) as client:
            page = client.get("/trades/history/" + TRADE)
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.text.count("100 FAAB"), 1)
            self.assertIn("Nasty Navel Lasers → zkobes", page.text)
            for name in ('Derek Carr', 'George Kittle', 'Tucker Kraft'):
                self.assertIn(name, page.text)
            self.assertIn("916477632584318976", page.text)

    def test_same_generation_conflicts_both_orders_repeat_and_http(self):
        results = []
        for scores in ([10, 20], [20, 10]):
            with self.subTest(scores=scores):
                graph = self.scores(scores)
                _, rows = self.fixture.store.records(fixtures.DAY, "player_week", player_id="score", limit=None)
                self.assertEqual(len(rows), 1)
                self.assertIsNone(rows[0]["payload"]["fantasy_points"])
                self.assertEqual(rows[0]["payload"]["scoring_conflict_reason"], "Conflicting numeric scores in the same source generation")
                self.assertEqual(reconcile_player_weeks(rows), rows)
                results.append(rows[0]['payload'])
                summary = graph.player_season_summaries("score")[0]
                self.assertIsNone(summary["starter_points"])
                self.assertIsNone(summary["last_scored_franchise_id"])
                with patch("routes.historical_assets.historical_store", self.fixture.store), TestClient(self.app()) as client:
                    result = client.get("/api/history/players/score")
                    self.assertEqual(result.status_code, 200)
                    self.assertIn("Conflicting numeric scores", result.text)
        self.assertEqual(results[0], results[1])

    def test_faab_two_party_multiple_directions_zero_absent_and_identical(self):
        publish_faab(self.fixture)
        facts = json.loads((Path(__file__).parent / 'fixtures/trade_faab_source.json').read_text())
        original = facts['transactions']['1'][0]
        for movements, count in [([], 0), (None, 0),
            ([dict(sender=3, receiver=6, amount=0)], 1),
            ([dict(sender=3, receiver=6, amount=100)] * 2, 1),
            ([dict(sender=3, receiver=6, amount=10), dict(sender=6, receiver=3, amount=20),
              dict(sender=1, receiver=6, amount=30)], 3),
            ([dict(sender=3, receiver=6, amount=None)], 0)]:
            with self.subTest(movements=movements):
                original['waiver_budget'] = movements
                self.fixture.cache.write(self.fixture.cache.normalize(fixtures.DAY, 2023, facts))
                model = HistoricalAssetGraph(self.fixture.store, fixtures.DAY,
                    self.fixture.data[fixtures.DAY], self.fixture.memory).trade_timeline(TRADE)
                self.assertEqual(len(model['faab_movements']), count)
                if movements and movements[0]['amount'] == 0:
                    self.assertEqual(model['faab_movements'][0]['amount'], 0)
        original['roster_ids'] = [3, 6]
        original['waiver_budget'] = [dict(sender=3, receiver=6, amount=40)]
        self.fixture.cache.write(self.fixture.cache.normalize(fixtures.DAY, 2023, facts))
        model = HistoricalAssetGraph(self.fixture.store, fixtures.DAY,
            self.fixture.data[fixtures.DAY], self.fixture.memory).trade_timeline(TRADE)
        self.assertEqual(len(model['participants']), 2)
        self.assertEqual(model['faab_movements'][0]['amount'], 40)

    def test_last_scored_owner_ignores_later_missing_score_and_snapshots_are_separate(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts['matchups'] = {'1': [dict(roster_id=1, players=['score'], starters=['score'], players_points={'score': 10})],
                             '2': [dict(roster_id=2, players=['score'], starters=['score'], players_points={})]}
        self.fixture.cache.write(self.fixture.cache.normalize(fixtures.DAY, 2026, facts))
        graph = HistoricalAssetGraph(self.fixture.store, fixtures.DAY, self.fixture.data[fixtures.DAY], self.fixture.memory)
        summary = graph.player_season_summaries('score')[0]
        self.assertEqual(summary['last_scored_franchise_id'], fixtures.DAY + ':franchise:1')
        self.assertIsNone(summary['starter_points'])
        history = graph.franchise_history('1')
        self.assertTrue(history['observed_season_roster_snapshots'])
        self.assertFalse(history['roster_snapshots'])
        self.assertIn('not weekly historical rosters', history['roster_coverage_note'])
        with patch('routes.historical_assets.historical_store', self.fixture.store), TestClient(self.app()) as client:
            data = client.get('/api/history/franchises/1').json()
            self.assertTrue(data['observed_season_roster_snapshots'])
            self.assertEqual(data['roster_snapshots'], [])

    def test_identical_zero_missing_cross_franchise_and_new_generation(self):
        for scores, rosters, expected, conflict in [
            ([10, 10], None, 10, False), ([0, 0], None, 0, False),
            ([None, None], None, None, False), ([10, 10], [1, 2], None, True),
            ([0, 20], None, None, True), ([None, 0], None, 0, False)]:
            with self.subTest(scores=scores, rosters=rosters):
                graph = self.scores(scores, rosters)
                rows = self.fixture.store.records(fixtures.DAY, "player_week", player_id="score", limit=None)[1]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["payload"]["fantasy_points"], expected)
                self.assertEqual(rows[0]["payload"]["scoring_conflict"], conflict)
                summary = graph.player_season_summaries("score")[0]
                self.assertEqual(summary["fantasy_points"], expected)
        old = self.scores([10, 20])
        self.assertIsNone(old.player_season_summaries("score")[0]["fantasy_points"])
        generation = self.fixture.store.dataset_version(fixtures.DAY)
        with patch('routes.historical_assets.historical_store', self.fixture.store), TestClient(self.app()) as client:
            self.assertIn('Conflicting numeric scores', client.get('/api/history/players/score/seasons').text)
        new = self.scores([25])
        self.assertNotEqual(self.fixture.store.dataset_version(fixtures.DAY), generation)
        self.assertIsNone(old.player_season_summaries("score")[0]["fantasy_points"])
        self.assertEqual(new.player_season_summaries("score")[0]["fantasy_points"], 25)
        with patch('routes.historical_assets.historical_store', self.fixture.store), TestClient(self.app()) as client:
            result = client.get('/api/history/players/score/seasons').json()
            self.assertEqual(result['records'][0]['fantasy_points'], 25)
            self.assertEqual(result['records'][0]['scoring_conflicts'], [])

    def test_repeat_routes_and_reads_leave_initialized_storage_unchanged(self):
        import hashlib
        graph = publish_faab(self.fixture)
        graph.trade_timeline(TRADE)
        graph.franchise_history('3')
        def files():
            return {str(p): (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in Path(self.fixture.temp.name).rglob('*') if p.is_file()}
        before = files()
        for _ in range(20):
            graph.trade_timeline(TRADE)
            graph.franchise_history('3')
        self.assertEqual(files(), before)
