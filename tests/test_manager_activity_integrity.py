"""Current-manager evidence and executed-versus-attempted activity contracts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.front_office_intelligence.engine import _activity
from src.core.front_office_evidence import assemble_front_office_evidence
from src.core.gm_behavioral_intelligence import GMBehavioralIntelligenceService
from src.core.gm_behavioral_intelligence.diagnostics import LeagueGMObservations
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.trade_intelligence.evidence_context import build_trade_evidence_context
from tests.test_gm_behavioral_intelligence_v1126 import trade
from tests.test_league_gm_diagnostics import observed_data


def manager_products(data, owner='now-b', outgoing_kind='player'):
    league = data['league']['league_id']
    rows = tuple(trade(str(i), owner=owner, incoming=('x',), outgoing=('y',),
                       incoming_types=('player',), outgoing_types=(outgoing_kind,)) for i in range(12))
    summary = assemble_front_office_evidence(league_id=league,
        franchise_id=f'{league}:franchise:2', gm_id=f'{league}:gm:{owner}', trades=rows)
    data['front_office_evidence'] = {'2': summary.contract()}
    data['gm_behavioral_intelligence'] = {'2': GMBehavioralIntelligenceService().build_profile(
        evidence=summary, trades=rows).contract()}


def waiver(identity, status, **changes):
    return {'transaction_id': identity, 'type': 'waiver', 'status': status,
        'roster_ids': [1], 'adds': {'p': 1}, 'drops': {'q': 1},
        'settings': {'waiver_bid': 0}, 'created': 1760000000000,
        'status_updated': 1760000001000, **changes}


class ManagerActivityIntegrityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cache = SleeperSeasonCache(Path(folder.name))
        self.observations = LeagueGMObservations(self.cache)
        self.patch = patch('src.core.gm_behavioral_intelligence.diagnostics.league_gm_observations', self.observations)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.data = observed_data()
        self.data['market_trend_summaries'] = {}

    def test_previous_owner_cannot_enter_successor_trade_context(self):
        manager_products(self.data, 'previous-owner')
        context = build_trade_evidence_context(self.data)
        self.assertEqual(context.behavior_by_roster, {})
        self.assertEqual(context.front_office_by_roster, {})

    def test_completed_claims_are_not_failed_attempts(self):
        self.data['transactions'] = [waiver('one', 'complete'), waiver('two', 'failed'), waiver('three', 'failed')]
        activity = _activity(self.data, 1, 0)
        self.assertEqual(activity.waivers, 1)
        self.assertEqual(activity.adds, 1)
        self.assertEqual(activity.drops, 1)
        events = next(row for row in activity.evidence if row.factor in ('Roster transactions', 'Completed non-trade transactions'))
        self.assertEqual(events.observed_value, '1')

    def test_completed_commissioner_news_uses_shared_admission(self):
        from services.commissioner import _completed_transactions
        one = waiver('one', 'complete')
        self.data['transactions'] = [one, deepcopy(one), waiver('two', 'failed'),
            waiver('three', 'pending'), waiver('four', 'cancelled'), waiver('five', 'unknown')]
        self.assertEqual([row['id'] for row in _completed_transactions(self.data)], ['one'])

    def test_malformed_publication_metadata_is_unavailable(self):
        manager_products(self.data)
        self.seal()
        for bad in ([], 'unsupported', {'method': 'current-manager-publication-1', 'bindings': []}):
            with self.subTest(bad=bad):
                self.data['_manager_evidence_publication'] = bad
                self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})

    def seal(self):
        from tests.manager_evidence_fixtures import publish
        publish(self.data)

    def test_franchise_history_does_not_raise_current_manager_profile_confidence(self):
        from src.core.intelligence import build_league_model
        from tests.test_league_gm_diagnostics import completed
        self.data['transactions'] = []
        baseline = build_league_model(self.data)
        self.data['transactions'] = [completed('franchise-' + str(i)) for i in range(5)]
        observed = build_league_model(self.data)
        self.assertEqual(observed.reports[1].activity.trades, 5)
        self.assertEqual(observed.reports[1].confidence, baseline.reports[1].confidence)
        self.assertEqual(observed.compatibility(1, 2).bilateral_trades, 5)
        self.assertEqual(observed.compatibility(1, 2).score, baseline.compatibility(1, 2).score)
        self.assertNotIn('Established Trade Channel', observed.compatibility(1, 2).best_trade_themes)

    def test_supported_current_manager_is_admitted_with_exact_provenance(self):
        manager_products(self.data)
        self.seal()
        context = build_trade_evidence_context(self.data)
        self.assertEqual(context.behavior_by_roster['2']['transaction_count'], 12)
        self.assertEqual(context.behavior_by_roster['2']['source_evidence_identity'],
                         context.front_office_by_roster['2']['semantic_identity'])

    def test_twelve_prior_owner_observations_are_removed_after_owner_transition(self):
        self.data['teams'][1]['owner_id'] = 'previous-owner'
        manager_products(self.data, 'previous-owner')
        self.seal()
        self.assertIn('2', build_trade_evidence_context(self.data).behavior_by_roster)
        self.data['teams'][1]['owner_id'] = 'now-b'
        context = build_trade_evidence_context(self.data)
        self.assertEqual(context.behavior_by_roster, {})
        self.assertEqual(context.front_office_by_roster, {})

    def test_missing_conflicting_and_wrong_manager_or_franchise_fail_closed(self):
        manager_products(self.data)
        self.seal()
        original = deepcopy(self.data)
        cases = [('gm_id', 'league-a:gm:wrong'), ('gm_id', None),
                 ('franchise_id', 'league-a:franchise:1'), ('franchise_id', None),
                 ('league_id', 'foreign'), ('method_version', 'unsupported'),
                 ('source_evidence_identity', 'wrong-generation'), ('semantic_identity', 'invented')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.data = deepcopy(original)
                self.data['gm_behavioral_intelligence']['2'][field] = value
                self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})
        for owner in (None, ''):
            self.data = deepcopy(original)
            self.data['teams'][1]['owner_id'] = owner
            self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})
        self.data = deepcopy(original)
        self.data['teams'][1]['user_id'] = 'different-owner'
        self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})
        self.data = deepcopy(original)
        self.data['teams'].append(deepcopy(self.data['teams'][1]))
        self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})

    def test_source_transition_and_missing_publication_cannot_revive_history(self):
        manager_products(self.data)
        self.data['history_generation'] = 'league-a-history'
        self.seal()
        self.assertIn('2', build_trade_evidence_context(self.data).behavior_by_roster)
        self.data['history_generation'] = 'source-b'
        self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})
        self.data['history_generation'] = 'league-a-history'
        self.data.pop('_manager_evidence_publication')
        self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})

    def test_publication_uses_preparation_source_not_new_generation(self):
        from src.core.intelligence.manager_evidence import begin_preparation, end_preparation, publish_rows
        manager_products(self.data)
        token = begin_preparation(self.data)
        try:
            self.data['history_generation'] = 'new-source'
            publish_rows(self.data, 'front_office_evidence', self.data['front_office_evidence'])
            publish_rows(self.data, 'gm_behavioral_intelligence', self.data['gm_behavioral_intelligence'])
        finally:
            end_preparation(token)
        self.assertNotIn('_manager_evidence_publication', self.data)
        self.assertEqual(build_trade_evidence_context(self.data).behavior_by_roster, {})

    def test_five_prior_owner_trades_remain_exact_franchise_history(self):
        from tests.test_league_gm_diagnostics import completed
        facts = {'league': {'league_id': 'past', 'season': '2025', 'status': 'complete'},
            'rosters': [{'roster_id': 1, 'owner_id': 'old-a'}, {'roster_id': 2, 'owner_id': 'old-b'}],
            'transactions': {str(i): [completed(str(j), draft_picks=[{'season': '2028', 'round': 1,
                'roster_id': 7, 'previous_owner_id': 1, 'owner_id': 2}]) for j in range(5)] if i == 1 else [] for i in range(19)}}
        self.cache.write(self.cache.normalize('league-a', 2025, facts))
        report = self.observations.report(self.data)
        self.assertEqual(report['teams']['2']['franchise']['trades'], 5)
        self.assertEqual(report['teams']['2']['manager']['trades'], 0)
        self.assertEqual(report['teams']['2']['franchise']['incoming']['pick'], 5)

    def test_duplicates_attempts_failed_drops_unknown_and_zero_faab_are_separate(self):
        rows = [waiver('one', 'complete'), waiver('two', 'failed'), waiver('three', 'failed'),
            waiver('four', 'pending'), waiver('five', 'cancelled'), waiver('six', None),
            waiver('drop-failed', 'failed', type='drop'), waiver('drop-done', 'complete', type='drop', adds={})]
        self.data['transactions'] = rows + [deepcopy(rows[0])]
        self.data['season_transactions']['1'] = deepcopy(rows)
        report = self.observations.report(self.data)
        counts = report['activity']['teams']['1']['franchise']
        self.assertEqual(counts['completed_waivers'], 1)
        self.assertEqual(counts['completed_adds'], 1)
        self.assertEqual(counts['completed_drops'], 2)
        self.assertEqual(counts['waiver_attempts'], {'failed': 2, 'pending': 1, 'cancelled': 1, 'unknown': 1})
        self.assertEqual(counts['faab_spent'], 0)
        self.assertEqual(counts['faab_priced_claims'], 1)
        self.assertEqual(counts['other_attempts']['failed'], 1)
        self.assertEqual(report['activity']['teams']['1']['manager']['completed_waivers'], 0)

    def test_conflicting_ids_missing_ids_and_future_events_do_not_complete_decisions(self):
        self.data['transactions'] = [waiver('conflict', 'complete'), waiver('conflict', 'failed'),
            waiver('', 'complete'), waiver('future', 'complete', status_updated='2100-01-01T00:00:00Z')]
        counts = self.observations.report(self.data)['activity']
        self.assertEqual(counts['total']['completed_waivers'], 0)
        self.assertEqual(counts['conflicting_identities'], 1)
        self.assertEqual(counts['unqualified_records'], 1)
        self.assertEqual(counts['total']['waiver_attempts']['unknown'], 1)

    def test_missing_and_invalid_faab_do_not_become_zero(self):
        for bid in (None, True, -1, float('inf'), 'bad'):
            with self.subTest(bid=bid):
                self.data['transactions'] = [waiver('claim', 'complete', settings={'waiver_bid': bid})]
                counts = self.observations.report(self.data)['activity']['total']
                self.assertIsNone(counts['faab_spent'])
                self.assertEqual(counts['faab_unavailable_claims'], 1)

    def test_qualified_reads_do_not_call_archive_factories_providers_or_solver(self):
        from src.core.intelligence.league_scope import scoped_evidence
        manager_products(self.data)
        self.seal()
        before = deepcopy(self.data)
        with patch.object(self.cache, 'sections', side_effect=AssertionError('archive decoding')), \
             patch('src.core.history_context.store.CanonicalHistoryStore.records', side_effect=AssertionError('history scan')), \
             patch('src.core.fois.service.FOISService.generate', side_effect=AssertionError('FOIS')):
            for _ in range(10):
                self.assertIn('2', scoped_evidence(self.data, 'gm_behavioral_intelligence').rows)
        self.assertEqual(self.data, before)

    def test_current_quality_precedes_historical_confidence_in_ordering(self):
        from services.trade_search_policy import rank_key
        near = {'evaluation': {'recommendation': 'WORTH PURSUING', 'values': {'ratio': .99},
            'dimensions': {'confidence': {'assessment': 'MEDIUM'},
                'historical_counterparty_evidence': {'score': 0}}, 'provenance': {'evaluation_id': 'near'}}}
        history = deepcopy(near)
        history['evaluation']['values']['ratio'] = .85
        history['evaluation']['dimensions']['confidence']['assessment'] = 'HIGH'
        history['evaluation']['dimensions']['historical_counterparty_evidence']['score'] = 4
        self.assertLess(rank_key(near), rank_key(history))

    def test_exact_directed_faab_including_zero_is_preserved(self):
        from tests.test_league_gm_diagnostics import completed
        self.data['transactions'] = [completed('faab', waiver_budget=[{'sender': 1, 'receiver': 2, 'amount': 0}])]
        report = self.observations.report(self.data)
        self.assertEqual(report['directed_faab_transfers'], 1)
        first = report['activity']['teams']['1']['franchise']
        second = report['activity']['teams']['2']['franchise']
        self.assertEqual(first['faab_sent'], 0)
        self.assertIsNone(first['faab_received'])
        self.assertEqual(second['faab_received'], 0)
        self.assertIsNone(second['faab_sent'])


class ManagerActivityHTTPTests(unittest.TestCase):
    def setUp(self):
        from tests.test_league_gm_diagnostics import LeagueDiagnosticHTTPTests
        self.fixture = LeagueDiagnosticHTTPTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.data, self.client = self.fixture.data, self.fixture.client
        self.data['teams'][1]['owner_id'] = 'now-b'

    def publish(self, owner='now-b'):
        from tests.manager_evidence_fixtures import publish
        manager_products(self.data, owner, outgoing_kind="pick")
        publish(self.data)

    def evaluate(self):
        result = self.fixture.owner.evaluate()
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()['evaluation']

    def test_real_http_twelve_observations_cannot_influence_successor_confidence(self):
        self.publish()
        admitted = self.evaluate()
        self.assertEqual(admitted['dimensions']['historical_counterparty_evidence']['behavioral_sample_count'], 12)
        self.assertEqual(admitted['dimensions']['confidence']['assessment'], 'HIGH')
        self.data['teams'][1]['owner_id'] = 'successor'
        rejected = self.evaluate()
        self.assertEqual(rejected['dimensions']['historical_counterparty_evidence']['behavioral_sample_count'], 0)
        self.assertEqual(rejected['dimensions']['confidence']['assessment'], 'MEDIUM')
        self.assertEqual(rejected['recommendation'], admitted['recommendation'])
        self.assertEqual(rejected['lineup_impact'], admitted['lineup_impact'])
        self.assertEqual(rejected['market_evidence'], admitted['market_evidence'])
        self.assertTrue(rejected['generated_trade_eligible'])
        self.assertIn('Compatible current-manager history is unavailable', rejected['dimensions']['league_partner_context']['summary'])

    def test_owner_and_source_transition_during_actual_evaluation_are_retryable(self):
        from src.core.intelligence import roster_diagnostics
        original = roster_diagnostics.package_diagnostics
        for change in ('owner', 'source'):
            with self.subTest(change=change):
                def transition(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if change == 'owner':
                        self.data['teams'][1]['owner_id'] = 'next-owner'
                    else:
                        self.data['history_generation'] = 'next-source'
                    return result
                with patch.object(roster_diagnostics, 'package_diagnostics', side_effect=transition):
                    response = self.fixture.owner.evaluate()
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()['detail']['code'], 'canonical_evidence_changed')

    def test_transition_at_final_response_publication_is_rejected(self):
        from routes.trades import PersonalTradeResponse
        original = PersonalTradeResponse.__call__
        async def interleave(response, scope, receive, send):
            self.data['history_generation'] = 'new-source-before-headers'
            return await original(response, scope, receive, send)
        with patch.object(PersonalTradeResponse, '__call__', interleave):
            response = self.fixture.owner.evaluate()
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()['detail']['code'], 'canonical_evidence_changed')

    def test_actual_league_and_hq_html_separate_completed_and_attempted_waivers(self):
        self.data['transactions'] = [waiver('claim', 'complete'), waiver('failure1', 'failed'), waiver('failure2', 'failed')]
        for path in ('/league', '/teams/1', '/teams/2'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('completed waiver claims', response.text)
                self.assertIn('unknown-status waiver attempts', response.text)
        report = self.fixture.service.report(self.data)['activity']['teams']['1']['franchise']
        self.assertEqual(report['completed_waivers'], 1)
        self.assertEqual(report['waiver_attempts']['failed'], 2)

    def test_partner_explanation_orders_current_benefit_cost_history(self):
        self.publish()
        evaluation = self.evaluate()
        context = evaluation['dimensions']['league_partner_context']
        self.assertLess(context['summary'].index(context['current_benefit']), context['summary'].index('Main cost:'))
        self.assertLess(context['summary'].index('Main cost:'), context['summary'].index('12 supported current-manager'))
        self.assertIn('not', context['manager_observations'])
        self.assertIn('observation', context['manager_observations'])
        self.assertEqual(context['admitted_manager_sample'], 12)
        self.assertIsNone(evaluation['dimensions']['counterparty_plausibility']['acceptance_probability'])

    def test_actual_league_api_does_not_export_unqualified_manager_products(self):
        from routes.api import create_api_router
        from unittest.mock import AsyncMock
        self.client.app.include_router(create_api_router(ensure_fresh=AsyncMock(),
            require_data=lambda: self.data, sync_sleeper=AsyncMock(), state={'data': self.data},
            league_id=self.data['league']['league_id']))
        self.publish()
        supported = self.client.get('/api/league')
        self.assertEqual(supported.status_code, 200)
        self.assertEqual(supported.json()['gm_behavioral_intelligence']['2']['transaction_count'], 12)
        self.assertNotIn('_manager_evidence_publication', supported.json())
        self.data['teams'][1]['owner_id'] = 'successor'
        rejected = self.client.get('/api/league').json()
        self.assertEqual(rejected['gm_behavioral_intelligence'], {})
        self.assertEqual(rejected['front_office_evidence'], {})
        self.assertEqual(rejected['manager_evidence_qualification']['rejected_products'], 2)

    def test_custom_keeps_neutral_partner_evidence_and_existing_guards(self):
        # Real Custom workflow controls assert partner strategy/package/Market
        # identity across personally different prices; no second solver.
        from tests.test_personal_trade_workflows import PersonalTradeWorkflowTests
        control = PersonalTradeWorkflowTests()
        control.setUp()
        try:
            control.test_personal_upgrade_does_not_price_the_counterpartys_return_or_veto_eligibility()
            control.test_neutral_counterparty_loss_still_blocks_personally_plausible_prices()
        finally:
            control.doCleanups()
