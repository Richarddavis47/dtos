"""Historical source defects exercised through real publication and consumers."""
from copy import deepcopy
from hashlib import sha256
from itertools import permutations
import unittest
from unittest.mock import patch

from tests import test_league_gm_diagnostics as fixtures

completed = fixtures.completed


def without_consideration(tid='missing'):
    return {key: value for key, value in completed(tid).items()
            if key not in {'adds', 'drops', 'draft_picks', 'waiver_budget'}}


class LeagueGMIntegrityReproductions(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.LeagueDiagnosticHTTPTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data, self.service, self.client = self.f.data, self.f.service, self.f.client
        self.data['transactions'] = []

    def publish(self, rows, season=2025):
        cache = self.service._cache()
        facts = {'league': {'league_id': 'past-' + str(season), 'season': str(season), 'status': 'complete'},
                 'rosters': [{'roster_id': 1, 'owner_id': 'historical-owner'},
                             {'roster_id': 2, 'owner_id': 'other-owner'}],
                 'transactions': {str(i): rows if i == 1 else [] for i in range(19)}}
        league = self.data['league']['league_id']
        return cache.write(cache.normalize(league, season, facts))

    def test_truncated_producer_archive_does_not_break_authenticated_routes(self):
        self.publish([completed('valid-adjacent')], 2024)
        path = self.publish([completed('truncated')])
        path.write_bytes(path.read_bytes()[:-8])
        digest = sha256(path.read_bytes()).hexdigest()
        for route in ('/league', '/teams/1', '/teams/2'):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn('retained source unavailable', response.text)
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 1)
        self.assertEqual(report['coverage']['state'], 'partial')
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), digest)

    def test_missing_consideration_remains_countable_but_not_supported_zero(self):
        self.data['transactions'] = [without_consideration()]
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 1)
        self.assertEqual(report['composition_supported_trades'], 0)
        for route in ('/league', '/teams/1', '/teams/2'):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn('Consideration unavailable', response.text)
                self.assertNotIn('acquiring 0 supported exact picks', response.text)
                self.assertNotIn('received 0 players / 0 exact picks', response.text)

    def test_reordered_participants_are_one_completed_event_not_conflict(self):
        first = completed('equivalent', adds={'a': 2}, drops={'a': 1})
        self.data['transactions'] = [first, {**deepcopy(first), 'roster_ids': [2, 1]}]
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 1)
        self.assertEqual(report['composition_supported_trades'], 1)
        self.assertFalse(any('conflicting transaction' in note for note in report['limitations']))
        for route in ('/league', '/teams/1', '/teams/2'):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn('1 observed trade', response.text)

    def test_corrupt_payload_and_invalid_gzip_routes_recover_without_source_repair(self):
        self.publish([completed('independent')], 2024)
        for corrupt in (lambda b: b[:len(b) // 2], lambda b: b'not gzip'):
            path = self.publish([completed('bad')])
            path.write_bytes(corrupt(path.read_bytes()))
            before = sha256(path.read_bytes()).hexdigest()
            for route in ('/league', '/teams/1', '/teams/2'):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn('retained source unavailable', response.text)
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), before)
        self.publish([completed('recovered')])
        for route in ('/league', '/teams/1', '/teams/2'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('retained source unavailable', response.text)
        self.assertEqual(self.service.report(self.data)['trade_count'], 2)

    def test_incomplete_history_is_shared_trade_context_not_a_recommendation_veto(self):
        path = self.publish([completed('bad')])
        path.write_bytes(path.read_bytes()[:-8])
        self.data['transactions'] = [without_consideration()]
        response = self.f.owner.evaluate()
        self.assertEqual(response.status_code, 200, response.text)
        evaluation = response.json()['evaluation']
        self.assertEqual(evaluation['recommendation'], 'WORTH PURSUING')
        context = evaluation['dimensions']['league_partner_context']
        self.assertEqual(context['franchise_sample'], 1)
        self.assertEqual(context['soft_tie_break'], 0)
        self.assertIn('Consideration unavailable', context['summary'])
        self.assertIn('retained season source', context['summary'])
        self.assertEqual(context['source_identity'], self.service.report(self.data)['semantic_identity'])

    def test_all_retained_sources_unavailable_keeps_read_only_pages_available(self):
        self.data.pop('season_transactions', None)
        path = self.publish([completed('unreadable')])
        path.write_bytes(path.read_bytes()[:-8])
        before = sha256(path.read_bytes()).hexdigest()
        for route in ('/league', '/teams/1', '/teams/2'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertIn('retained season source unavailable', response.text)
        self.assertEqual(self.service.report(self.data)['coverage']['state'], 'unavailable')
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), before)


class LeagueGMIntegritySourceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.LeagueObservationSourceTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data, self.service, self.cache = self.f.data, self.f.service, self.f.cache

    def test_corrupt_stream_matrix_preserves_independent_season_and_original_bytes(self):
        from src.core.history_context.season_cache import SeasonSourceUnavailable
        for kind, corrupt in (
            ('trailer', lambda value: value[:-8]),
            ('payload', lambda value: value[:len(value) // 2]),
            ('invalid', lambda value: b'not a gzip archive'),
        ):
            with self.subTest(kind=kind):
                self.f.publish([completed('valid')], season=2024)
                self.f.publish([completed('bad')])
                path = self.cache.path('league-a', 2025)
                path.write_bytes(corrupt(path.read_bytes()))
                before = sha256(path.read_bytes()).hexdigest()
                with self.assertRaises(SeasonSourceUnavailable):
                    self.cache.read('league-a', 2025)
                report = self.service.report(self.data)
                self.assertEqual(report['trade_count'], 1)
                self.assertEqual(report['coverage']['state'], 'partial')
                failed = next(row for row in report['coverage']['seasons'] if row['season'] == 2025)
                self.assertEqual(failed['source_state'], 'unavailable')
                self.assertEqual(len(failed['unavailable']), 19)
                self.assertFalse(failed['acquired'])
                self.assertFalse(failed['observed_empty'])
                self.assertEqual(sha256(path.read_bytes()).hexdigest(), before)

    def test_valid_empty_season_is_observed_zero_not_unreadable(self):
        self.f.publish([])
        self.assertIsNotNone(self.cache.read('league-a', 2025))
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 0)
        self.assertEqual(report['coverage']['state'], 'observed_zero')
        self.assertTrue(all(row['complete_acquisition'] for row in report['coverage']['seasons']))

    def test_all_archives_unavailable_cannot_manufacture_observed_zero(self):
        self.data.pop('season_transactions')
        self.f.publish([])
        path = self.cache.path('league-a', 2025)
        path.write_bytes(path.read_bytes()[:-8])
        report = self.service.report(self.data)
        self.assertEqual(report['coverage']['state'], 'unavailable')
        self.assertEqual(report['trade_count'], 0)
        self.assertIn('not an observed zero', str(report['limitations']))

    def test_failed_read_reuses_qualified_cache_and_recovers_on_actual_publication(self):
        self.f.publish([completed('one')])
        valid = self.service.report(self.data)
        path = self.cache.path('league-a', 2025)
        path.write_bytes(path.read_bytes()[:-8])
        with patch.object(self.cache, 'read', wraps=self.cache.read) as read:
            failed = self.service.report(self.data)
            self.assertNotEqual(valid['semantic_identity'], failed['semantic_identity'])
            for _ in range(5):
                self.assertEqual(self.service.report(self.data), failed)
            self.assertEqual(read.call_count, 1)
        self.f.publish([completed('one'), completed('two')])
        recovered = self.service.report(self.data)
        self.assertEqual(recovered['trade_count'], 2)
        self.assertEqual(recovered['coverage']['state'], 'observed')
        self.assertNotIn('retained source unavailable', str(recovered['limitations']))

    def test_unrelated_programming_error_is_not_hidden_as_unavailable_history(self):
        self.f.publish([completed()])
        with patch.object(self.cache, 'sections', side_effect=RuntimeError('programming control')):
            with self.assertRaisesRegex(RuntimeError, 'programming control'):
                self.service.report(self.data)

    def test_unreadable_archive_does_not_trigger_implicit_rebuild_or_provider_fetch(self):
        import asyncio
        from unittest.mock import AsyncMock
        from src.core.history_context.season_cache import SeasonSourceUnavailable
        self.f.publish([completed()])
        path = self.cache.path('league-a', 2025)
        path.write_bytes(path.read_bytes()[:-8])
        before = sha256(path.read_bytes()).hexdigest()
        provider = AsyncMock(return_value={})
        with self.assertRaises(SeasonSourceUnavailable):
            asyncio.run(self.cache.get_or_rebuild('league-a', 2025, provider))
        provider.assert_not_called()
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), before)

    def test_category_and_composition_matrix_uses_actual_publisher(self):
        pick = {'season': '2029', 'round': 2, 'roster_id': 3,
                'previous_owner_id': 1, 'owner_id': 2}
        faab = {'sender': 1, 'receiver': 2, 'amount': 12}
        cases = [
            ('omitted', without_consideration(), 'unavailable', {}),
            ('all_empty', {**without_consideration(), 'adds': {}, 'drops': {}, 'draft_picks': [], 'waiver_budget': []}, 'unavailable', {}),
            ('players', completed(), 'supported', {'player': 2}),
            ('picks', {**without_consideration(), 'draft_picks': [pick]}, 'supported', {'pick': 1}),
            ('faab', {**without_consideration(), 'waiver_budget': [faab]}, 'supported', {'faab': 1}),
            ('zero_faab', {**without_consideration(), 'waiver_budget': [{**faab, 'amount': 0}]}, 'supported', {'faab': 1}),
            ('player_pick', completed(draft_picks=[pick]), 'supported', {'player': 2, 'pick': 1}),
            ('player_faab', completed(waiver_budget=[faab]), 'supported', {'player': 2, 'faab': 1}),
            ('missing_sender', {**without_consideration(), 'adds': {'p': 2}}, 'unavailable', {}),
            ('missing_player_identity', {**without_consideration(), 'adds': {'': 2}, 'drops': {'': 1}}, 'unavailable', {}),
            ('partial_pick', completed(draft_picks=[{k: v for k, v in pick.items() if k != 'roster_id'}]), 'partial', {'player': 2}),
            ('malformed_players', completed(adds=False, draft_picks=[pick]), 'partial', {'pick': 1}),
            ('malformed_picks', completed(draft_picks=False, waiver_budget=[faab]), 'partial', {'player': 2, 'faab': 1}),
        ]
        for name, raw, state, incoming in cases:
            with self.subTest(name=name):
                self.f.publish([raw])
                report = self.service.report(self.data)
                self.assertEqual(report['trade_count'], 1)
                self.assertEqual(report[f'composition_{state}_trades'], 1)
                self.assertEqual(sum(report[f'composition_{s}_trades'] for s in ('supported', 'partial', 'unavailable')), 1)
                self.assertEqual(sum(report['teams'][rid]['franchise']['incoming'].get(kind, 0)
                                     for rid in ('1', '2') for kind in ('player', 'pick', 'faab')), sum(incoming.values()))
                if state == 'unavailable':
                    self.assertEqual(report['category_supported_trades'], {})
                    for row in report['teams'].values():
                        self.assertEqual(row['manager']['acquired_positions'], {})
                        self.assertEqual(row['franchise']['package_style'], {})
                    self.assertIn('Consideration unavailable', report['teams']['1']['summary'])
                if name == 'players':
                    from src.core.gm_behavioral_intelligence.diagnostics import supported_asset_count
                    self.assertEqual(supported_asset_count(report['teams']['1']['franchise'], 'incoming', 'pick'), 0)
                if name == 'malformed_picks':
                    self.assertEqual(report['category_supported_trades'].get('player'), 1)
                    self.assertEqual(report['category_supported_trades'].get('faab'), 1)
                    self.assertEqual(report['category_supported_trades'].get('pick', 0), 0)

    def test_composition_denominators_and_unsupported_manager_preference(self):
        self.f.publish([without_consideration(str(i)) for i in range(6)])
        report = self.service.report(self.data)
        manager = report['teams']['1']['manager']
        self.assertEqual(manager['trades'], 6)
        self.assertEqual(manager['composition_supported_trades'], 0)
        self.assertEqual(manager['composition_unavailable_trades'], 6)
        self.assertEqual(manager['category_supported_trades'], {})
        from src.core.gm_behavioral_intelligence.diagnostics import partner_context
        context = partner_context(report, 1, {'coverage': 'supported current week',
            'numeric_impact_state': 'supported', 'pre_optimal_points': 20,
            'post_optimal_points': 28, 'need_positions_received': ['WR']}, ['WR'])
        self.assertEqual(context['soft_tie_break'], 0)
        self.assertIn('does not establish a matching', context['summary'])
        self.f.publish([completed('known'), without_consideration('unknown')])
        mixed = self.service.report(self.data)
        self.assertEqual(mixed['trade_count'], 2)
        self.assertEqual(mixed['composition_supported_trades'], 1)
        self.assertEqual(mixed['composition_unavailable_trades'], 1)
        self.assertEqual(mixed['category_supported_trades'], {'player': 1, 'pick': 1, 'faab': 1})

    def test_all_participant_permutations_deduplicate_without_mutating_direction(self):
        for participants in ([1, 2], [1, 2, 3]):
            base = completed('same', roster_ids=participants,
                waiver_budget=[{'sender': 1, 'receiver': 2, 'amount': 12}])
            rows = [{**deepcopy(base), 'roster_ids': list(order)} for order in permutations(participants)]
            original = deepcopy(rows)
            self.f.publish(rows)
            report = self.service.report(self.data)
            self.assertEqual(report['trade_count'], 1)
            self.assertEqual(report['directed_faab_transfers'], 1)
            self.assertEqual(report['teams']['2']['franchise']['incoming']['faab'], 1)
            self.assertEqual(report['teams']['1']['manager']['trades'], 1)
            self.f.publish(list(reversed(rows)))
            repeated = self.service.report(self.data)
            self.assertEqual(repeated['semantic_identity'], report['semantic_identity'])
            self.assertEqual(rows, original)

    def test_repeated_source_pages_and_current_duplicates_are_one_identity(self):
        first = completed('current')
        self.data['transactions'] = [first]
        self.data['season_transactions']['1'] = [{**deepcopy(first), 'roster_ids': [2, 1]}]
        self.data['season_transactions']['2'] = [deepcopy(first)]
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 1)
        self.assertEqual(report['teams']['1']['franchise']['trades'], 1)

    def test_true_directed_conflicts_and_transaction_versions_remain_withheld(self):
        pick = {'season': '2029', 'round': 2, 'roster_id': 3, 'previous_owner_id': 1, 'owner_id': 2}
        base = completed('conflict', draft_picks=[pick], waiver_budget=[{'sender': 1, 'receiver': 2, 'amount': 12}])
        changes = [
            {'adds': {'p': 1, 'q': 2}, 'drops': {'p': 2, 'q': 1}},
            {'draft_picks': [{**pick, 'roster_id': 2}]},
            {'draft_picks': [{**pick, 'previous_owner_id': 2, 'owner_id': 1}]},
            {'waiver_budget': [{'sender': 1, 'receiver': 2, 'amount': 13}]},
            {'waiver_budget': [{'sender': 2, 'receiver': 1, 'amount': 12}]},
            {'roster_ids': [1, 3]}, {'roster_ids': None}, {'status': 'pending'},
            {'status_updated': base['status_updated'] + 1},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.f.publish([base, {**deepcopy(base), **change}])
                report = self.service.report(self.data)
                self.assertEqual(report['trade_count'], 0)
                self.assertIn('conflicting transaction identities withheld', str(report['limitations']))

    def test_different_source_leagues_do_not_share_duplicate_identity(self):
        self.f.publish([completed('shared-id')], season=2024, source='old-a')
        self.f.publish([completed('shared-id', roster_ids=[2, 1])], source='old-b')
        report = self.service.report(self.data)
        self.assertEqual(report['trade_count'], 2)
        self.assertEqual({r['source_league_id'] for r in report['teams']['1']['franchise']['references']}, {'old-a', 'old-b'})

    def test_day_arkham_corruption_and_recovery_are_isolated(self):
        day, arkham = '1313066632158924800', '1319750579458686976'
        self.f.publish([completed('same-id')], namespace=day)
        self.f.publish([completed('same-id'), completed('second')], namespace=arkham)
        a, b = fixtures.observed_data(day), fixtures.observed_data(arkham)
        self.assertEqual(self.service.report(a)['trade_count'], 1)
        path = self.cache.path(day, 2025)
        path.write_bytes(path.read_bytes()[:-8])
        self.assertEqual(self.service.report(a)['trade_count'], 0)
        self.assertEqual(self.service.report(b)['trade_count'], 2)
        self.f.publish([completed('recovered')], namespace=day)
        self.assertEqual(self.service.report(a)['trade_count'], 1)
        self.assertEqual(self.service.report(b)['trade_count'], 2)
