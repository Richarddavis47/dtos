"""Current-season production uses canonical facts, never roster-history totals."""
from pathlib import Path
import tempfile
import unittest

from services.player_evidence import prepare_player_production
from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.global_production import GlobalProduction
from src.core.data_platform.normalization.identity import PlayerIdentityResolver
from src.core.historical_memory.providers import normalize_nflverse_row


def raw(week=1, **changes):
    row = dict(player_id='00-test', season='2026', week=str(week), season_type='REG',
               game_id=f'g-{week}', position='QB', team='BUF', completions='20', attempts='30',
               passing_yards='250', passing_tds='2', passing_interceptions='1',
               carries='4', rushing_yards='20', rushing_tds='0', receptions='0', targets='0',
               receiving_yards='0', receiving_tds='0', passing_2pt_conversions='0',
               rushing_2pt_conversions='0', receiving_2pt_conversions='0',
               fumbles_total='0', fumbles_lost_total='0', special_teams_tds='0',
               fg_made='0', fg_att='0', pat_made='0', pat_att='0',
               fg_made_0_19='0', fg_made_20_29='0', fg_made_30_39='0',
               fg_made_40_49='0', fg_made_50_59='0', fg_made_60_='0',
               kickoff_return_yards='0', punt_return_yards='0')
    return row | changes


def prepared(path, *, scoring=None, weeks=range(1, 9), league='A', source_rows=None, player='4984', season=2026):
    store = GlobalEvidenceStore(path, reserve_bytes=0)
    rows = [normalize_nflverse_row(row) for row in (source_rows or [raw(w) for w in weeks])]
    GlobalProduction(store).publish_batch(rows, identities=PlayerIdentityResolver({player: {'gsis_id': '00-test'}}),
        game_dates={row['game_id']: f"{row['season']}-09-{int(row['week']):02d}T00:00:00Z" for row in rows},
        retrieved_at='2026-10-31T00:00:00Z')
    data = dict(league=dict(league_id=league, season=str(season), status='in_season'),
                nfl_state=dict(season='2026', week=9), players={player: {'position': 'QB'}},
                scoring_settings=scoring or {'pass_yd': .04, 'pass_td': 4, 'pass_int': -2, 'rush_yd': .1})
    return prepare_player_production(data, expected_league_id=league, as_of='2026-11-01T00:00:00Z', path=path)


