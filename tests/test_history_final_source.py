"""Actual release asset, canonical admission and published-state read regressions."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests import test_historical_tracker_phase2 as fixtures


class HistoryFinalSourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TrackerPhase2Tests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def test_actual_application_asset_is_registered_without_static_mount(self):
        import dtos_app
        response = TestClient(dtos_app.app).get('/static/js/history-production.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, Path('static/js/history-production.js').read_text())
        self.assertIn('javascript', response.headers['content-type'])
        self.assertEqual(response.headers['cache-control'], 'no-cache')

    def test_real_outer_state_supplies_owner_observation(self):
        import dtos_app
        from src.core.historical_memory.read_model import historical_graph
        data = self.fixture.data
        data.pop('last_sync', None)
        with patch.object(dtos_app, 'current_league_context', return_value=None), patch.dict(dtos_app.STATE, {'data': data, 'last_sync': '2026-10-13T02:00:00Z'}):
            self.assertIs(dtos_app.require_data(), data)
            graph = historical_graph(self.fixture.fixture.store, fixtures.DAY, dtos_app.require_data())
            self.assertEqual(graph.current_asset_observation('DTOS-P-13346')['as_of'], '2026-10-13T02:00:00Z')
            api = self.fixture.client.get('/api/history/players/13346')
            self.assertEqual(api.status_code, 200)
            self.assertEqual(api.json()['current_owner_observation']['as_of'], '2026-10-13T02:00:00Z')
            page = self.fixture.client.get('/players/13346')
            self.assertEqual(page.status_code, 200)
            self.assertIn('2026-10-13T02:00:00Z', page.text)

    def test_secondary_runtime_and_exact_active_and_consumed_pick_timing(self):
        import dtos_app
        from src.core.league_runtime.manager import LeagueRuntime
        from src.core.league_runtime.context import CanonicalLeagueContext
        from src.core.historical_memory.read_model import historical_graph
        data = self.fixture.data
        data['pick_ledger'] = [{'league_id': fixtures.DAY, 'season': 2028, 'round': 3,
                              'original_roster_id': 7, 'current_owner_id': 6}]
        runtime = LeagueRuntime(fixtures.DAY)
        runtime.apply_data(data)
        runtime.state['last_sync'] = '2026-10-13T03:00:00Z'
        runtime.source_generations = {'rosters': 'supported-roster-generation', 'picks': 'supported-pick-generation'}
        context = CanonicalLeagueContext(runtime, self.fixture.fixture.store, None, None, None)
        with patch.object(dtos_app, 'current_league_context', return_value=context), patch.dict(dtos_app.STATE, {'last_sync': '2030-01-01T00:00:00Z'}):
            self.fixture.data = dtos_app.require_data()
            graph = historical_graph(self.fixture.fixture.store, fixtures.DAY, self.fixture.data)
            for player in ('DTOS-P-13346', 'DTOS-P-13287'):
                self.assertEqual(graph.current_asset_observation(player)['as_of'], '2026-10-13T03:00:00Z')
            active = graph.pick_dossier('PICK-2028-R3-ORIG7')
            self.assertEqual(active['current_owner_observation']['as_of'], '2026-10-13T03:00:00Z')
            self.assertTrue(active['current_owner'].endswith(':6'))
            self.assertTrue(active['original_franchise_id'].endswith(':7'))
            for pick in (fixtures.PICK, 'PICK-2026-R1-ORIG4'):
                consumed = graph.pick_dossier(pick)
                self.assertIsNone(consumed['current_owner'])
                self.assertTrue(consumed['exercised'])
                self.assertEqual(consumed['selected_player_observation']['as_of'], '2026-10-13T03:00:00Z')
                response = self.fixture.client.get('/picks/' + pick)
                self.assertEqual(response.status_code, 200)
                self.assertIn('DTOS Sleeper retrieval/sync observation', response.text)
                self.assertNotIn('2030-01-01', response.text)

    def test_nested_optional_outcomes_keep_actual_season_routes_available(self):
        facts = copy.deepcopy(self.fixture.fixture.sources[0])
        facts['winners_bracket'] = [{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': {'roster_id': 1}, 'l': [2]}]
        facts['losers_bracket'] = []
        self.fixture.publish(facts)
        for url in ('/history/2026', '/api/history/seasons/2026'):
            with self.subTest(url=url):
                response = self.fixture.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_bracket_outcome_matrix_and_independent_surrounding_content(self):
        from src.core.history_context.playoffs import playoff_facts
        for winner, loser in [(1, 2), ('1', '2'), (None, None), ({'w': 1}, 2), (1, [2]),
                              ({'nested': {'w': [1]}}, [2]), ('invalid', 2), ('1' * 5000, 2), (1, 1), (999, 2), (True, 2)]:
            with self.subTest(winner=winner, loser=loser):
                facts = copy.deepcopy(self.fixture.fixture.sources[0])
                facts['winners_bracket'] = [{'m': 1, 'p': 1, 't1': 1, 't2': 2, 'w': winner, 'l': loser}]
                facts['losers_bracket'] = []
                self.fixture.publish(facts)
                result = self.fixture.client.get('/api/history/seasons/2026/playoffs')
                self.assertEqual(result.status_code, 200)
                payload = result.json()['playoffs']['result']
                supported = winner in (1, '1') and not isinstance(winner, bool) and loser in (2, '2')
                self.assertEqual(payload.get('champion_roster_id'), 1 if supported else None)
                if not supported:
                    self.assertEqual(payload.get('placements'), {})
                for url in ('/history/2026', '/api/history/seasons/2026', '/api/history/franchises/1', '/trades/history/' + fixtures.ROOT):
                    self.assertEqual(self.fixture.client.get(url).status_code, 200, url)
                from src.core.history_context.playoffs import admitted_bracket_row
                roster_ids = {r['roster_id'] for r in facts['rosters']}
                self.assertEqual(payload, playoff_facts([admitted_bracket_row(r, roster_ids) for r in facts['winners_bracket']]))
        for bracket in (None, []):
            facts['winners_bracket'] = bracket
            self.fixture.publish(facts)
            self.assertEqual(self.fixture.client.get('/history/2026').status_code, 200)
            scope = self.fixture.fixture.store.source_coverage(fixtures.DAY)
            current = next(s for s in scope['seasons'] if s['season'] == 2026)
            self.assertEqual(current['families']['winners_bracket'], 'unavailable' if bracket is None else 'observed_empty')

    def test_resolved_match_participants_reject_conflicting_championship_outcome(self):
        from src.core.history_context.playoffs import playoff_facts, roster_identity
        self.assertIsNone(roster_identity(10 ** 5000))
        rows = [{'m': 1, 'r': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2},
                {'m': 2, 'r': 1, 't1': 3, 't2': 4, 'w': 3, 'l': 4},
                {'m': 3, 'r': 2, 'p': 1, 't1': {'w': 1}, 't2': {'w': 2}, 'w': 2, 'l': 3}]
        result = playoff_facts(rows)
        self.assertIsNone(result['champion_roster_id'])
        self.assertEqual(result['placements'], {})
        self.assertIn('bracket_outcome_identity_conflict', result['reason_codes'])
        self.assertEqual(result, playoff_facts(list(reversed(rows))))
        partial = playoff_facts([{'m': 1, 'p': 1, 't1': 1, 't2': None, 'w': 1, 'l': 2}])
        self.assertEqual(partial['champion_roster_id'], 1)
        self.assertNotIn('bracket_outcome_identity_conflict', partial['reason_codes'])

    def test_retrieval_only_refresh_updates_warm_timeline_without_rebuild_or_durable_write(self):
        from src.core.historical_memory.read_model import HistoricalReadModelCache
        from src.core.league_runtime.context import ownership_source_data
        cache = HistoricalReadModelCache()
        data = self.fixture.data
        state = {'data': data, 'last_sync': '2026-10-13T02:00:00Z'}
        graph = cache.get(self.fixture.fixture.store, fixtures.DAY, ownership_source_data(data, state))
        graph.trade_timeline(fixtures.ROOT)
        manifest = self.fixture.fixture.store.path.parent / 'historical_read_model_manifest.json'
        original = manifest.read_bytes()
        for timestamp in ('2026-10-13T03:00:00Z', None, 'invalid', '2026-10-13T04:00:00Z'):
            state['last_sync'] = timestamp
            warm = cache.get(self.fixture.fixture.store, fixtures.DAY, ownership_source_data(data, state))
            self.assertIs(warm, graph)
            observation = warm.current_asset_observation('DTOS-P-13346')
            self.assertEqual(observation['as_of'], timestamp if timestamp and timestamp != 'invalid' else None)
            branch = next(b for b in warm.trade_timeline(fixtures.ROOT)['branches'] if b.get('converted_asset'))
            self.assertEqual(branch['converted_asset']['as_of'], observation['as_of'])
            self.assertEqual(warm.player_dossier('13346')['current_owner_observation']['as_of'], observation['as_of'])
            self.assertEqual(manifest.read_bytes(), original)
        self.assertEqual(cache.metadata()['build_count'], 1)

    def test_owner_observation_scope_generation_and_holder_changes(self):
        from src.core.historical_memory.read_model import HistoricalReadModelCache
        from src.core.league_runtime.context import ownership_source_data
        cache = HistoricalReadModelCache()
        for league in (fixtures.DAY, fixtures.ARK, fixtures.DAY):
            data = self.fixture.fixture.data[league]
            stamp = '2026-10-13T02:00:00Z' if league == fixtures.DAY else '2026-10-13T09:00:00Z'
            state = {'data': data, 'last_sync': stamp}
            graph = cache.get(self.fixture.fixture.store, league, ownership_source_data(data, state, {'rosters': league + ':source', 'picks': league + ':picks'}))
            for team in data['teams']:
                for player in team.get('players') or []:
                    observation = graph.current_asset_observation('DTOS-P-' + str(player.get('id') or player.get('player_id')))
                    self.assertEqual(observation['as_of'], stamp)
                    self.assertEqual(observation['current_observed_owner'], league + ':franchise:' + str(team['roster_id']))
                    self.assertEqual(observation['ownership_source_generations']['rosters'], league + ':source')
            foreign = ownership_source_data(data, {'data': {}, 'last_sync': stamp})
            self.assertIsNone(foreign['ownership_source_observation']['observed_at'])
        changed = copy.deepcopy(self.fixture.data)
        player = next(p for t in changed['teams'] for p in t.get('players') or [] if str(p.get('id') or p.get('player_id')) == '13346')
        for team in changed['teams']:
            team['players'] = [p for p in team.get('players') or [] if p is not player]
        changed['teams'][1]['players'].append(player)
        graph = cache.get(self.fixture.fixture.store, fixtures.DAY, ownership_source_data(changed, {'data': changed, 'last_sync': '2026-10-13T10:00:00Z'}))
        self.assertTrue(graph.current_asset_observation('DTOS-P-13346')['current_observed_owner'].endswith(':' + str(changed['teams'][1]['roster_id'])))

    def test_week_zero_form_and_rows_preserve_zero_not_missing(self):
        for value, status in [('', 200), ('0', 200), ('1', 200), ('18', 200), ('-1', 422), ('invalid', 422)]:
            response = self.fixture.client.get('/transactions?scope=all_history&week=' + value)
            self.assertEqual(response.status_code, status)
            if value == '0':
                self.assertIn('name="week" value="0" min="0"', response.text)
        captured = copy.deepcopy(self.fixture.fixture.cache.read(fixtures.DAY, 2023).facts)
        captured['transactions'] = {'0': [row for rows in captured['transactions'].values() for row in rows]}
        self.fixture.publish(captured, 2023)
        facts = self.fixture.client.get('/api/history/transactions?week=0').json()['records']
        self.assertTrue(facts)
        response = self.fixture.client.get('/transactions?scope=all_history&week=0')
        self.assertIn('Week 0', response.text)
        self.assertNotIn('W?', response.text)

    def test_market_display_keeps_source_confidence_and_identifiers_honest(self):
        from src.ui.trade_timeline import _quote_card
        row = {'match_state': 'UNAVAILABLE', 'value': None, 'source_quote_confidence': 87,
               'temporal_confidence': 0, 'retained_attachment_at': '965057520920260608',
               'limitation': 'Dated estimates require event-stability evidence.'}
        text = _quote_card(row, 'Player')
        self.assertIn('Source observation confidence: 87', text)
        self.assertIn('Not eligible for comparison', text)
        self.assertIn('identifier, not a supported timestamp', text)
        self.assertNotIn('Dated estimates require', text)
        row.update(match_state='DATED_ESTIMATE', value=0, retained_attachment_at='2023-05-18T00:00:00Z')
        text = _quote_card(row, 'Player')
        self.assertIn('Dated estimates require', text)
        self.assertIn('attachment timestamp: 2023-05-18T00:00:00Z', text)

    def test_fois_profile_links_only_supported_participant_trade_references(self):
        from dataclasses import replace
        from tests.test_fois_presentation import FOISPresentationTests
        profile = FOISPresentationTests()
        profile.setUp()
        try:
            score = profile._persist_profiles(fixtures.DAY, 1)[0]
            score = replace(score, franchise_id=fixtures.DAY + ':franchise:4',
                            evidence_references=(fixtures.ROOT, 'missing-transaction', fixtures.ROOT))
            profile.repository.save(score, 'readable-activity-fixture')
            profile.data = self.fixture.data
            with patch('src.core.history_context.canonical_history_store', self.fixture.fixture.store):
                result = profile._client().get('/fois/gms/' + score.gm_id)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.text.count('href="/trades/history/' + fixtures.ROOT + '"'), 1)
            self.assertIn('NOT REVALIDATED', result.text)
            self.assertNotIn('/trades/history/missing-transaction', result.text)
            score = replace(score, franchise_id=fixtures.DAY + ':franchise:99')
            profile.repository.save(score, 'nonparticipant-fixture')
            with patch('src.core.history_context.canonical_history_store', self.fixture.fixture.store):
                result = profile._client().get('/fois/gms/' + score.gm_id)
            self.assertNotIn('href="/trades/history/' + fixtures.ROOT + '"', result.text)
        finally:
            profile.tearDown()


if __name__ == '__main__':
    unittest.main()
