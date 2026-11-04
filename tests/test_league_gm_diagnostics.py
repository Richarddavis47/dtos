"""League observations describe source facts, never manager personality."""
import unittest

from tests.test_trade_intelligence import fixture_data
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
from unittest.mock import patch

from src.core.gm_behavioral_intelligence.diagnostics import LeagueGMObservations, partner_context
from src.core.history_context.season_cache import SleeperSeasonCache


class ExistingLeagueDiagnosticControls(unittest.TestCase):
    def analyze(self, rows):
        data = fixture_data()
        data['transactions'] = rows
        return IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60)).analyze(
            data, 1, include_trade_opportunities=False)

    def test_pending_and_cancelled_are_not_completed_activity(self):
        result = self.analyze([{'transaction_id': str(i), 'type': 'trade',
                              'status': status, 'roster_ids': [1, 2]}
                             for i, status in enumerate(('pending', 'cancelled', 'failed', None))])
        self.assertEqual(result.front_office_model.reports[1].activity.trades, 0)
        self.assertEqual(result.front_office_model.compatibility(1, 2).bilateral_trades, 0)

    def test_trade_count_does_not_establish_manager_personality(self):
        result = self.analyze([{'transaction_id': str(i), 'type': 'trade',
                              'status': 'complete', 'roster_ids': [1, 2]}
                             for i in range(6)])
        self.assertTrue(all(row.aggressiveness == 'Unestablished'
                            for row in result.league.gm_profiles.values()))

def completed(tid='one', **changes):
    return {'type': 'trade', 'status': 'complete', 'transaction_id': tid,
            'roster_ids': [1, 2], 'adds': {'p': 2, 'q': 1},
            'drops': {'p': 1, 'q': 2}, 'created': 1760000000000,
            'status_updated': 1760000001000, **changes}


def observed_data(league='league-a'):
    return {'league': {'league_id': league, 'season': '2026', 'settings': {'leg': 2}},
            'teams': [{'roster_id': 1, 'owner_id': 'now-a', 'team_name': 'Renamed A'},
                      {'roster_id': 2, 'owner_id': 'now-b', 'team_name': 'Franchise B'},
                      {'roster_id': 3, 'owner_id': 'now-c', 'team_name': 'Franchise C'}],
            'players': {'p': {'position': 'WR'}, 'q': {'position': 'RB'}},
            'season_transactions': {'0': [], '1': [], '2': []}, 'transactions': []}


class LeagueObservationSourceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cache = SleeperSeasonCache(Path(folder.name) / 'seasons')
        self.service = LeagueGMObservations(self.cache)
        self.data = observed_data()

    def publish(self, rows, owners=('now-a', 'old-b'), season=2025, namespace='league-a', source='past-league'):
        facts = {'league': {'league_id': source, 'season': str(season), 'status': 'complete'},
                 'rosters': [{'roster_id': i, 'owner_id': owner} for i, owner in enumerate(owners, 1)],
                 'transactions': {str(w): rows if w == 1 else [] for w in range(19)}}
        self.cache.write(self.cache.normalize(namespace, season, facts))

    def test_complete_and_zero_coverage_are_distinct_from_missing(self):
        report = self.service.report(self.data)
        self.assertEqual((report['trade_count'], report['coverage']['state']), (0, 'observed_zero'))
        self.data.pop('season_transactions')
        self.assertEqual(self.service.report(self.data)['coverage']['state'], 'unavailable')
        self.data['transactions'] = [completed()]
        result = self.service.report(self.data)
        self.assertEqual(result['coverage']['state'], 'partial')
        self.assertIn('low counts do not prove', result['coverage']['explanation'])

    def test_pending_cancelled_conflicts_dedup_and_foreign_scope(self):
        rows = [completed('one'), completed('one'), completed('pending', status='pending'),
                completed('cancelled', status='cancelled'), completed('foreign', league_id='league-b'),
                completed('conflict'), completed('conflict', status='pending')]
        self.data['transactions'] = rows
        self.data['season_transactions']['1'] = [completed('one', league_id='league-a')]
        result = self.service.report(self.data)
        self.assertEqual(result['trade_count'], 1)
        self.assertTrue(any('conflicting' in note for note in result['limitations']))

    def test_historical_manager_is_not_current_owner_or_pick_origin(self):
        self.publish([completed()])
        result = self.service.report(self.data)
        self.assertEqual(result['teams']['1']['manager']['trades'], 1)
        self.assertEqual(result['teams']['2']['manager']['trades'], 0)
        self.assertEqual(result['teams']['2']['franchise']['trades'], 1)
        self.assertIn('Exact intra-season', result['teams']['1']['attribution'])
        self.data['teams'][0]['owner_id'] = 'new-owner'
        changed = self.service.report(self.data)
        self.assertEqual(changed['teams']['1']['manager']['trades'], 0)
        self.assertNotEqual(changed['semantic_identity'], result['semantic_identity'])

    def test_current_owner_unknown_conflicting_and_rename(self):
        self.data['transactions'] = [completed()]
        self.assertEqual(self.service.report(self.data)['teams']['1']['manager']['trades'], 0)
        self.publish([completed()], owners=(None, None))
        self.assertEqual(self.service.report(self.data)['teams']['1']['manager']['trades'], 0)
        facts = {'league': {'league_id': 'past'}, 'rosters': [
            {'roster_id': 1, 'owner_id': 'now-a'}, {'roster_id': 1, 'owner_id': 'other'}],
            'transactions': {'1': [completed('conflicting-owner')]}}
        self.cache.write(self.cache.normalize('league-a', 2025, facts))
        result = self.service.report(self.data)
        self.assertEqual(result['teams']['1']['manager']['trades'], 0)
        self.data['teams'][0]['team_name'] = 'New name'
        renamed = self.service.report(self.data)
        self.assertEqual(renamed['trade_count'], result['trade_count'])
        self.assertEqual(renamed['teams']['1']['name'], 'New name')

    def test_three_party_exact_acquired_pick_and_directed_faab_once(self):
        pick = {'season': '2029', 'round': 2, 'roster_id': 3, 'previous_owner_id': 1, 'owner_id': 2}
        row = completed(roster_ids=[1, 2, 3], adds={'p': 2, 'q': 3}, drops={'p': 1, 'q': 2},
            draft_picks=[pick, deepcopy(pick)], waiver_budget=[{'sender': 3, 'receiver': 1, 'amount': 12}] * 2)
        self.data['transactions'] = [row]
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 1)
        self.assertEqual(report['unique_transferred_player_pick_assets'], 3)
        self.assertEqual(report['directed_faab_transfers'], 1)
        self.assertEqual(report['teams']['2']['franchise']['incoming']['pick'], 1)
        self.assertEqual(report['teams']['1']['franchise']['outgoing']['pick'], 1)
        self.assertEqual(report['teams']['3']['franchise']['outgoing'].get('pick', 0), 0)
        self.assertEqual(len(report['counterparty_pairs']), 3)
        from src.core.gm_behavioral_intelligence.diagnostics import _movements
        self.assertIn('PICK-2029-R2-ORIG3', [item[1] for item in _movements(row)[1]])

    def test_missing_pick_identity_and_conflicting_legs_are_qualified(self):
        self.data['transactions'] = [completed(draft_picks=[{'season': 2029, 'round': 2, 'owner_id': 2, 'previous_owner_id': 1}])]
        result = self.service.report(self.data)
        self.assertEqual(result['composition_supported_trades'], 0)
        self.assertEqual(result['pick_trades'], 0)
        self.assertEqual(result['teams']['1']['franchise']['package_style'], {})
        self.assertIn('incomplete', result['teams']['1']['summary'])

    def test_package_shape_counts_deals_not_assets(self):
        self.data['players']['r'] = {'position': 'WR'}
        self.data['transactions'] = [completed(adds={'p': 2, 'q': 1, 'r': 2}, drops={'p': 1, 'q': 2, 'r': 1})]
        result = self.service.report(self.data)
        self.assertEqual(result['teams']['1']['franchise']['package_style']['consolidation'], 1)
        self.assertEqual(result['teams']['2']['franchise']['package_style']['depth expansion'], 1)
        self.assertEqual(result['teams']['2']['franchise']['acquired_positions']['WR'], 1)

    def test_creation_ambiguous_future_and_missing_clock_do_not_date_counts(self):
        for changes in ({'status_updated': None}, {'status_updated': 'bad'},
                        {'status_updated': '2100-01-01T00:00:00Z'}, {'status_updated': 1000000000000}):
            self.data['transactions'] = [completed(**changes)]
            result = self.service.report(self.data)
            self.assertEqual(result['trade_count'], 1)
            self.assertEqual(result['completed_with_supported_clock'], 0)
            self.assertIsNone(result['latest_supported_completion'])

    def test_recent_and_old_seasons_do_not_manufacture_predictive_trend(self):
        self.publish([completed(str(i)) for i in range(4)])
        self.data['transactions'] = [completed('recent')]
        result = self.service.report(self.data)
        self.assertEqual(result['season_counts'], {'2025': 4, '2026': 1})
        self.assertEqual(result['teams']['1']['franchise']['counterparties']['2'], 5)
        self.assertNotIn('always', result['teams']['1']['summary'])

    def test_sparse_sample_need_without_history_and_conflicting_need(self):
        need = {'coverage': 'supported current week', 'need_positions_received': ['WR'],
                'numeric_impact_state': 'supported', 'pre_optimal_points': 10, 'post_optimal_points': 12}
        self.data['transactions'] = [completed()]
        report = self.service.report(self.data)
        context = partner_context(report, 2, need, ['WR'])
        self.assertEqual(context['soft_tie_break'], 0)
        self.assertIn('does not establish a matching current-manager preference', context['summary'])
        self.data['transactions'] += [completed(str(i)) for i in range(4)]
        self.publish([completed('attributed-' + str(i)) for i in range(5)], owners=('now-a', 'now-b'))
        report = self.service.report(self.data)
        self.assertEqual(partner_context(report, 2, need, ['WR'])['soft_tie_break'], 1)
        self.assertEqual(partner_context(report, 2, need, ['RB'])['soft_tie_break'], 0)
        provisional = {**need, 'coverage': 'provisional'}
        self.assertEqual(partner_context(report, 2, provisional, ['WR'])['soft_tie_break'], 0)

    def test_same_verified_source_republication_does_not_invalidate_observations(self):
        rows = [completed()]
        self.publish(rows)
        first = self.service.report(self.data)
        identity = self.service.source_identity(self.data)
        builds = self.service.builds
        self.publish(rows)  # Actual canonical producer rewrites bytes/inode, same facts/checksum.
        self.assertEqual(self.service.source_identity(self.data), identity)
        self.assertEqual(self.service.report(self.data), first)
        self.assertEqual(self.service.builds, builds)

    def test_prior_owner_history_cannot_promote_a_current_manager_partner(self):
        self.publish([completed(str(i)) for i in range(5)], owners=('old-a', 'old-b'))
        need = {'coverage': 'supported current week', 'need_positions_received': ['WR'],
                'numeric_impact_state': 'supported', 'pre_optimal_points': 10, 'post_optimal_points': 12}
        result = partner_context(self.service.report(self.data), 2, need, ['WR'])
        self.assertEqual(result['manager_sample'], 0)
        self.assertEqual(result['soft_tie_break'], 0)
        self.assertIn('does not establish a matching', result['summary'])

    def test_retrieval_only_revision_is_stable_and_real_revision_invalidates(self):
        self.data['transactions'] = [completed()]
        old = self.service.report(self.data)
        builds = self.service.builds
        self.data['transactions'][0]['retrieved_at'] = '2030-01-01'
        self.assertEqual(self.service.report(self.data), old)
        self.assertEqual(self.service.builds, builds)
        self.data['transactions'][0]['adds']['p'] = 1
        self.assertNotEqual(self.service.report(self.data)['semantic_identity'], old['semantic_identity'])
        self.publish([completed('source')])
        self.assertNotEqual(self.service.report(self.data)['semantic_identity'], old['semantic_identity'])

    def test_two_leagues_strategy_and_market_are_independent(self):
        self.publish([completed()])
        first = self.service.report(self.data)
        other = observed_data('league-b')
        self.assertEqual(self.service.report(other)['trade_count'], 0)
        self.data['strategy'] = 'REBUILD'
        self.data['market_data'] = {'providers': {'anything': {'p': 0}}}
        self.assertEqual(self.service.report(self.data), first)
        self.assertEqual(self.service.report(observed_data('league-b'))['trade_count'], 0)
        self.assertEqual(self.service.report(self.data)['trade_count'], 1)

    def test_bounded_cache_no_padding_and_no_durable_growth(self):
        for i in range(8):
            self.service.report(observed_data('league-' + str(i)))
        self.assertLessEqual(len(self.service._entries), 4)
        self.publish([completed()])
        result = self.service.report(self.data)
        def files():
            return {str(p): sha256(p.read_bytes()).hexdigest() for p in self.cache.root.rglob('*') if p.is_file()}
        before = files()
        for _ in range(5):
            self.assertEqual(self.service.report(self.data), result)
        self.assertEqual(files(), before)

    def test_home_prepared_read_never_opens_an_archive(self):
        self.publish([completed()])
        with patch.object(self.cache, 'read', side_effect=AssertionError('No Home archive decode')):
            self.assertIsNone(self.service.report(self.data, prepared_only=True))
            self.assertTrue(self.service.source_identity(self.data))

    def test_inflight_publication_change_is_withheld(self):
        build = self.service._build
        def changed(data):
            result = build(data)
            data['transactions'] = [completed('newer')]
            return result
        with patch.object(self.service, '_build', side_effect=changed):
            result = self.service.report(self.data)
        self.assertIsNone(result['trade_count'])
        self.assertEqual(result['coverage']['state'], 'unavailable')

    def test_malformed_participants_and_nonfinite_faab(self):
        for changes in ({'roster_ids': '1,2'}, {'roster_ids': [1, 1]}, {'roster_ids': [True, 2]}):
            self.data['transactions'] = [completed(**changes)]
            self.assertEqual(self.service.report(self.data)['trade_count'], 0)
        self.data['transactions'] = [completed(waiver_budget=[{'sender': 1, 'receiver': 2, 'amount': float('nan')}])]
        result = self.service.report(self.data)
        self.assertEqual(result['directed_faab_transfers'], 0)
        self.assertEqual(result['composition_supported_trades'], 0)

    def test_no_current_prices_age_or_unsupported_personality_enters_report(self):
        self.data['transactions'] = [completed()]
        self.data['market_data'] = {'generation': 'incompatible', 'providers': {'bad': {'p': 100000}}}
        self.data['players']['p']['age'] = 50
        report = self.service.report(self.data)
        self.assertTrue(any('transaction-time age' in t for t in report['limitations']))
        self.assertFalse(any(word in str(report).lower() for word in ('acceptance probability', 'desperate', 'easy to exploit', 'historical winner')))
        self.assertTrue(any('RETAINED / NOT REVALIDATED' in t for t in report['limitations']))

    def test_semantic_source_identity_ignores_transport_week_duplicates(self):
        self.data['transactions'] = [completed(leg=2, week=2)]
        self.data['season_transactions']['1'] = [completed(leg=1, week=1)]
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 1)
        self.assertEqual(report['composition_supported_trades'], 1)

    def test_high_cardinality_limit_is_explicit_not_complete(self):
        self.data['transactions'] = [completed(str(i)) for i in range(10002)]
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 10000)
        self.assertEqual(report['coverage']['state'], 'partial')
        self.assertTrue(any('limit reached' in t for t in report['limitations']))

    def test_actual_orchestrator_source_revision_with_same_transaction_count(self):
        data = fixture_data()
        data['transactions'] = [completed()]
        with patch('src.core.gm_behavioral_intelligence.diagnostics.league_gm_observations', self.service):
            engine = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60))
            first = engine.analyze(data, 1, include_trade_opportunities=False)
            again = engine.analyze(data, 1, include_trade_opportunities=False)
            self.assertTrue(again.cache_hit)
            data['transactions'][0]['status'] = 'cancelled'
            changed = engine.analyze(data, 1, include_trade_opportunities=False)
            self.assertNotEqual(first.context.snapshot_key, changed.context.snapshot_key)
            self.assertEqual(changed.front_office_model.reports[1].activity.trades, 0)

    def test_manager_changes_franchise_without_inheriting_prior_owner_behavior(self):
        self.publish([completed()], owners=('now-b', 'now-a'))
        result = self.service.report(self.data)
        self.assertEqual(result['teams']['1']['manager']['trades'], 0)
        self.assertEqual(result['teams']['2']['manager']['trades'], 0)
        self.assertTrue(all('this franchise only' in r['attribution'] for r in result['teams'].values()))

    def test_prepared_publication_reuses_verified_small_sections_without_archive_decode(self):
        self.publish([completed()])
        with patch.object(self.cache, 'read', side_effect=AssertionError('redundant archive decode')):
            result = self.cache.sections('league-a', 2025, ('league', 'rosters', 'transactions'))
        self.assertTrue(result['rosters'])

    def test_compact_sections_decode_once_and_publication_race_cannot_poison_cache(self):
        self.publish([completed()])
        with self.cache._checksum_lock:
            self.cache._section_cache.clear()  # Exercise a genuinely cold reader.
        names = ('league', 'rosters', 'transactions')
        with patch.object(self.cache, 'read', wraps=self.cache.read) as read:
            self.assertTrue(self.cache.sections('league-a', 2025, names))
            self.assertTrue(self.cache.sections('league-a', 2025, names))
            self.assertEqual(read.call_count, 1)
        normalize = self.cache.normalize
        newer = normalize('league-a', 2025, {'league': {'league_id': 'past-league'}, 'transactions': {'1': [completed('newer')]}})
        def interrupted(*args):
            result = normalize(*args)
            self.cache.write(newer)
            return result
        with patch.object(self.cache, 'normalize', side_effect=interrupted):
            with self.assertRaisesRegex(ValueError, 'publication changed'):
                self.cache.read('league-a', 2025)
        self.assertEqual(self.cache.section('league-a', 2025, 'transactions')['1'][0]['transaction_id'], 'newer')


