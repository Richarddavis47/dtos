"""Phone product evidence contracts, actual canonical publication and routes."""
import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from services.matchup_season import prepare_season_matchups, season_week_view
from services.player_projection_view import player_projection_view
from src.ui.matchup_season import render_season_week
from src.ui.standings import render_standings, playoff_boundary, completed_streak
from routes.matchups import create_matchups_router
from tests import test_capital_strategy_reconciliation as capital_fixture


def phone_fixture(owner):
    f = capital_fixture.CapitalStrategyTests()
    f.setUp()
    owner.addCleanup(f.doCleanups)
    data = f.data
    data['roster_positions'] = data['league']['roster_positions']
    data['league']['settings'].update(playoff_teams=4, divisions=0)
    for team in data['teams']:
        for index, p in enumerate(team['players']):
            p['roster_slot'] = ['Starter', 'IR', 'Taxi'][index]
        team.update(wins=1, losses=0, ties=0, points_for=123.45, points_against=110.67)
    async def fetch(path):
        return rows
    rows = [{'roster_id': t['roster_id'], 'matchup_id': 2,
             'starters': [t['players'][0]['id']], 'starters_points': [10.25], 'points': 10.25,
             'players': [p['id'] for p in t['players']], 'players_points': {p['id']: 100 if i else 10.25 for i,p in enumerate(t['players'])}}
            for t in data['teams']]
    data['season_matchups'] = asyncio.run(prepare_season_matchups(data['league'], 2, rows, fetch, observed_at='fixture-only'))
    return f


