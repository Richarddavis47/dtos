"""Narrow status, contextual navigation and source/display boundary regressions."""
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from services.team_headquarters import build_team_headquarters
from services.player_projection_view import player_projection_view
from src.core.projection_intelligence.service import ProjectionService
from tests.test_trade_intelligence import fixture_data


class MyTeamFinalTests(TestCase):
    def test_status_survives_core_group_copies_and_other_positions(self):
        data = fixture_data()
        team = data['teams'][0]
        expected = {'QB': 'Questionable', 'RB': 'Active', 'WR': 'IR', 'TE': None}
        for player in team['players']:
            source = data['players'][player['id']]
            source.update(status=expected[player['position']], injury_status=None)
            if player['position'] == 'QB':
                source.update(status='Active', injury_status='Questionable')
                player['status'] = 'Active'
        team['players'].append({'id': 'k', 'name': 'Fixture Kicker', 'position': 'K'})
        data['players']['k'] = {'id': 'k', 'name': 'Fixture Kicker', 'position': 'K', 'injury_status': 'Out'}
        view = build_team_headquarters(data, 1)
        for pos, status in expected.items():
            for player in view['roster_groups'][pos]:
                self.assertEqual(player.get('availability_status'), status)
        self.assertEqual(view['other_players'][0]['availability_status'], 'Out')
        self.assertTrue(any('Questionable' in s for s in view['overview']['statuses']))

    def test_te_display_without_bonus_is_qualified_not_false_exact_replay(self):
        for position, premium, stats, expected in (
            ('TE', .5, {'rec': 5}, 7.5), ('TE', 1, {'rec': 5}, 10),
            ('TE', .5, {'rec': 5, 'bonus_rec_te': 5}, 7.5),
            ('TE', 0, {'rec': 5}, 5), ('WR', .5, {'rec': 5}, 5),
            ('TE', .5, {'rec': 0}, 0), ('TE', .5, {}, None),
        ):
            with self.subTest(position=position, premium=premium, stats=stats), tempfile.TemporaryDirectory() as folder, patch('services.global_evidence.retained_global_evidence', return_value=None):
                data = {'league': {'league_id': 'a', 'season': '2026', 'scoring_settings': {'rec': 1, 'bonus_rec_te': premium}}, 'week': 1, 'players': {'t': {'id': 't', 'position': position}}}
                service = ProjectionService(Path(folder) / 'p.sqlite3', league_id='a')
                feed = [{'player_id': 't', 'season': 2026, 'week': 1, 'player': {'position': position}, 'stats': stats}]
                snapshot = service.publish_horizon({1: feed}, data=data, league_id='a', season=2026, current_week=1)
                row = snapshot['players']['t']
                self.assertEqual(row['canonical_projection'], expected)
                view = player_projection_view(data, 't', service)
                self.assertEqual(view['value'], expected)
                if position == 'TE' and premium and 'bonus_rec_te' not in stats and stats:
                    self.assertIsNone(row['sleeper_web_display_projection'])
                    self.assertIn('unverified', view['display_reason'])
                elif expected is not None:
                    self.assertEqual(float(row['sleeper_web_display_projection']), expected)
                if expected is None:
                    self.assertEqual(view['availability'], 'unavailable')
                self.assertEqual(snapshot['projection_snapshot_id'], service.publish_horizon({1: feed}, data=data, league_id='a', season=2026, current_week=1)['projection_snapshot_id'])

    def test_actual_routes_te_premium_and_contextual_returns(self):
        import asyncio
        from contextlib import ExitStack
        from types import SimpleNamespace
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        from fastapi.testclient import TestClient
        from routes.teams import create_teams_router
        from routes.transactions import create_transactions_router
        from routes.matchups import create_matchups_router
        from services.matchup_season import prepare_season_matchups
        from src.core.intelligence.orchestrator import IntelligenceOrchestrator
        from src.core.intelligence.cache import IntelligenceCache
        from src.core.intelligence.team_strength import prepare_for_data

        class Links(HTMLParser):
            def __init__(self, body):
                super().__init__()
                self.urls = []
                self.feed(body)
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.urls.append(dict(attrs).get('href', ''))

        async def fresh():
            pass
        for league_id, premium in (('day-fixture', .5), ('arkham-fixture', 1)):
            with self.subTest(league=league_id), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                data = fixture_data()
                data.update(week=1, roster_positions=['TE', 'BN'])
                data['league'].update(league_id=league_id, season='2026', roster_positions=['TE', 'BN'], settings={'leg': 1, 'playoff_week_start': 14})
                data['league']['scoring_settings'] = {'rec': 1, 'bonus_rec_te': premium}
                data['scoring_settings'] = data['league']['scoring_settings']
                payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week, 'player': {'position': p['position']}, 'stats': {'rec': 5}} for pid,p in data['players'].items()] for week in (1, 2)}
                service = ProjectionService(Path(folder)/'projection.sqlite3', league_id=league_id)
                service.publish_horizon(payloads, data=data, league_id=league_id, season=2026, current_week=1)
                stack.enter_context(patch('services.global_evidence.retained_global_evidence', return_value=None))
                prepare_for_data(service, data, bye_evidence={'season': 2026, 'reference': 'fixture-schedule', 'player_weeks': {'1-TE-8': 2}})
                rows = [{'roster_id': t['roster_id'], 'matchup_id': 1, 'starters': [f"{t['roster_id']}-TE-8"], 'players': [p['id'] for p in t['players']], 'points': 11, 'starters_points': [11]} for t in data['teams'][:2]]
                async def fetch(_):
                    return rows
                data['season_matchups'] = asyncio.run(prepare_season_matchups(data['league'], 1, rows, fetch, observed_at='fixture'))
                engine = IntelligenceOrchestrator(cache=IntelligenceCache())
                history = SimpleNamespace(player_dossier=lambda pid: {'season_summaries': [], 'ownership_timeline': [], 'league_origin': {}, 'identity': {'canonical_id': pid, 'resolution_status': 'resolved'}}, franchise_history=lambda rid: {'standings': [], 'transactions': [], 'identities': [], 'roster_snapshots': [], 'franchise_id': f'{league_id}:{rid}'})
                for name in ('routes.transactions', 'routes.teams', 'routes.matchups'):
                    stack.enter_context(patch(name + '.current_league_context', return_value=SimpleNamespace(league_id=league_id, projection=service)))
                stack.enter_context(patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=service.snapshot))
                stack.enter_context(patch('src.core.projection_intelligence.projection_service.week_snapshot', side_effect=service.week_snapshot))
                for name in ('services.team_headquarters', 'services.asset_intelligence'):
                    stack.enter_context(patch(name+'.intelligence_orchestrator', engine))
                for name in ('routes.transactions', 'routes.teams'):
                    stack.enter_context(patch(name+'.historical_graph', return_value=history))
                app = FastAPI()
                common = dict(ensure_fresh=fresh, require_data=lambda:data, page=lambda title,body:HTMLResponse(body))
                app.include_router(create_teams_router(**common, state={}))
                app.include_router(create_transactions_router(**common, refresh_transactions=fresh, state={}))
                app.include_router(create_matchups_router(**common))
                client = stack.enter_context(TestClient(app))
                team = client.get('/teams/1')
                self.assertEqual(team.status_code, 200)
                player = client.get('/players/1-TE-8?from_team=1&from_section=my-team-advanced&week=1')
                self.assertEqual(player.status_code, 200)
                expected = 5 * (1 + premium)
                self.assertIn(str(expected), player.text)
                self.assertIn('exact Sleeper display replay is unverified', player.text)
                self.assertIn('exact Sleeper display replay is unverified', team.text)
                matchup = client.get('/matchups/1?week=1')
                self.assertEqual(matchup.status_code, 200)
                self.assertIn(f'{expected:.2f}', matchup.text)
                links = [url for url in Links(team.text).urls if url.startswith('/players/')]
                self.assertTrue(any('from_section=my-team-advanced' in url for url in links))
                for url in links:
                    q = parse_qs(urlsplit(url).query)
                    self.assertEqual(q.get('from_team'), ['1'])
                self.assertIn('/teams/1#my-team-advanced', player.text)
                fragment = client.get('/players/1-TE-8/projections?week=2&from_team=1&from_section=my-team-advanced')
                self.assertEqual(fragment.status_code, 200)
                self.assertIn('name="from_section" value="my-team-advanced"', fragment.text)
                self.assertIn('from_team=1', fragment.text)
                unknown = client.get('/players/1-TE-8?week=1&from_team=9999&from_section=evil')
                self.assertNotIn('/teams/9999', unknown.text)
                changed = [{**row, 'stats': {'rec': 6}} for row in payloads[1]]
                before = service.snapshot()['projection_snapshot_id']
                service.publish_horizon({1:changed}, data=data, league_id=league_id, season=2026, current_week=1)
                self.assertNotEqual(before, service.snapshot()['projection_snapshot_id'])
                self.assertEqual(player_projection_view(data, '1-TE-8', service)['value'], 6*(1+premium))


if __name__ == '__main__':
    import unittest
    unittest.main()