class CurrentProductionCoverageTests(unittest.TestCase):
    def test_zero_coefficient_needs_no_statistic_but_missing_active_stat_does(self):
        row = GlobalProduction.score_game({'rec': 0}, {'rec': 1, 'unsupported': 0})
        self.assertEqual(row['availability'], 'calculated')
        self.assertEqual(row['fantasy_points'], 0)
        self.assertIsNone(GlobalProduction.score_game({'rec': 0}, {'rec': 1, 'unsupported': .1})['fantasy_points'])

    def test_player_record_does_not_require_team_defense_but_does_require_player_special_teams(self):
        values = {'position': 'QB', 'pass_yd': 250}
        row = GlobalProduction.score_game(values, {'pass_yd': .04, 'pts_allow_0': 10, 'sack': 1})
        self.assertEqual(row['fantasy_points'], 10)
        self.assertEqual(set(row['inapplicable_components']), {'pts_allow_0', 'sack'})
        partial = GlobalProduction.score_game(values, {'pass_yd': .04, 'st_ff': 1})
        self.assertIsNone(partial['fantasy_points'])
        self.assertEqual(partial['missing_components'], ['st_ff'])
        for position in ('DEF', '', 'unknown'):
            self.assertIsNone(GlobalProduction.score_game(values | {'position': position}, {'sack': 1})['fantasy_points'])

    def test_published_kicking_and_return_statistics_survive_normalization(self):
        stats = normalize_nflverse_row(raw(position='K', fg_made='2', fg_att='2',
            fg_made_50_59='1', fg_made_60_='1', pat_att='3', pat_made='3',
            special_teams_tds='1', kickoff_return_yards='40', punt_return_yards='12'))['raw_stats']
        self.assertEqual([stats[k] for k in ('fgm', 'fgm_50p', 'xpm', 'fgmiss', 'xpmiss', 'st_td', 'kr_yd', 'pr_yd')],
                         [2, 2, 3, 0, 0, 1, 40, 12])
        unknown = normalize_nflverse_row(raw(fg_made_60_='', fg_att='', pat_att=''))['raw_stats']
        for key in ('fgm_50p', 'fgmiss', 'xpmiss'):
            self.assertIsNone(unknown[key])
        self.assertNotIn('st_ff', stats)

    def test_ongoing_season_preserves_eight_observations_and_exact_denominator(self):
        with tempfile.TemporaryDirectory() as folder:
            result = prepared(Path(folder)/'facts.sqlite3')
            row = result['players']['4984']['production']['windows'][3]
            self.assertEqual(row['fantasy_points'], 18)
            self.assertEqual((row['observation_count'], row['scored_count']), (8, 8))
            self.assertEqual(list(row['weeks']), list(range(1, 9)))
            self.assertEqual(row['season'], 2026)
            self.assertNotIn('183.82', str(result))

    def test_partial_scoring_retains_coverage_and_names_the_actual_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            result = prepared(Path(folder)/'facts.sqlite3', scoring={'pass_yd': .04, 'st_ff': 1})
            row = result['players']['4984']['production']['windows'][3]
            self.assertIsNone(row['fantasy_points'])
            self.assertEqual((row['observation_count'], row['scored_count']), (8, 0))
            self.assertEqual(tuple(row['missing_components']), ('st_ff',))
            self.assertIn('st_ff', ' '.join(result['players']['4984']['production']['limitations']))

    def test_no_fake_bye_dnp_or_missing_week_zero_and_no_ownership_double_count(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'facts.sqlite3'
            a=prepared(path, weeks=(1, 3, 8))
            b=prepared(path, weeks=(1, 3, 8))
            self.assertEqual(a, b)
            row=a['players']['4984']['production']['windows'][3]
            self.assertEqual(row['observation_count'], 3)
            self.assertEqual(tuple(row['weeks']), (1, 3, 8))
            self.assertEqual(row['fantasy_points'], 18)

    def test_window_adapter_old_cache_keeps_unknown_counts_and_new_cache_roundtrips(self):
        from src.core.player_value_projection.canonical_production import prepared_production_context
        with tempfile.TemporaryDirectory() as folder:
            result=prepared(Path(folder)/'facts.sqlite3')
            import json
            restored=json.loads(json.dumps(result))
            context=prepared_production_context(restored, league_id='A', player_id='4984')
            self.assertEqual(context.windows[3].observation_count, 8)
            legacy=json.loads(json.dumps(result))
            for row in legacy['players']['4984']['production']['windows']:
                for key in ('season','weeks','observation_count','scored_count','missing_components'):
                    row.pop(key,None)
            legacy['players']['4984'].pop('current_sample_count')
            legacy['players']['4984'].pop('previous_sample_count')
            old=prepared_production_context(legacy, league_id='A', player_id='4984')
            self.assertIsNone(old.windows[3].observation_count)
            self.assertEqual(old.windows[3].fantasy_points, 18)
            with self.assertRaises(ValueError):
                prepared_production_context(restored, league_id='other', player_id='4984')

    def test_new_fields_do_not_change_reference_values_or_input_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'facts.sqlite3'
            first=prepared(path)
            counts=GlobalEvidenceStore(path,readonly=True).counts()
            other=prepared(path, league='B', scoring={'pass_yd': .1})
            self.assertEqual(first['reference_generation'], other['reference_generation'])
            self.assertEqual(counts, GlobalEvidenceStore(path,readonly=True).counts())
            self.assertEqual(other['players']['4984']['production']['windows'][3]['fantasy_points'],25)

    def test_current_week_is_excluded_when_authoritative_context_supplies_the_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            value=prepared(Path(folder)/'facts.sqlite3', weeks=range(1, 10))
            row=value['players']['4984']['production']['windows'][3]
            self.assertEqual(value['completed_week_boundary'], 8)
            self.assertEqual(row['observation_count'], 8)
            self.assertNotIn(9, row['weeks'])
            self.assertIn('Current-week', ' '.join(value['players']['4984']['production']['limitations']))

    def test_legacy_same_generation_sample_count_is_preserved_without_inventing_scored_count(self):
        from src.core.player_value_projection.canonical_production import prepared_production_context
        with tempfile.TemporaryDirectory() as folder:
            value=prepared(Path(folder)/'facts.sqlite3', scoring={'pass_yd': .04, 'st_ff': 1})
            for row in value['players']['4984']['production']['windows']:
                for key in ('observation_count','scored_count','weeks','missing_components'):
                    row.pop(key,None)
            row=prepared_production_context(value,league_id='A',player_id='4984').windows[3]
            self.assertEqual(row.observation_count,8)
            self.assertIsNone(row.scored_count)
            self.assertIsNone(row.fantasy_points)
            self.assertEqual(row.missing_components,())

    def test_unknown_position_does_not_create_a_team_scoring_exemption(self):
        result=GlobalProduction.score_game({'pass_yd':250}, {'pass_yd':.04,'sack':1})
        self.assertIsNone(result['fantasy_points'])
        self.assertEqual(result['known_component_points'],10)

    def test_real_zero_and_partial_game_leave_other_windows_supported(self):
        from src.core.player_value_projection.canonical_production import canonical_production_context
        from tests.test_canonical_production_context import evidence
        data=evidence([None,0,0,0])
        data['production']['games'][0].update(availability='incomplete',missing_components=['st_ff'])
        row=canonical_production_context(data)
        self.assertIsNone(row.windows[3].fantasy_points)
        self.assertEqual(row.windows[1].fantasy_points,0)
        self.assertEqual(row.windows[3].scored_count,3)
        self.assertEqual(row.windows[3].observation_count,4)

    def test_invalid_stat_and_coefficient_never_become_a_complete_zero(self):
        for value in (True,float('nan'),float('inf'),'not numeric'):
            self.assertIsNone(GlobalProduction.score_game({'rec':value},{'rec':1})['fantasy_points'])
            with self.assertRaises(ValueError):
                GlobalProduction.score_game({'rec':0},{'rec':value})


class ProductionViewFixture:
    """Real store/preparation/Market/dossier paths, entirely disposable."""
    def __init__(self, case, *, league='1314695233040052224', page=None, scoring=None):
        from tests.test_market_history_coverage import MarketHistoryFixture
        from routes.transactions import create_transactions_router
        from unittest.mock import AsyncMock, patch
        from src.core.history_context.store import CanonicalHistoryStore
        from src.core.data_platform.storage import SnapshotWarehouse
        from src.core.data_platform import data_platform
        self.f=MarketHistoryFixture(case,league=league,page=page)
        self.case=case
        self.scoring=scoring or {'pass_yd':.04,'pass_td':4,'pass_int':-2,'rush_yd':.1,'pts_allow_0':10,'sack':1,'unused':0}
        self.path=self.f.root/'global-production.sqlite3'
        self.set_scoring(self.scoring)
        self.history=CanonicalHistoryStore()
        case.enterContext(patch.object(data_platform,'warehouse',SnapshotWarehouse()))
        case.enterContext(patch('routes.transactions.canonical_history_store',self.history))
        self.f.app.include_router(create_transactions_router(ensure_fresh=AsyncMock(),
            refresh_transactions=AsyncMock(return_value=True),require_data=lambda:self.f.data,
            state=self.f.state,page=page or (lambda title,body: __import__('fastapi.responses',fromlist=['HTMLResponse']).HTMLResponse(body))))

    def set_scoring(self, scoring):
        from src.core.valuation.universe import ValuationUniverse
        from src.core.valuation_intelligence.engine import _score_asset
        self.f.data['scoring_settings']=scoring
        value=prepared(self.path,league=self.f.data['league']['league_id'],scoring=scoring,player='1')
        self.f.data['canonical_player_production']=value
        universe=ValuationUniverse(self.f.data, self.f.state)
        self.f.data['valuation_intelligence']['assets']['player:1']=_score_asset(universe.by_id['player:1'],[],{},None)
        self.f.data['valuation_intelligence']['generated_at']=value['generation']
        self.f.cache.clear()
        self.f.market=self.f.cache.get(self.f.data,self.f.state,self.f.history,self.f.data['league']['league_id'])
        return value

    def api(self):
        return self.f.client.get('/api/market/assets/player:1').json()['valuation']['canonical_production']


class ProductionRenderedCoverageTests(unittest.TestCase):
    def test_complete_and_incomplete_canonical_samples_reach_both_rendered_consumers(self):
        f=ProductionViewFixture(self)
        for path in ('/market?selected=player%3A1','/players/1?front_office=4'):
            response=f.f.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn('8 of 8 observations',response.text)
            self.assertIn('18.00 fantasy points per observed game',response.text)
            self.assertNotIn('This player context does not include a season production summary',response.text)
        self.assertEqual(f.api()['windows'][3]['fantasy_points'],18)
        f.set_scoring({'pass_yd':.04,'st_ff':1,'sack':1})
        self.assertIsNone(f.api()['windows'][3]['fantasy_points'])
        for path in ('/market?selected=player%3A1','/players/1?front_office=4'):
            response=f.f.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn('0 of 8 observations',response.text)
            self.assertIn('st_ff',response.text)
            self.assertIn('average is withheld',response.text)

    def test_failed_refresh_preserves_the_same_facts_and_changes_both_cached_explanations(self):
        f=ProductionViewFixture(self)
        before=f.api()
        f.f.client.get('/market?selected=player%3A1')
        f.f.state['last_error']='Disposable upstream failure'
        for path in ('/market?selected=player%3A1','/players/1?front_office=4'):
            response=f.f.client.get(path)
            self.assertIn('league refresh did not complete',response.text)
            self.assertIn('8 of 8 observations',response.text)
        self.assertEqual(f.api(),before)

    def test_actual_saved_cache_restoration_preserves_production_publication(self):
        from unittest.mock import patch
        from services import sleeper
        f=ProductionViewFixture(self)
        original=f.api()
        with patch.object(sleeper,'league_cache_file',return_value=f.f.root/'saved-cache.json'):
            sleeper.save_cache(state=f.f.state,league_id=f.f.data['league']['league_id'])
            self.assertTrue((f.f.root/'saved-cache.json').exists())
            restored={}
            sleeper.load_cache(state=restored,league_id=f.f.data['league']['league_id'])
        self.assertEqual(restored['data']['canonical_player_production'],__import__('json').loads(__import__('json').dumps(f.f.data['canonical_player_production'])))
        f.f.data=restored['data']
        f.f.state.update(restored)
        f.f.cache.clear()
        f.f.market=f.f.cache.get(f.f.data,f.f.state,f.f.history,f.f.data['league']['league_id'])
        self.assertEqual(f.api(),original)
        self.assertIn('8 of 8 observations',f.f.client.get('/players/1?front_office=4').text)

    def test_scored_roster_history_never_substitutes_for_missing_canonical_points(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        # A synthetic roster-history total deliberately differs from canonical
        # production. It is presentation evidence, not the original Granite run.
        f=ProductionViewFixture(self,scoring={'pass_yd':.04,'st_ff':1})
        from routes.transactions import historical_graph
        history=historical_graph(f.history,f.f.data['league']['league_id'],f.f.data).player_dossier('1')
        history['season_summaries']=[dict(season=2026,status='in_progress',games_observed=8,starts=8,
            bench_appearances=0,unknown_role_appearances=0,fantasy_points=183.82,overall_rank=None,
            positional_rank=None,completeness_percentage=44.4)]
        with patch('routes.transactions.historical_graph',return_value=SimpleNamespace(player_dossier=lambda _:history)):
            response=f.f.client.get('/players/1?front_office=4')
        self.assertEqual(response.status_code,200)
        self.assertIn('183.82',response.text)
        self.assertIn('average is withheld',response.text)
        self.assertIsNone(f.api()['windows'][3]['fantasy_points'])


class ProductionPeriodControls(unittest.TestCase):
    def test_completed_season_is_still_an_observed_sample_not_a_full_season_total(self):
        with tempfile.TemporaryDirectory() as folder:
            value=prepared(Path(folder)/'facts.sqlite3',season=2025,
                source_rows=[raw(w,season='2025') for w in range(1,9)])
            self.assertIsNone(value['completed_week_boundary'])
            row=value['players']['4984']['production']['windows'][3]
            self.assertEqual(row['fantasy_points'],18)
            self.assertEqual(row['season'],2025)
            self.assertEqual(row['observation_count'],8)

    def test_current_absence_keeps_previous_production_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            value=prepared(Path(folder)/'facts.sqlite3',source_rows=[raw(1,season='2025')])
            rows=value['players']['4984']['production']['windows']
            self.assertIsNone(rows[3]['fantasy_points'])
            self.assertEqual(rows[3]['observation_count'],0)
            self.assertEqual(rows[4]['fantasy_points'],18)

    def test_position_bonuses_use_actual_eligible_counts_not_guessed_participation(self):
        for position,points in [('QB',0),('RB',2.5),('WR',0),('TE',0)]:
            result=GlobalProduction.score_game({'position':position,'rec':5},{'bonus_rec_rb':.5})
            self.assertEqual(result['fantasy_points'],points)
        self.assertIsNone(GlobalProduction.score_game({'position':'RB'},{'bonus_rec_rb':.5})['fantasy_points'])
        self.assertIsNone(GlobalProduction.score_game({'rec':5},{'bonus_rec_rb':.5})['fantasy_points'])
        # NFL FB alone does not prove Sleeper's RB-bonus classification.
        self.assertIsNone(GlobalProduction.score_game({'position':'FB','rec':5},{'bonus_rec_rb':.5})['fantasy_points'])

    def test_required_kicking_values_score_only_exact_counts(self):
        values=normalize_nflverse_row(raw(position='K',fg_made='2',fg_att='2',
            fg_made_40_49='1',fg_made_50_59='1',pat_made='2',pat_att='2'))['raw_stats']
        values['position']='K'
        score=GlobalProduction.score_game(values,{'fgm_40_49':4,'fgm_50p':5,'xpm':1,'fgmiss':-1,'pts_allow_0':10})
        self.assertEqual(score['fantasy_points'],11)
        bad=normalize_nflverse_row(raw(position='K',fg_att='2',fg_made='1'))['raw_stats']
        self.assertIsNone(GlobalProduction.score_game(bad|{'position':'K'},{'fgmiss':-1})['fantasy_points'])

    def test_failed_publication_retains_the_original_admitted_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'facts.sqlite3'
            original=prepared(path)
            from src.core.data_platform.global_evidence import GlobalFact,IngestionCheckpoint
            store=GlobalEvidenceStore(path,reserve_bytes=0)
            store.publish([GlobalFact('production','sleeper:4984','nflverse','future-failed',
                '2026-09-02T00:00:00Z',None,{'rec':99},season=2026,week=2)],
                retrieved_at='2026-10-31T10:00:00Z',checkpoint=IngestionCheckpoint('failed','unadmitted',0,1,False))
            data={'league':{'league_id':'A','season':2026},'nfl_state':{'season':'2026','week':9},
                  'players':{'4984':{}},'scoring_settings':{'pass_yd':.04,'pass_td':4,'pass_int':-2,'rush_yd':.1}}
            after=prepare_player_production(data,expected_league_id='A',as_of='2026-11-01T00:00:00Z',path=path)
            self.assertEqual(after,original)


class ProductionFreshSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sleeper_sync_publishes_canonical_production_before_cache_save(self):
        from contextlib import ExitStack
        from unittest.mock import patch,Mock
        from services import sleeper
        from services.player_evidence import prepare_player_production as real_prepare
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'production.sqlite3'
            prepared(path,player='1')
            scoring={'pass_yd':.04,'pass_td':4,'pass_int':-2,'rush_yd':.1,'pts_allow_0':10,'sack':1,'unused':0}
            league=dict(league_id='2100000000000000999',name='Disposable source league',season='2026',
                status='in_season',total_rosters=1,roster_positions=['QB','K','DEF','BN'],
                settings={'leg':9,'draft_rounds':3},scoring_settings=scoring)
            async def get(client,route):
                if route=='/league/'+league['league_id']:
                    return league
                if route.endswith('/users'):
                    return [dict(user_id='fixture-owner',display_name='Fixture')]
                if route.endswith('/rosters'):
                    return [dict(roster_id=1,owner_id='fixture-owner',players=['1'],starters=['1'],settings={})]
                if route=='/players/nfl':
                    return {'1':dict(player_id='1',position='QB',fantasy_positions=['QB'],full_name='Source Player',team='BUF')}
                if route=='/state/nfl':
                    return dict(season='2026',week=9,season_type='regular')
                return []
            state={'data':None,'syncing':False}
            projection=Mock()
            projection.begin_external_refresh.return_value=False
            projection.snapshot.return_value=None
            with ExitStack() as stack:
                stack.enter_context(patch.object(sleeper,'sleeper_get',side_effect=get))
                stack.enter_context(patch.object(sleeper,'league_cache_file',return_value=Path(folder)/'cache.json'))
                stack.enter_context(patch.object(sleeper,'refresh_public_market',return_value={'provider_status':{}}))
                stack.enter_context(patch.object(sleeper,'player_history_evidence_batch',return_value={'1':{}}))
                for name in ('src.core.valuation.normalization.prepare_market_normalization',
                    'src.core.intelligence.pick_context.prepare_pick_context','src.core.relevant_players.apply_relevant_player_filter',
                    'src.core.intelligence.team_strength.prepare_for_data','src.core.intelligence.strength_history.record_strength_history',
                    'src.core.intelligence_memory.checkpoint_pipeline.ingest_runtime'):
                    stack.enter_context(patch(name,return_value={}))
                stack.enter_context(patch('src.core.valuation.ranking.prepare_global_player_ranks',return_value={'players':{}}))
                stack.enter_context(patch('src.core.relevant_players.build_relevant_player_universe',return_value={'member_ids':['1']}))
                for name in ('build_provider_network','build_valuation_intelligence','audit_market_calibration'):
                    stack.enter_context(patch.object(sleeper,name))
                def prepare_actual(data,**kwargs):
                    return real_prepare(data,**kwargs,path=path)
                prepare_call=stack.enter_context(patch('services.player_evidence.prepare_player_production',side_effect=prepare_actual))
                await sleeper.sync_sleeper_league(league['league_id'],state,projections=projection)
                self.assertIsNone(state['last_error'])
                prepare_call.assert_called_once()
                row=state['data']['canonical_player_production']['players']['1']['production']['windows'][3]
                self.assertEqual((row['fantasy_points'],row['observation_count']),(18,8))
                self.assertEqual(state['preparation_state'],'ready')
                self.assertTrue((Path(folder)/'cache.json').exists())
                restored={}
                sleeper.load_cache(state=restored,league_id=league['league_id'])
                self.assertEqual(restored['data']['canonical_player_production']['generation'],state['data']['canonical_player_production']['generation'])


class ProductionPublishedConfigurationTests(unittest.TestCase):
    def test_public_league_coefficients_expose_specific_remaining_gaps_without_fabricating_points(self):
        import json
        configs=json.loads((Path(__file__).parent/'fixtures/current_production_leagues.json').read_text())['leagues']
        for league in configs:
            with self.subTest(league=league['name']),tempfile.TemporaryDirectory() as folder:
                value=prepared(Path(folder)/'facts.sqlite3',league=league['league_id'],scoring=league['scoring_settings'])
                window=value['players']['4984']['production']['windows'][3]
                self.assertEqual(window['observation_count'],8)
                self.assertIsNone(window['fantasy_points'])
                missing=set(window['missing_components'])
                self.assertNotIn('sack',missing)
                self.assertNotIn('pts_allow_0',missing)
                if league['name']=='Granite Gridiron':
                    self.assertEqual(missing,{'st_ff','st_fum_rec'})
                elif league['name']=='Day Traders':
                    self.assertTrue({'st_ff','st_fum_rec','pass_td_40p'}<=missing)
                else:
                    self.assertIn('pass_td_40p',missing)
                    self.assertNotIn('fgm_50_59',missing)

    def test_big_play_counters_never_become_long_touchdown_counters(self):
        values=normalize_nflverse_row(raw(passing_40='2',rushing_40='0',receiving_40='1'))['raw_stats']
        self.assertEqual([values[k] for k in ('pass_cmp_40p','rush_40p','rec_40p')],[2,0,1])
        self.assertEqual(GlobalProduction.score_game(values,{'pass_cmp_40p':.5})['fantasy_points'],1)
        self.assertIsNone(GlobalProduction.score_game(values,{'pass_td_40p':1})['fantasy_points'])


class ProductionFreshnessControls(unittest.TestCase):
    def test_failed_check_does_not_revalidate_old_facts(self):
        from services.global_evidence import canonical_player_evidence
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'global.sqlite3'
            prepared(path)
            store=GlobalEvidenceStore(path,reserve_bytes=0)
            store.record_source_check('nflverse/production/2026',source_identity=None,
                checked_at='2026-11-05T23:00:00Z',status='failed',details={'reason':'source_failure'})
            data={'league':{'league_id':'A','season':2026},'nfl_state':{'season':'2026','week':9},
                  'players':{'4984':{}},'scoring_settings':{'pass_yd':.04}}
            report=canonical_player_evidence('4984',data,expected_league_id='A',path=path,as_of='2026-11-06T00:00:00Z')
            self.assertEqual(report['availability_detail']['reason'],'retained_evidence_not_current')
            self.assertIn('latest_source_check_failed',report['limitations'])
            self.assertEqual(report['production']['ppg'],10)

    def test_source_failure_qualification_reaches_both_views_without_erasing_values(self):
        f=ProductionViewFixture(self)
        store=GlobalEvidenceStore(f.path,reserve_bytes=0)
        before=f.api()['windows'][3]
        store.record_source_check('nflverse/production/2026',source_identity=None,
            checked_at='2026-10-31T23:00:00Z',status='partial',details={'unresolved_rows':1})
        f.set_scoring(f.scoring)
        self.assertEqual(f.api()['windows'][3],before)
        for path in ('/market?selected=player%3A1','/players/1?front_office=4'):
            text=f.f.client.get(path).text
            self.assertIn('Latest canonical production source check is partial',text)
            self.assertIn('8 of 8 observations',text)