class MatchupsPhoneTests(unittest.TestCase):
    def setUp(self):
        self.f = phone_fixture(self)
        self.data, self.service = self.f.data, self.f.reader

    def test_submitted_vs_optimal_and_all_roster_sections_exclude_bench(self):
        side = season_week_view(self.data, 2, self.service)['groups']['2'][0]
        self.assertEqual(side['actual'], 10.25)
        self.assertEqual(side['projection'], 10)
        self.assertEqual([p['player_id'] for p in side['reserve']], ['b'])
        self.assertEqual([p['player_id'] for p in side['taxi']], ['e'])
        self.assertEqual(side['known_subtotal'], 10)
        self.assertIn('not the submitted lineup', render_season_week(season_week_view(self.data, 2, self.service), matchup_id='2'))
        self.assertIn('data-roster-section="reserve"', render_season_week(season_week_view(self.data, 2, self.service), matchup_id='2'))

    def test_unknown_identity_does_not_link_and_history_does_not_borrow_ir(self):
        del self.data['players']['a']
        body = render_season_week(season_week_view(self.data, 2, self.service), matchup_id='2')
        self.assertNotIn('/players/a?', body)
        self.assertIn('Dossier unavailable', body)
        historical = season_week_view(self.data, 1, self.service)['groups']['2'][0]
        self.assertEqual(historical['reserve'], [])
        self.assertEqual(historical['taxi'], [])
        self.assertIsNone(historical['projection'])

    def test_missing_scores_and_partial_projection_never_zero_or_leader(self):
        rows = self.data['season_matchups']['weeks']['2']['rows']
        rows[0]['points'] = None
        rows[0]['starters'].append('absent')
        self.data['roster_positions'] = ['QB', 'SUPER_FLEX']
        view = season_week_view(self.data, 2, self.service)
        self.assertIsNone(view['groups']['2'][0]['projection'])
        self.assertIsNone(view['groups']['2'][0]['actual'])
        self.assertIn('Score unavailable', render_season_week(view))
        self.assertNotIn('win probability: 50', render_season_week(view))

    def test_exact_publication_matches_dossier_and_trade_under_two_scorings(self):
        from services.trade_intelligence import evaluate_trade_request
        from src.core.projection_intelligence.service import ProjectionService
        from pathlib import Path
        original = self.service.snapshot()
        for scale, league_id in ((1, 'league-1'), (.5, 'league-2')):
            data = copy.deepcopy(self.data)
            data['league']['league_id'] = league_id
            data['league']['scoring_settings'] = {'pass_yd': scale}
            data['season_matchups']['league_id'] = league_id
            # Calendar references include league/rules; prepare the source again.
            rows = data['season_matchups']['weeks']['2']['rows']
            async def fetch(path):
                return rows
            data['season_matchups'] = asyncio.run(prepare_season_matchups(data['league'], 2, rows, fetch, observed_at='fixture'))
            service = self.service if scale == 1 else ProjectionService(Path(self.f.tmp.name) / 'second.sqlite3')
            if scale != 1:
                service.publish_horizon(self.f.payloads, data=data, league_id=league_id, season=2026, current_week=2)
            view = season_week_view(data, 2, service)
            value = view['groups']['2'][0]['lineup'][0]['projection']
            self.assertEqual(value, 10 * scale)
            self.assertEqual(value, player_projection_view(data, 'a', service, 2)['value'])
            self.assertEqual(value, service.snapshot()['players']['a']['sleeper_projection'])
            report = evaluate_trade_request(data, {'active_roster_id': 1, 'partner_roster_id': 2,
                'assets_sent': ['a'], 'assets_received': ['c'], 'strategy': 'WIN NOW', 'workflow': 'create'}, projection_reader=service)
            self.assertEqual(report['evaluation']['provenance']['inputs']['projection_generation'], service.snapshot()['projection_snapshot_id'])
        self.assertEqual(self.service.snapshot(), original)

    def test_publication_changes_view_and_wrong_scoring_is_unavailable(self):
        before = season_week_view(self.data, 2, self.service)
        self.f.points['a'] = 20
        self.f.publish()
        after = season_week_view(self.data, 2, self.service)
        self.assertNotEqual(before['projection_generation'], after['projection_generation'])
        self.assertEqual(after['groups']['2'][0]['projection'], 20)
        self.data['league']['scoring_settings'] = {'pass_yd': 6}
        self.assertIsNone(season_week_view(self.data, 2, self.service)['groups']['2'][0]['projection'])

    def test_routes_default_order_and_week_validation(self):
        async def fresh():
            pass
        app = FastAPI()
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda:self.data, page=lambda t,b:HTMLResponse(b)))
        # Other matchup sorts ahead numerically, but authenticated own remains first.
        self.data['season_matchups']['weeks']['2']['rows'] += [{'roster_id': 9, 'matchup_id': 1, 'starters': [], 'points': None}]
        account = SimpleNamespace(membership=SimpleNamespace(league_id='league-1', roster_id=1))
        with patch('routes.matchups.current_league_context', return_value=SimpleNamespace(projection=self.service)), patch('routes.matchups.current_account', return_value=account):
            client = TestClient(app)
            html = client.get('/matchups').text
            self.assertIn('Week 2', html)
            self.assertLess(html.index('/matchups/2?week=2'), html.index('/matchups/1?week=2'))
            self.assertIn('You</span>', html)
            self.assertEqual(client.get('/matchups?week=19').status_code, 422)
            self.assertIn('week=3', client.get('/matchups/2?week=3').text)

    def test_standings_source_ranks_boundary_and_missing_rules(self):
        self.assertIsNone(playoff_boundary(self.data, {})[0])
        for i,t in enumerate(self.data['teams'],1):
            t['official_standing_rank'] = i
        for rid in range(3,7):
            self.data['teams'].append({'roster_id':rid,'team_name':f'Franchise {rid}','official_standing_rank':rid})
        ranks = {rid:rid for rid in range(1,7)}
        self.assertEqual(playoff_boundary(self.data, ranks)[0],4)
        text = render_standings(self.data)
        self.assertIn('123.45', text)
        self.assertIn('110.67', text)
        self.assertIn('Playoff-position boundary', text)
        self.assertIn('🥇', text)
        for setting,value in [('divisions',2), ('playoff_type',1), ('playoff_type',None)]:
            other = copy.deepcopy(self.data)
            other['league']['settings'][setting]=value
            self.assertIsNone(playoff_boundary(other,ranks)[0])
        self.data['teams'][0]['points_against']=None
        self.assertIn('Unavailable',render_standings(self.data))
        self.assertNotIn('clinched',text)

    def test_streak_requires_completed_pair_and_no_cross_league_borrowing(self):
        rows = self.data['season_matchups']['weeks']['1']['rows']
        rows[0]['points'], rows[1]['points'] = 12, 10
        self.assertIn('W1', completed_streak(self.data,1))
        self.data['season_matchups']['league_id']='other'
        self.assertEqual(completed_streak(self.data,1),'')

    def test_full_card_has_no_nested_control(self):
        from html.parser import HTMLParser
        class Controls(HTMLParser):
            active = False
            nested = []
            def handle_starttag(self, tag, attrs):
                if ('class', 'matchup-card-link') in attrs:
                    self.active = True
                elif self.active and tag in {'a','button','summary','input'}:
                    self.nested.append(tag)
            def handle_endtag(self, tag):
                if tag == 'a':
                    self.active = False
        parser = Controls()
        parser.feed(render_season_week(season_week_view(self.data,2,self.service)))
        self.assertEqual(parser.nested, [])
    def test_configured_submitted_slots_flex_empty_and_non_scoring_totals(self):
        for slots in (['QB','SUPER_FLEX','REC_FLEX'], ['RB','WR','TE','FLEX']):
            data=copy.deepcopy(self.data)
            data['roster_positions']=slots+['BN','IR','TAXI']
            row=data['season_matchups']['weeks']['2']['rows'][0]
            row['starters']=['a','b','e','0'][:len(slots)]
            row['starters_points']=[10,2,1,0][:len(slots)]
            side=season_week_view(data,2,self.service)['groups']['2'][0]
            self.assertEqual([p['slot'] for p in side['lineup']], slots)
            self.assertEqual(side['actual'],10.25)
            if len(slots)==4:
                self.assertIsNone(side['projection'])
                self.assertEqual(side['lineup'][-1]['name'],'Empty slot')
            else:
                self.assertEqual(side['projection'],21)

    def test_no_matchup_bye_and_viewer_in_other_league_are_honest(self):
        view=season_week_view(self.data,2,self.service)
        view.update(groups={}, viewer_roster_id=1)
        text=render_season_week(view)
        self.assertIn('no published matchup',text)
        view['byes']=[{'roster_id':1,'team':'Own franchise'}]
        text=render_season_week(view)
        self.assertIn('First-round bye',text)
        self.assertNotIn('no published matchup',text)
        async def fresh():pass
        app=FastAPI()
        app.include_router(create_matchups_router(ensure_fresh=fresh,require_data=lambda:self.data,page=lambda t,b:HTMLResponse(b)))
        foreign=SimpleNamespace(membership=SimpleNamespace(league_id='foreign',roster_id=1))
        with patch('routes.matchups.current_league_context',return_value=SimpleNamespace(projection=self.service)),patch('routes.matchups.current_account',return_value=foreign):
            self.assertNotIn('You</span>',TestClient(app).get('/matchups').text)

    def test_standings_missing_rank_and_scoring_never_fabricated(self):
        self.data['teams'][0].update(points_for=None, points_against=None)
        text=render_standings(self.data)
        self.assertIn('Official rank unavailable',text)
        self.assertNotIn('Playoff-position boundary',text)
        self.assertNotIn('🥇',text)
        self.assertIn('Unavailable',text)
        from src.core.history_context.results import standing_points
        self.assertIsNone(standing_points({},'fpts'))
        self.assertEqual(standing_points({'fpts':0,'fpts_decimal':0},'fpts'),0)
        self.assertEqual(standing_points({'fpts':123,'fpts_decimal':45},'fpts'),123.45)

    def test_missing_predecessor_does_not_establish_full_streak(self):
        data=copy.deepcopy(self.data)
        data['league']['settings'].update(leg=4,last_scored_leg=3,playoff_week_start=8)
        data['week']=4
        rows=data['season_matchups']['weeks']['2']['rows']
        rows[0]['points'],rows[1]['points']=20,10
        async def fetch(path):
            if path.endswith('/2'):
                raise TimeoutError()
            return rows
        data['season_matchups']=asyncio.run(prepare_season_matchups(data['league'],4,rows,fetch,observed_at='fixture'))
        self.assertEqual(completed_streak(data,1),'')

    def test_missing_standings_points_do_not_break_team_links_or_become_zero(self):
        from routes.teams import create_teams_router
        from services.team_headquarters import build_team_headquarters
        from tests import test_team_headquarters as headquarters_fixture
        data = copy.deepcopy(self.data)
        data['teams'][0].update(points_for=None, points_against=None)
        data['teams'][1].update(points_for=0, points_against=0)
        view = build_team_headquarters(data, 1)
        self.assertIsNone(view['performance']['points_for'])
        self.assertIsNone(view['performance']['points_against'])
        self.assertEqual(build_team_headquarters(data,2)['performance']['points_for'],0)
        async def fresh():pass
        app=FastAPI()
        app.include_router(create_teams_router(ensure_fresh=fresh,require_data=lambda:data,
            state={},page=lambda t,b:HTMLResponse(b)))
        with patch('routes.teams.historical_graph',side_effect=headquarters_fixture.TeamHeadquartersRequestSchedulingTests._history_graph):
            client=TestClient(app)
            directory=client.get('/teams')
            detail=client.get('/teams/1')
        self.assertEqual(directory.status_code,200)
        self.assertEqual(detail.status_code,200)
        self.assertIn('<b>Unavailable</b><span>Points For</span>',directory.text)
        self.assertIn('<b>0.00</b><span>Points For</span>',directory.text)
        self.assertIn('<span>Points For</span><b>Unavailable</b>',detail.text)
        self.assertIn('<span>Points Against</span><b>Unavailable</b>',detail.text)