class LeagueDiagnosticHTTPTests(unittest.TestCase):
    def setUp(self):
        from tests.test_roster_diagnostic_aging import DiagnosticAgingTests
        self.f = DiagnosticAgingTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data = self.f.data
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.service = LeagueGMObservations(SleeperSeasonCache(Path(folder.name)))
        self.enterContext(patch('src.core.gm_behavioral_intelligence.diagnostics.league_gm_observations', self.service))
        self.data['transactions'] = [completed(str(i), adds={'a': 2}, drops={'a': 1}) for i in range(5)]
        self.owner = self.f.f.f
        self.client = self.owner.f.client

    def test_actual_league_team_trade_and_cached_home_use_same_observations(self):
        from src.core.intelligence import roster_diagnostics
        with patch.object(roster_diagnostics, '_now', return_value=self.f.observed):
            league = self.client.get('/league')
            self.assertEqual(league.status_code, 200, league.text)
            self.assertIn('League identity', league.text)
            self.assertIn('5 completed trades observed', league.text)
            team = self.client.get('/teams/2')
            self.assertEqual(team.status_code, 200, team.text)
            self.assertIn('This franchise completed 5 observed trades', team.text)
            result = self.owner.evaluate()
            self.assertEqual(result.status_code, 200, result.text)
            evaluation = result.json()['evaluation']
            context = evaluation['dimensions']['league_partner_context']
            self.assertEqual(context['franchise_sample'], 5)
            self.assertEqual(context['source_identity'], self.service.report(self.data)['semantic_identity'])
            self.assertEqual(evaluation['recommendation'], 'WORTH PURSUING')
            from src.ui.home_trade_opportunities import cards
            output = cards([{**result.json(), 'home_offer': 'fixture'}], 1)
            self.assertIn('Why this partner:', output)
            self.assertIn('Cost and uncertainty:', output)
            self.assertIn('Why this partner?', self.client.get('/static/js/trade_workspace.js').text)

    def test_league_report_respects_authenticated_selected_strategy(self):
        from src.core.intelligence.orchestrator import intelligence_orchestrator
        with patch.object(intelligence_orchestrator, 'analyze', wraps=intelligence_orchestrator.analyze) as analyze:
            response = self.client.get('/league')
        self.assertEqual(response.status_code, 200)
        preferences = analyze.call_args.kwargs.get('user_preferences') or (analyze.call_args.args[2] if len(analyze.call_args.args) > 2 else {})
        self.assertEqual(preferences.get('strategy'), 'REBUILD')

    def test_no_history_is_neutral_and_home_does_not_discover_or_read_archives(self):
        self.data['transactions'] = []
        with patch.object(self.service._cache(), 'read', side_effect=AssertionError('Home archive read')), patch('services.trade_intelligence.generate_trade_workflow', side_effect=AssertionError('Home search')):
            self.assertEqual(self.client.get('/').status_code, 200)
        result = self.owner.evaluate()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['evaluation']['recommendation'], 'WORTH PURSUING')
        self.assertEqual(result.json()['evaluation']['dimensions']['league_partner_context']['soft_tie_break'], 0)

    def test_read_only_opponent_authority_and_invalidated_home_source(self):
        old = self.client.get('/api/trades/home-opportunities?front_office=1').json()['source_identity']
        self.assertEqual(self.client.get('/teams/2').status_code, 200)
        response = self.client.post('/api/trades/evaluate', json={**self.owner.payload, 'active_roster_id': 2}, headers={'X-CSRF-Token': self.owner.f.csrf})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail']['code'], 'unauthorized_franchise')
        self.data['transactions'][0]['status'] = 'cancelled'
        changed = self.client.get('/api/trades/home-opportunities?front_office=1').json()
        self.assertNotEqual(changed['source_identity'], old)
        self.assertEqual(changed['count'], 0)

    def test_trade_history_match_only_breaks_otherwise_equivalent_results(self):
        from services.trade_search_policy import rank_key
        base = {'evaluation': {'recommendation': 'WORTH PURSUING', 'values': {'ratio': 1}, 'dimensions': {'league_partner_context': {'soft_tie_break': 0}}, 'provenance': {'evaluation_id': 'a'}}}
        matched = deepcopy(base)
        matched['evaluation']['dimensions']['league_partner_context']['soft_tie_break'] = 1
        matched['evaluation']['provenance']['evaluation_id'] = 'z'
        self.assertLess(rank_key(matched), rank_key(base))
        matched['evaluation']['recommendation'] = 'NOT WORTH IT'
        self.assertGreater(rank_key(matched), rank_key(base))

class ObservationBoundRecencyTests(unittest.TestCase):
    def test_observation_limit_preserves_current_before_older_history(self):
        fixture = LeagueObservationSourceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.publish, self.data, self.service = fixture.publish, fixture.data, fixture.service
        self.publish([completed('old')])
        self.data['transactions'] = [completed('current')]
        with patch('src.core.gm_behavioral_intelligence.diagnostics.MAX_ROWS', 1):
            result = self.service.report(self.data)
        self.assertEqual(result['trade_count'], 1)
        self.assertEqual(result['teams']['1']['franchise']['references'][0]['transaction_id'], 'current')
        self.assertEqual(result['coverage']['state'], 'partial')
