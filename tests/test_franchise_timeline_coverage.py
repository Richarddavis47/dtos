"""Retained Day/Arkham captures plus explicit disposable season variants."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from services.franchise_timeline import franchise_timeline
from src.core.historical_memory.graph import HistoricalAssetGraph
from tests import test_historical_tracker_phase2 as fixtures


class FranchiseTimelineCoverageTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.TrackerPhase2Tests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.client = TestClient(self.f.app)
        self.addCleanup(self.client.close)

    def page(self, roster='1'):
        response = self.client.get('/history/team/' + self.f.data['league']['league_id'] + ':franchise:' + roster)
        self.assertEqual(response.status_code, 200, response.text[:300])
        return response.text

    def graph(self):
        return HistoricalAssetGraph(self.f.fixture.store, self.f.data['league']['league_id'], self.f.data)

    def past(self, transactions=None, *, status='complete'):
        facts = deepcopy(self.f.fixture.sources[0])
        facts['league'].update(league_id='9000000000000002024', season='2024', previous_league_id=None, status=status)
        facts['transactions'] = {str(w): [] for w in range(19)} if transactions is None else transactions
        facts['drafts'], facts['draft_picks'] = [], []
        current = deepcopy(self.f.fixture.sources[0])
        current['league']['previous_league_id'] = facts['league']['league_id']
        self.f.data['league']['previous_league_id'] = facts['league']['league_id']
        self.f.publish(current)
        self.f.publish(facts, season=2024)
        return facts

    def trade(self, tid='controlled', status='complete'):
        return {'transaction_id': tid, 'type': 'trade', 'status': status, 'roster_ids': [1, 2],
                'adds': {'fixture-player': 1}, 'drops': {'fixture-player': 2}, 'draft_picks': [],
                'created': 1727800000000, 'status_updated': 1727800000001}

    def test_partial_day_and_arkham_retained_events_reach_rendered_page(self):
        for league, roster in ((fixtures.DAY, '3'), (fixtures.ARK, '1')):
            with self.subTest(league=league):
                self.f.data = self.f.fixture.data[league]
                view = franchise_timeline(self.graph(), roster)
                html = self.page(roster)
                self.assertIn('Partial transaction coverage', html)
                self.assertIn('Not retrieved: weeks', html)
                self.assertGreater(view['total'], 0)
                self.assertIn('Draft Selection', html)
                self.assertIn('RETAINED / NOT REVALIDATED', html)
                self.assertNotIn('No completed transaction activity in the fully acquired', html)

    def test_complete_closed_season_can_support_no_completed_transactions(self):
        self.past()
        view = franchise_timeline(self.graph(), '1')
        s = next(s for s in view['seasons'] if s['season'] == 2024)
        self.assertEqual(s['state'], 'complete')
        self.assertTrue(s['no_activity_supported'])
        html = self.page()
        self.assertIn('2024 · Complete transaction coverage', html)
        self.assertIn('19 of 19 supported source weeks retrieved', html)
        self.assertIn('No completed transaction activity in the fully acquired supported source periods', html)

    def test_current_or_old_calendar_age_does_not_imply_complete(self):
        self.past(status='in_season')
        self.assertEqual(next(s for s in franchise_timeline(self.graph(), '1')['seasons'] if s['season'] == 2024)['state'], 'partial')
        api = self.client.get('/api/history/franchises/1')
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.json()['season_status']['2024'], 'partial')

    def test_discovered_uncached_season_is_unknown_not_empty(self):
        with patch.object(self.f.fixture.store, 'season_chain', return_value={'seasons': [
                {'season': 2022, 'league_id': '9000000000000002022', 'cache_status': 'unavailable'}]}):
            html = self.page()
            self.assertIn('2022 · Unknown transaction coverage', html)
            self.assertIn('missing history is not no activity', html)

    def test_checkpoint_retains_events_without_claiming_acquired_weeks(self):
        self.past({'0': [self.trade()]})
        store = self.f.fixture.store
        store.preserve_reader_checkpoint(fixtures.DAY, 2024, current_season=2026)
        self.f.fixture.cache.delete(fixtures.DAY, 2024)
        view = franchise_timeline(self.graph(), '1')
        season = next(s for s in view['seasons'] if s['season'] == 2024)
        self.assertEqual(season['state'], 'partial')
        self.assertEqual(season['acquired'], [])
        self.assertFalse(season['no_activity_supported'])
        self.assertTrue(any(r['id'] == 'controlled' for r in view['events']))
        html = self.page()
        self.assertIn('2024 · Partial transaction coverage', html)
        self.assertNotIn('No completed transaction activity in the fully acquired', html)

    def test_missing_and_malformed_source_periods_have_specific_reasons(self):
        self.past({'0': [], '1': None, '2': 'malformed'})
        html = self.page()
        self.assertIn('Source unavailable: weeks 1', html)
        self.assertIn('Source data could not be read: weeks 2', html)
        self.assertIn('2024 · Partial transaction coverage', html)

    def test_failed_rejected_pending_and_unknown_are_not_completed_movements(self):
        facts = self.past({'0': [self.trade('attempt-' + state, state) for state in ('pending', 'failed', 'rejected', 'cancelled', 'unknown')]})
        view = franchise_timeline(self.graph(), '1')
        self.assertFalse([r for r in view['events'] if r['id'].startswith('attempt-')])
        self.assertEqual(len([r for r in view['attempts'] if r['id'].startswith('attempt-')]), 5)
        self.assertTrue(all(not r['assets'] for r in view['attempts']))
        html = self.page()
        self.assertIn('Not completed or not attributable', html)
        self.assertIn('no asset movement is inferred', html)
        graph = self.graph()
        self.assertTrue(all(r['trade_dossier_url'] is None for r in graph.transaction_archive() if r['season'] == 2024))
        self.assertEqual(facts['transactions']['0'][0]['status'], 'pending')

    def test_duplicate_transactions_are_shown_once(self):
        row = self.trade()
        self.past({'0': [row, deepcopy(row)], '1': [deepcopy(row)]})
        events = [r for r in franchise_timeline(self.graph(), '1')['events'] if r['id'] == 'controlled']
        self.assertEqual(len(events), 1)
        self.assertEqual(self.page().count('source record controlled'), 0)  # IDs appear only in the explicit source disclosure.

    def test_conflicting_retained_identities_withhold_movements(self):
        a, b = self.trade(), self.trade()
        b['type'] = 'waiver'
        self.past({'0': [a, b]})
        view = franchise_timeline(self.graph(), '1')
        self.assertFalse([r for r in view['events'] if r['id'] == 'controlled'])
        self.assertTrue(any('Conflicting retained' in r['reason'] for r in view['attempts']))

    def test_pick_original_franchise_is_not_its_owner_or_a_participant(self):
        row = self.trade('third-origin')
        row['draft_picks'] = [{'season': '2029', 'round': 1, 'roster_id': 3, 'previous_owner_id': 2, 'owner_id': 1}]
        self.past({'0': [row]})
        view = franchise_timeline(self.graph(), '1')
        event = next(r for r in view['events'] if r['id'] == 'third-origin')
        self.assertEqual(next(a['id'] for a in event['assets'] if a['kind'] == 'pick'), 'PICK-2029-R1-ORIG3')
        self.assertIn('2029 round 1 · original franchise:', self.page())
        self.assertFalse([r for r in franchise_timeline(self.graph(), '3')['events'] if r['id'] == 'third-origin'])

    def test_missing_traded_pick_year_never_uses_transaction_season(self):
        row = self.trade('pick-year-unknown')
        row['draft_picks'] = [{'round': 1, 'roster_id': 3, 'previous_owner_id': 2, 'owner_id': 1}]
        facts = self.past()
        facts['transactions']['0'] = [row]
        self.f.publish(facts, season=2024)
        view = franchise_timeline(self.graph(), '1')
        event = next(r for r in view['events'] if r['id'] == 'pick-year-unknown')
        self.assertTrue(event['completed'])
        self.assertIsNone(next(a['id'] for a in event['assets'] if a['kind'] == 'pick'))
        self.assertIsNone(event['detail_url'])
        self.assertTrue(any(a['kind'] == 'player' for a in event['assets']))
        season = next(s for s in view['seasons'] if s['season'] == 2024)
        self.assertEqual(season['state'], 'partial')
        html = self.page()
        self.assertIn('Year unknown round 1', html)
        self.assertIn('Exact draft-pick identity is incomplete', html)
        self.assertNotIn('PICK-2024-R1-ORIG3', html)
        archive = next(r for r in self.graph().transaction_archive() if r['sleeper_transaction_id'] == 'pick-year-unknown')
        self.assertIsNone(archive['trade_dossier_url'])
        ledger = self.client.get('/transactions?scope=all_history&season=2024').text
        self.assertIn('Exact draft-pick identity incomplete', ledger)
        self.assertNotIn('/trades/history/pick-year-unknown', ledger)

    def test_draft_selection_preserves_original_distinct_from_selecting_roster(self):
        facts = self.past()
        facts['drafts'] = [{'draft_id': 'fixture-draft', 'league_id': facts['league']['league_id'], 'type': 'linear', 'status': 'complete'}]
        facts['draft_picks'] = [{'draft_id': 'fixture-draft', 'pick_no': 1, 'round': 2, 'roster_id': 1, 'original_roster_id': 3, 'player_id': 'fixture-selected'}]
        self.f.publish(facts, season=2024)
        event = next(r for r in franchise_timeline(self.graph(), '1')['events'] if r['season'] == 2024)
        self.assertEqual(event['assets'][0]['id'], 'PICK-2024-R2-ORIG3')
        self.assertIsNone(event['occurred_at'])
        self.assertIn('Exact selection time is not recorded', self.page())
        del facts['draft_picks'][0]['original_roster_id']
        facts['drafts'][0]['type'] = 'auction'
        self.f.publish(facts, season=2024)
        event = next(r for r in franchise_timeline(self.graph(), '1')['events'] if r['season'] == 2024)
        self.assertIsNone(event['assets'][0]['id'])
        self.assertIn('Original franchise: not established', self.page())

    def test_ownership_changes_are_season_observations_not_current_manager_credit(self):
        facts = self.past({'0': [self.trade()]})
        facts['rosters'][0]['owner_id'] = 'earlier-manager'
        facts['users'].append({'user_id': 'earlier-manager', 'display_name': 'Earlier manager', 'metadata': {'team_name': 'Earlier franchise'}})
        self.f.publish(facts, season=2024)
        html = self.page()
        self.assertIn('Observed manager changed between seasons 2024 and 2026', html)
        self.assertIn('exact takeover time is unavailable', html)
        self.assertIn('not verified trade-time actors', html)
        self.assertIn('Earlier franchise', html)

    def test_foreign_league_context_and_invalid_roster_never_leak(self):
        response = self.client.get('/history/team/' + fixtures.ARK + ':franchise:1')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/history/team/' + fixtures.DAY + ':franchise:invalid').status_code, 404)
        html = self.page()
        self.assertNotIn(fixtures.ARK + ':franchise:', html)

    def test_source_change_withholds_complete_coverage_and_empty_conclusion(self):
        self.past()
        graph = self.graph()
        with patch.object(self.f.fixture.store, 'dataset_version', side_effect=['before', 'after']):
            view = franchise_timeline(graph, '1')
        self.assertFalse(view['stable_source'])
        self.assertTrue(all(s['state'] == 'unknown' and not s['no_activity_supported'] for s in view['seasons']))

    def test_ordinary_reads_do_not_build_asset_graph_call_provider_or_regrade(self):
        graph = self.graph()
        franchise_timeline(graph, '1')
        baseline = {str(p): p.read_bytes() for p in Path(self.f.fixture.temp.name).rglob('*.json')}
        with patch.object(graph, 'prepare_indexes', side_effect=AssertionError('no full graph')), \
             patch.object(graph, 'events', side_effect=AssertionError('no trade tree')), \
             patch('services.sleeper.sleeper_get', side_effect=AssertionError('no providers')), \
             patch.object(self.f.fixture.store, '_record_page', wraps=self.f.fixture.store._record_page) as reads:
            franchise_timeline(graph, '1')
            self.assertFalse(any(c.args[1] is None for c in reads.call_args_list))
        self.assertEqual(baseline, {str(p): p.read_bytes() for p in Path(self.f.fixture.temp.name).rglob('*.json')})

    def test_current_activity_list_is_not_full_season_acquisition(self):
        self.assertNotEqual(next(s for s in franchise_timeline(self.graph(), '1')['seasons'] if s['season'] == 2026)['state'], 'complete')

    def test_unparsed_or_unknown_records_cannot_establish_no_activity(self):
        for row in ({'type': 'trade', 'status': 'complete', 'roster_ids': [1, 2]}, self.trade(status='unknown')):
            with self.subTest(row=row):
                facts = self.past()
                facts['transactions']['0'] = [row]
                self.f.publish(facts, season=2024)
                season = next(s for s in franchise_timeline(self.graph(), '1')['seasons'] if s['season'] == 2024)
                self.assertEqual(season['state'], 'partial')
                self.assertFalse(season['no_activity_supported'])
                self.assertIn('Retained gaps:', self.page())

    def test_malformed_consideration_does_not_crash_or_become_a_movement(self):
        row = self.trade()
        row['draft_picks'] = [None]
        self.past({'0': [row]})
        view = franchise_timeline(self.graph(), '1')
        self.assertFalse([r for r in view['events'] if r['id'] == 'controlled'])
        self.assertTrue(any('Malformed source consideration' in r['reason'] for r in view['attempts']))
        self.assertIn('Malformed source consideration', self.page())
        response = self.client.get('/transactions?scope=all_history&season=2024&team=1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Consideration unavailable or malformed', response.text)
        self.assertNotIn('/trades/history/controlled', response.text)

    def test_missing_historical_identity_does_not_hide_supported_transactions(self):
        facts = self.past({'0': [self.trade()]})
        facts['users'] = None
        self.f.publish(facts, season=2024)
        view = franchise_timeline(self.graph(), '1')
        self.assertTrue(any(r['id'] == 'controlled' for r in view['events']))
        season = next(s for s in view['seasons'] if s['season'] == 2024)
        self.assertFalse(season['identity_observed'])
        self.assertEqual(season['state'], 'partial')
        self.assertIn('Franchise identity for this season is not established', self.page())

    def test_prepared_current_buckets_are_admitted_but_activity_lists_are_not(self):
        self.f.fixture.cache.delete(fixtures.DAY, 2026)
        self.f.data['league']['status'] = 'complete'
        self.f.data['season_transactions'] = {str(w): [] for w in range(19)}
        self.f.fixture.store.update_current(fixtures.DAY, self.f.data)
        period = next(s for s in franchise_timeline(self.graph(), '1')['seasons'] if s['season'] == 2026)
        self.assertEqual(period['state'], 'complete')
        self.assertTrue(period['no_activity_supported'])
        self.f.data['season_transactions'] = {}
        self.f.data['transactions'] = []
        self.f.fixture.store.update_current(fixtures.DAY, self.f.data)
        period = next(s for s in franchise_timeline(self.graph(), '1')['seasons'] if s['season'] == 2026)
        self.assertEqual(period['state'], 'unknown')
        self.assertFalse(period['no_activity_supported'])

    def test_wrong_declared_source_season_is_unknown_without_hiding_other_seasons(self):
        facts = self.past({'0': [self.trade()]})
        facts['league']['season'] = '2025'
        self.f.publish(facts, season=2024)
        view = franchise_timeline(self.graph(), '1')
        self.assertEqual(next(s for s in view['seasons'] if s['season'] == 2024)['state'], 'unknown')
        self.assertFalse([r for r in view['events'] if r['season'] == 2024])
        self.assertTrue(any(r['season'] == 2026 for r in view['events']))
        self.assertIn('source league-season metadata is incompatible', self.page())

    def test_completed_waiver_add_drop_and_zero_faab_transfer_remain_factual(self):
        row = self.trade('completed-waiver')
        row.update(type='waiver', roster_ids=[1], adds={'fixture-added': 1}, drops={'fixture-dropped': 1})
        self.past({'0': [row]})
        events = franchise_timeline(self.graph(), '1')['events']
        waiver = next(r for r in events if r['id'] == 'completed-waiver')
        self.assertEqual({a['id'] for a in waiver['assets']}, {'fixture-added', 'fixture-dropped'})
        self.assertIn('Waiver', self.page())
        row = self.trade('zero-faab')
        row['waiver_budget'] = [{'sender': 1, 'receiver': 2, 'amount': 0}]
        self.past({'0': [row]})
        self.assertIn('0 FAAB', self.page())

    def test_missing_continuation_keeps_completed_source_facts_without_attribution(self):
        self.past({'0': [self.trade()]})
        current = deepcopy(self.f.fixture.sources[0])
        current['league']['previous_league_id'] = 'missing-intermediate-season'
        self.f.data['league']['previous_league_id'] = 'missing-intermediate-season'
        self.f.publish(current)
        view = franchise_timeline(self.graph(), '1')
        event = next(r for r in view['events'] if r['id'] == 'controlled')
        self.assertTrue(event['completed'])
        self.assertTrue(event['assets'])
        self.assertEqual(event['attribution'], 'franchise continuity unconfirmed')
        self.assertIn('Source roster observation · 2024', self.page())
        self.assertEqual(next(s for s in view['seasons'] if s['season'] == 2024)['state'], 'partial')


if __name__ == '__main__':
    unittest.main()
