"""Customer facts stay visible while source inventories remain available on demand."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from html.parser import HTMLParser
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.history import create_history_router
from src.ui.franchise_timeline import render_franchise_timeline
from src.ui.season_history import season_draft_selections, season_postseason_results
from src.ui.trade_timeline import _quote_card
from tests import test_pick_page_prepared_evidence as pick_fixtures


def default_text(markup):
    """Closed native disclosure bodies are not part of the default experience."""
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__()
            self.closed = []
            self.in_summary = False
            self.parts = []
        def handle_starttag(self, tag, attrs):
            if tag == 'details':
                self.closed.append('open' not in dict(attrs))
            elif tag == 'summary' and sum(self.closed) == 1:
                self.in_summary = True
        def handle_endtag(self, tag):
            if tag == 'summary':
                self.in_summary = False
            elif tag == 'details':
                self.closed.pop()
        def handle_data(self, data):
            if not any(self.closed) or self.in_summary and sum(self.closed) == 1:
                self.parts.append(data)
    reader = Reader()
    reader.feed(markup)
    return ' '.join(reader.parts)



class CustomerHistoryPresentationTests(unittest.TestCase):
    def archive(self):
        return {
            'season': 2025, 'display_status': 'Partial',
            'standings': [{'roster_id': 1, 'team_name': 'Original Franchise', 'gm_name': 'Then Manager',
                'rank': 1, 'franchise_id': 'L:franchise:1', 'wins': 9, 'losses': 4,
                'points_for': 0, 'points_against': -1, 'postseason_finish': 1},
                {'roster_id': 2, 'team_name': 'Selecting Franchise', 'gm_name': 'Other Manager'}],
            'champion': {'team_name': 'Original Franchise'}, 'runner_up': {},
            'weeks': [], 'leaders': [], 'availability': {'playoffs': True},
            'counts': {'matchups': 0, 'transactions': 1, 'draft_picks': 1},
            'draft': {'picks': [{'player_id': '501', 'payload': {'pick_no': 1, 'round': 1,
                'original_roster_id': 1, 'selecting_roster_id': 2,
                'metadata': {'first_name': 'Recorded', 'last_name': 'Player'}}}]},
            'playoffs': {'result': {'champion_roster_id': 1}, 'brackets': [{'payload': {
                'type': 'winners', 'bracket': [{'m': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}]}}]},
        }

    def test_existing_season_page_has_readable_draft_and_playoffs_not_primary_json(self):
        archive = self.archive()
        app = FastAPI()
        app.include_router(create_history_router(league_id='L', page=lambda title, body: HTMLResponse(body)))
        with patch('routes.history.season_archive', return_value=archive) as read, TestClient(app) as client:
            response = client.get('/history/2025')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(read.call_args.args, ('L', 2025))
        normal = default_text(response.text)
        self.assertIn('View recorded draft selections', normal)
        self.assertIn('View recorded playoff results', normal)
        self.assertNotIn('(JSON)', normal)
        self.assertIn('Recorded Player', response.text)
        self.assertIn('Original franchise: Original Franchise', response.text)
        self.assertIn('Selected by: Selecting Franchise', response.text)
        self.assertIn('Winner: Original Franchise', response.text)
        self.assertIn('/api/history/seasons/2025/draft', response.text)
        self.assertIn('/api/history/seasons/2025/playoffs', response.text)
        self.assertEqual(archive, self.archive())

    def test_missing_draft_and_bracket_do_not_become_complete_empty_or_reconstructed(self):
        archive = self.archive()
        archive['draft'] = {}
        archive['playoffs']['brackets'] = []
        self.assertIn('Missing records do not establish an empty draft', season_draft_selections(archive))
        self.assertIn('no bracket is reconstructed', season_postseason_results(archive))

    def test_raw_draft_user_and_legacy_alias_are_not_presented_as_franchise_origin(self):
        archive = self.archive()
        payload = archive['draft']['picks'][0]['payload']
        payload.pop('original_roster_id')
        payload.pop('selecting_roster_id')
        payload.update(roster_id=2, picked_by='715018078752182272',
                       original_franchise=2, current_pick_owner='715018078752182272')
        markup = season_draft_selections(archive)
        self.assertIn('Selected by: Selecting Franchise', markup)
        self.assertIn('Original franchise: Not recorded', markup)
        self.assertNotIn('Franchise 715018078752182272', markup)
        self.assertNotIn('Original franchise: Selecting Franchise', markup)

    def test_conflicting_playoff_outcomes_do_not_turn_into_supported_winner(self):
        archive = self.archive()
        archive['playoffs']['brackets'][0]['payload']['bracket'][0]['w'] = 3
        markup = season_postseason_results(archive)
        self.assertIn('Winner not established', markup)
        self.assertNotIn('Winner: Franchise 3', markup)

    def test_current_and_historical_pick_rights_are_distinct_without_duplicate_missing_labels(self):
        fixture = pick_fixtures.PickPagePreparedEvidenceTests()
        data = fixture.data()
        data['market_data'] = {}
        data['traded_picks'].append(dict(season='2024', round=1, roster_id=1, owner_id=2))
        markup = fixture.render(data)
        normal = default_text(markup)
        self.assertIn('Current traded picks', normal)
        self.assertIn('2027 Round 1', normal)
        self.assertNotIn('2024 Round 1', normal)
        self.assertIn('Past or unconfirmed pick transfers', normal)
        self.assertNotIn('MARKET UNAVAILABLE', normal)
        self.assertNotIn('Projected range: UNKNOWN', normal)
        self.assertEqual(normal.count('Market price: Unavailable'), 1)
        self.assertIn('Owner in recorded transfer', markup)
        self.assertIn('These recorded transfers do not establish a currently tradable pick', markup)
        self.assertIn('PICK-2024-R1-ORIG1', markup)
        zero = fixture.data()
        zero['market_data']['pick_quotes']['FantasyCalc'][0]['normalization_reference']['normalized_value'] = 0
        self.assertIn('Market price: 0', default_text(fixture.render(zero)))

    def test_pick_actions_require_exact_future_native_right_and_matching_owner(self):
        from types import SimpleNamespace
        from routes.historical_assets import create_historical_assets_router
        base = dict(pick_id='PICK-2027-R1-ORIG1', season='2027', round='1', events=[],
                    original_franchise_id='L:franchise:1', current_owner='L:franchise:2',
                    reconciliation_status='current_observation', slot_status='unknown')
        facts = dict(league={'league_id': 'L', 'season': '2026'},
                     teams=[{'roster_id': 1, 'team_name': 'Your Team'},
                            {'roster_id': 2, 'team_name': 'Partner'}],
                     pick_ledger=[dict(season=2027, round=1, original_roster_id=1,
                                       current_owner_id=2, league_id='L')])
        for case in ('current', 'historical', 'converted', 'foreign', 'duplicate', 'owner_conflict', 'unknown_season'):
            with self.subTest(case=case):
                dossier, data = deepcopy(base), deepcopy(facts)
                if case == 'historical':
                    dossier['season'] = '2025'
                    dossier['pick_id'] = 'PICK-2025-R1-ORIG1'
                    data['pick_ledger'][0]['season'] = 2025
                elif case == 'converted':
                    dossier['exercised'] = True
                elif case == 'foreign':
                    data['pick_ledger'][0]['league_id'] = 'OTHER'
                elif case == 'duplicate':
                    data['pick_ledger'].append(dict(data['pick_ledger'][0], current_owner_id=1))
                elif case == 'owner_conflict':
                    data['pick_ledger'][0]['current_owner_id'] = 1
                elif case == 'unknown_season':
                    data['league'].pop('season')
                app = FastAPI()
                app.include_router(create_historical_assets_router(league_id='L', require_data=lambda: data,
                    page=lambda title, body: HTMLResponse(body)))
                with patch('routes.historical_assets.historical_graph', return_value=SimpleNamespace(pick_dossier=lambda identity: dossier)), TestClient(app) as client:
                    response = client.get('/picks/' + dossier['pick_id'] + '?front_office=1')
                self.assertEqual(response.status_code, 200)
                if case == 'current':
                    self.assertIn('asset_id=2027-R1-1', response.text)
                    self.assertIn('owner_roster_id=2', response.text)
                    self.assertIn('Future draft pick', default_text(response.text))
                else:
                    self.assertNotIn('/trades/trade-for?', response.text)
                    self.assertNotIn('/trades/shop?', response.text)
                    self.assertNotIn('Future draft pick', default_text(response.text))

    def test_readable_quote_clock_retains_precise_original_in_source_details(self):
        row = dict(asset_name='Player', value=0, match_state='EXACT', observed_at='2026-11-03T18:01:05.123456Z',
            comparison_identity=None, provider_evidence=[], admission_reason='Supported quote', quote_age_seconds=0)
        markup = _quote_card(row, 'Player')
        self.assertIn('Nov 3, 2026 · 18:01 UTC', default_text(markup))
        self.assertIn('2026-11-03T18:01:05.123456Z', markup)
        self.assertIn('<b>0</b>', markup)

    def test_franchise_coverage_keeps_partial_state_and_activity_but_collapses_week_inventory(self):
        from tests.test_franchise_timeline_coverage import FranchiseTimelineCoverageTests
        fixture = FranchiseTimelineCoverageTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        event_record = fixture.trade('rendered-clock')
        event_record.update(created=1727800000123, status_updated=1727800001123)
        fixture.past({'0': [event_record]})
        from services.franchise_timeline import franchise_timeline
        model = fixture.graph()
        view = franchise_timeline(model, '1')
        before = deepcopy(view)
        markup = render_franchise_timeline(view)
        normal = default_text(markup)
        self.assertIn('Partial transaction coverage', normal)
        self.assertIn('RETAINED / NOT REVALIDATED', normal)
        self.assertIn('source periods retrieved', normal)
        self.assertNotIn('Retrieved weeks:', normal)
        self.assertIn('Retrieved weeks:', markup)
        event = next(row for row in view['events'] if row['id'] == 'rendered-clock')
        self.assertEqual(event['occurred_at'], '2024-10-01T16:26:40.123000Z')
        self.assertIn('Oct 1, 2024 · 16:26 UTC', normal)
        self.assertNotIn(event['occurred_at'], normal)
        self.assertNotIn('source-linked roster-slot continuity', normal)
        self.assertIn('Exact event timestamp: ' + event['occurred_at'], markup)
        self.assertIn('Recorded franchise attribution: source-linked roster-slot continuity', markup)
        self.assertEqual(view, before)
        # Break the authoritative source-season link, retaining the source
        # event. Rendering must qualify franchise attribution, not credit a
        # current manager or silently discard the supported movement.
        current = deepcopy(fixture.f.fixture.sources[0])
        current['league']['previous_league_id'] = 'missing-intermediate-season'
        fixture.f.data['league']['previous_league_id'] = 'missing-intermediate-season'
        fixture.f.publish(current)
        uncertain = franchise_timeline(fixture.graph(), '1')
        uncertain_before = deepcopy(uncertain)
        raw = next(row for row in uncertain['events'] if row['id'] == 'rendered-clock')
        self.assertTrue(raw['completed'])
        self.assertEqual(raw['attribution'], 'franchise continuity unconfirmed')
        uncertain_markup = render_franchise_timeline(uncertain)
        uncertain_normal = default_text(uncertain_markup)
        self.assertIn('This activity is recorded, but its link to this franchise is unconfirmed.', uncertain_normal)
        self.assertIn('Ownership changes do not backdate decisions to the current manager.', uncertain_normal)
        self.assertNotIn('franchise continuity unconfirmed', uncertain_normal)
        self.assertIn('Recorded franchise attribution: franchise continuity unconfirmed', uncertain_markup)
        self.assertIn('Exact event timestamp: ' + raw['occurred_at'], uncertain_markup)
        self.assertEqual(uncertain, uncertain_before)
        # Keep the original distinction between owner-observation clocks and
        # the transaction clock available once in the real detail route.
        response = fixture.f.client.get('/trades/history/1333655835015942144')
        self.assertEqual(response.status_code, 200)
        detail_normal = default_text(response.text)
        self.assertNotIn('DTOS Sleeper retrieval/sync observations', detail_normal)
        self.assertIn('Current-owner as-of dates, where recorded, describe DTOS Sleeper retrieval/sync observations, not acquisition or ownership-change times.', response.text)
        self.assertIn('Exact transaction timestamp: 2026-03-01T02:07:18.497000Z', response.text)
        self.assertIn('Mar 1, 2026 · 02:07 UTC', detail_normal)
