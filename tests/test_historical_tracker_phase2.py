"""Released canonical/source/HTTP boundaries for the bounded Phase 2 tracker."""
from __future__ import annotations

import contextlib
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from routes.history import create_history_router
from routes.transactions import create_transactions_router
from src.core.historical_memory.graph import HistoricalAssetGraph
from tests import test_trade_timeline as base
from tests.test_historical_faab_conflicts import publish_faab

DAY, ARK = base.DAY, base.ARK
ROOT = "1333655835015942144"
FAAB = "965057520920260608"
PICK = "PICK-2026-R2-ORIG7"


async def prepared():
    """Fixture requests never synchronize a provider."""


class TrackerPhase2Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = base.TradeTimelineTests()
        self.fixture.setUp()
        self.fixture.load()
        self.fixture.load(1)
        publish_faab(self.fixture)
        self.data = self.fixture.data[DAY]
        self.data.update(week=5, transactions=[])
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(patch('src.core.intelligence_memory.intelligence_checkpoint_store', self.fixture.memory))
        for name in ("routes.historical_assets.historical_store",
                     "routes.transactions.canonical_history_store",
                     "services.history.historical_store",
                     "services.history.canonical_history_store"):
            self.stack.enter_context(patch(name, self.fixture.store))
        app = FastAPI()
        def page(title, body):
            renderer = getattr(self, 'page_renderer', None)
            return renderer(title, body) if renderer else HTMLResponse(body)
        def resolver():
            return str(self.data['league']['league_id'])
        app.include_router(create_historical_assets_router(
            league_id=DAY, require_data=lambda: self.data, page=page, league_resolver=resolver))
        app.include_router(create_transactions_router(
            ensure_fresh=prepared, refresh_transactions=prepared,
            require_data=lambda: self.data, state={}, page=page))
        app.include_router(create_history_router(league_id=DAY, page=page, require_data=lambda: self.data, league_resolver=resolver))
        self.app = app
        self.client = self.stack.enter_context(TestClient(app, raise_server_exceptions=False))

    def tearDown(self):
        self.stack.close()
        self.fixture.tearDown()

    def graph(self):
        return HistoricalAssetGraph(self.fixture.store, DAY, self.data, self.fixture.memory)

    def publish(self, facts, season=2026):
        self.fixture.cache.write(self.fixture.cache.normalize(DAY, season, facts))
        self.fixture.store.update_current(DAY, self.data)

    def scores(self, starters, points=10):
        facts = copy.deepcopy(self.fixture.sources[0])
        row = {"roster_id": 1, "matchup_id": None, "players": ["13346"],
               "players_points": {} if points is None else {"13346": points}}
        if starters != "absent":
            row["starters"] = starters
        facts["matchups"] = {"1": [row]}
        self.publish(facts)
        return self.fixture.store.optional_records(DAY, "player_week", season=2026, player_id="13346")[1][0]

    def test_direct_leaders_preserve_score_conflicts_without_full_record_projection(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        for values in ([10, 20], [20, 10], [0, 0]):
            facts['matchups'] = {'1': [{'roster_id': 1, 'players': ['13346'],
                'starters': ['13346'], 'players_points': {'13346': value}} for value in values]}
            self.publish(facts)
            with patch.object(self.fixture.store, '_season_records', side_effect=AssertionError('full projection')):
                count, leaders = self.fixture.store.season_player_leaders(DAY, 2026)
            self.assertEqual(count, 1)
            if values[0] != values[1]:
                self.assertEqual(leaders, [])
            else:
                self.assertEqual([(r['player_id'], r['points']) for r in leaders], [('13346', 0.0)])

    def test_current_activity_does_not_scan_historical_archive(self):
        with patch.object(HistoricalAssetGraph, 'transaction_archive', side_effect=AssertionError('unneeded history scan')) as reads:
            self.assertEqual(self.client.get('/transactions').status_code, 200)
            reads.assert_not_called()

    def test_missing_or_null_starters_are_unknown_not_bench(self):
        for starters in ("absent", None):
            with self.subTest(starters=starters):
                row = self.scores(starters)
                self.assertIsNone(row["payload"]["starter"])
                self.assertEqual(row["payload"]["lineup_role"], "unknown")
                summary = self.graph().player_season_summaries("13346")[0]
                self.assertEqual(summary["bench_appearances"], 0)
                self.assertEqual(summary["unknown_role_appearances"], 1)

    def test_explicit_empty_lineup_and_zero_are_observed(self):
        row = self.scores([], 0)
        self.assertIs(row["payload"]["starter"], False)
        self.assertEqual(row["payload"]["lineup_role"], "bench")
        self.assertEqual(row["payload"]["fantasy_points"], 0)
        row = self.scores(["13346"], None)
        self.assertIs(row["payload"]["starter"], True)
        self.assertIsNone(row["payload"]["fantasy_points"])

    def test_current_ledger_owner_is_distinct_from_historical_transfer(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts["transactions"]["5"].append({
            "type": "trade", "status": "complete", "transaction_id": "exact-transfer",
            "created": 1767225600000, "roster_ids": [7, 3],
            "draft_picks": [{"season": "2028", "round": 3, "roster_id": 7,
                             "previous_owner_id": 7, "owner_id": 3}]})
        self.data["pick_ledger"] = [{"season": 2028, "round": 3,
                                    "original_roster_id": 7, "current_owner_id": 6}]
        self.publish(facts)
        dossier = self.graph().pick_dossier("PICK-2028-R3-ORIG7")
        self.assertEqual(dossier["current_owner"], DAY + ":franchise:6")
        self.assertEqual(dossier["last_observed_holder"], DAY + ":franchise:3")
        self.assertEqual(dossier["original_franchise_id"], DAY + ":franchise:7")
        self.assertTrue(dossier["current_owner_transition_unresolved"])
        r = self.client.get("/picks/PICK-2028-R3-ORIG7")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Connecticut Clams", r.text)
        self.assertIn("transition", r.text.lower())

    def test_missing_current_ledger_does_not_promote_last_transfer(self):
        dossier = self.graph().pick_dossier(PICK)
        self.assertTrue(dossier["exercised"])
        self.assertIsNone(dossier["current_owner"])
        self.assertIsNone(self.graph().pick_dossier("PICK-2027-R1-ORIG4")["current_owner"])

    def test_known_completed_trade_survives_unavailable_other_bucket(self):
        facts = copy.deepcopy(self.fixture.cache.read(DAY, 2023).facts)
        facts["transactions"]["2"] = None
        self.publish(facts, 2023)
        response = self.client.get("/trades/history/" + FAAB)
        self.assertEqual(response.status_code, 200)
        self.assertIn("100 FAAB", response.text)
        self.assertIn("unavailable", response.text.lower())

    def test_optional_scores_and_brackets_keep_independent_pages_available(self):
        for route in ("/players/13346", "/history/2023",
                      "/api/history/players/13346", "/api/history/seasons/2023"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("Internal Server Error", response.text)

    def test_archive_source_filters_and_pagination(self):
        facts = copy.deepcopy(self.fixture.cache.read(DAY, 2023).facts)
        source = json.loads((Path(__file__).parent / "fixtures/historical_archive_source.json").read_text())
        facts["transactions"] = {"1": source["transactions"]}
        self.publish(facts, 2023)
        for extra, expected in [("", 179), ("&team=2", 60), ("&draft_pick=no", 158),
                                ("&date_from=2030-01-01", 0), ("&type=trade", 22),
                                ("&q=nonexistent-audit-query", 0)]:
            with self.subTest(extra=extra):
                r = self.client.get("/transactions?scope=all_history&season=2023" + extra)
                self.assertEqual(r.status_code, 200)
                self.assertIn(f"{expected} archived transactions match", r.text)
        r = self.client.get("/transactions?scope=all_history&season=2023&team=2&draft_pick=no&per_page=10&page=2")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Archive page 2", r.text)
        self.assertLessEqual(r.text.count('>Trade Dossier</a>'), 10)

    def test_blank_optional_fields_are_omitted_but_malformed_are_rejected(self):
        r = self.client.get("/transactions?scope=all_history&type=trade&season=&week=")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/transactions?season=wrong").status_code, 422)

    def test_pick_conversion_retains_validated_origin_and_human_identity(self):
        r = self.client.get(f"/picks/{PICK}?from_trade={ROOT}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'/players/13346?from_trade={ROOT}', r.text)
        self.assertIn("Denzel Boston", r.text)
        foreign = self.client.get(f"/picks/{PICK}?from_trade=foreign-trade")
        self.assertNotIn("foreign-trade", foreign.text)

    def test_converted_branch_has_separate_current_player_observation(self):
        self.data["last_sync"] = "2026-10-13T02:00:00Z"
        branch = next(b for b in self.graph().trade_timeline(ROOT)["branches"] if b["asset_id"] == PICK)
        endpoint = branch["converted_asset"]
        self.assertEqual(branch["state"], "Converted into confirmed drafted player")
        self.assertEqual(endpoint["player_id"], "DTOS-P-13346")
        self.assertEqual(endpoint["current_observed_owner"], DAY + ":franchise:1")
        self.assertEqual(endpoint["as_of"], "2026-10-13T02:00:00Z")
        self.assertNotIn("descendant_value", branch)

    def test_role_conflicts_and_unknown_survive_reconciliation(self):
        from src.core.history_context.assets import reconcile_player_weeks
        row = self.scores(["13346"], 10)
        bench = copy.deepcopy(row)
        bench['payload']['starter'] = False
        for values in ([row, bench], [bench, row]):
            admitted = reconcile_player_weeks(values)
            self.assertIsNone(admitted[0]['payload']['starter'])
            self.assertTrue(admitted[0]['payload']['lineup_role_conflict'])
            self.assertEqual(admitted[0]['payload']['fantasy_points'], 10)
            self.assertEqual(reconcile_player_weeks(admitted)[0]['payload']['lineup_role'], 'unknown')
        other = copy.deepcopy(row)
        other['payload']['fantasy_points'] = 20
        conflicted_score = reconcile_player_weeks([row, other])[0]['payload']
        self.assertIs(conflicted_score['starter'], True)
        self.assertIsNone(conflicted_score['fantasy_points'])
        self.assertTrue(conflicted_score['scoring_conflict'])

    def test_source_periods_distinguish_empty_unavailable_unacquired_malformed(self):
        facts = copy.deepcopy(self.fixture.cache.read(DAY, 2023).facts)
        facts['transactions'].update({'2': [], '3': None, '5': {'error': 'malformed'}})
        self.publish(facts, 2023)
        row = next(r for r in self.fixture.store.source_coverage(DAY)['seasons'] if r['season'] == 2023)
        self.assertEqual(row['transactions']['observed'], [1])
        self.assertEqual(row['transactions']['observed_empty'], [2])
        self.assertEqual(row['transactions']['unavailable'], [3])
        self.assertIn(4, row['transactions']['unacquired'])
        self.assertEqual(row['transactions']['malformed'], [5])
        self.assertFalse(row['transactions']['complete_acquisition'])
        self.assertEqual(self.client.get('/trades/history/' + FAAB).status_code, 200)

    def test_malformed_optional_scoring_and_bracket_shapes_do_not_crash(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts['matchups'] = {'1': [{'roster_id': 1, 'players': ['13346'],
                                  'players_points': ['not-a-score-map'], 'starters': None}]}
        facts['winners_bracket'] = {'malformed': 'not-a-list'}
        facts['losers_bracket'] = [None, 'bad-row']
        self.publish(facts)
        for path in ('/players/13346', '/api/history/players/13346', '/history/2026'):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertNotIn('Internal Server Error', r.text)
        row = self.graph().player_season_summaries('13346')[0]
        self.assertIsNone(row['fantasy_points'])
        self.assertEqual(row['unknown_role_appearances'], 1)

    def test_current_owner_requires_current_league_and_exact_pick(self):
        self.data['pick_ledger'] = [
            {'season': 2028, 'round': 3, 'original_roster_id': 7, 'current_owner_id': 6},
            {'season': 2028, 'round': 3, 'original_roster_id': 4, 'current_owner_id': 1}]
        g = self.graph()
        self.assertEqual(g.pick_dossier('PICK-2028-R3-ORIG7')['current_owner'], DAY + ':franchise:6')
        self.assertEqual(g.pick_dossier('PICK-2028-R3-ORIG4')['current_owner'], DAY + ':franchise:1')
        self.data['pick_ledger'][0]['league_id'] = ARK
        self.assertIsNone(self.graph().pick_dossier('PICK-2028-R3-ORIG7')['current_owner'])
        self.data['league'] = self.fixture.data[ARK]['league']
        self.assertIsNone(self.graph().pick_dossier('PICK-2028-R3-ORIG4')['current_owner'])

    def test_ledger_publication_changes_generation_and_unchanged_reuse_is_stable(self):
        self.data['pick_ledger'] = [{'season': 2028, 'round': 3, 'original_roster_id': 7, 'current_owner_id': 6}]
        self.fixture.store.update_current(DAY, self.data)
        first = self.fixture.store.dataset_version(DAY)
        self.fixture.store.update_current(DAY, self.data)
        self.assertEqual(first, self.fixture.store.dataset_version(DAY))
        self.data['pick_ledger'][0]['current_owner_id'] = 4
        self.fixture.store.update_current(DAY, self.data)
        self.assertNotEqual(first, self.fixture.store.dataset_version(DAY))

    def test_foreign_canonical_trade_origin_is_not_reinterpreted(self):
        forged = 'TRADE-' + ARK + '-' + ROOT
        for path in (f'/picks/{PICK}', '/players/13346', '/trades/history/1414718106177122304'):
            r = self.client.get(path + '?from_trade=' + forged)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('Back to original trade timeline', r.text)
            self.assertNotIn(forged, r.text)

    def test_all_hops_and_historical_performance_preserve_origin(self):
        for path in (f'/picks/{PICK}', '/players/13346', '/history/player/13346',
                     '/trades/history/1414718106177122304'):
            with self.subTest(path=path):
                r = self.client.get(path + '?from_trade=' + ROOT)
                self.assertEqual(r.status_code, 200)
                self.assertIn(f'href="/trades/history/{ROOT}"', r.text)
                self.assertIn('Back to original trade timeline', r.text)
                if path == '/players/13346':
                    self.assertIn('/history/player/13346?from_trade=' + ROOT, r.text)
                    self.assertIn('/trades/history/1414718106177122304?from_trade=' + ROOT, r.text)

    def test_consumed_love_and_boston_keep_conversion_and_no_active_pick_action(self):
        for pick, name in [('PICK-2026-R1-ORIG4', 'Jeremiyah Love'), (PICK, 'Denzel Boston')]:
            r = self.client.get('/picks/' + pick + '?front_office=4&from_trade=' + ROOT)
            self.assertIn('Consumed by verified draft conversion', r.text)
            self.assertIn(name, r.text)
            self.assertNotIn('Shop Asset', r.text)
            self.assertNotIn('Trade For', r.text)

    def test_170_season_points_are_not_30_recipient_points(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts['matchups'] = {str(week): [{'roster_id': franchise, 'matchup_id': None,
            'players': ['13346'], 'starters': ['13346'] if start else [],
            'players_points': {'13346': score}}] for week, franchise, score, start in
            [(1, 1, 70, True), (2, 1, 70, True), (3, 4, 10, True), (4, 4, 20, False)]}
        self.publish(facts)
        summary = self.graph().player_season_summaries('13346')[0]
        self.assertEqual((summary['fantasy_points'], summary['starter_points']), (170, 150))
        held = self.graph().recipient_production('13346', DAY + ':franchise:4')
        self.assertEqual((held['observed_roster_points'], held['started_points'], held['bench_points']), (30, 10, 20))
        self.assertIsNone(held['complete_holding_period_points'])
        r = self.client.get('/trades/history/' + ROOT + '/production')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Known observed roster subtotal: 30.00', r.text)
        self.assertNotIn('170.00', r.text)
        self.assertIn('Complete holding-period benefit: Unavailable', r.text)

    def test_partial_recipient_scores_roles_and_zero_are_distinct(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts['matchups'] = {
            '1': [{'roster_id': 4, 'players': ['13346'], 'starters': ['13346'], 'players_points': {'13346': 0}}],
            '2': [{'roster_id': 4, 'players': ['13346'], 'starters': None, 'players_points': {'13346': 20}}],
            '3': [{'roster_id': 4, 'players': ['13346'], 'starters': ['13346'], 'players_points': {}}]}
        self.publish(facts)
        held = self.graph().recipient_production('13346', DAY + ':franchise:4')
        self.assertEqual(held['started_points'], 0)
        self.assertEqual(held['unknown_role_points'], 20)
        self.assertIsNone(held['bench_points'])
        self.assertEqual(held['missing_score_observations'], 1)
        self.assertEqual(held['supported_starts'], 2)
        self.assertIsNone(held['complete_holding_period_points'])

    def test_reacquisition_intervals_remain_independent_not_a_continuous_hold(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        facts['transactions'] = {str(i): [{'type': 'trade', 'status': 'complete',
            'transaction_id': f'reacquire-{i}', 'created': 1798675200000 + i * 86400000,
            'roster_ids': [sender, receiver], 'adds': {'12506': receiver}, 'drops': {'12506': sender}}]
            for i, sender, receiver in [(1, 1, 4), (2, 4, 6), (3, 6, 4)]}
        self.publish(facts)
        held = self.graph().recipient_production('12506', DAY + ':franchise:4')
        self.assertEqual(len(held['ownership_intervals']), 2)
        self.assertIsNotNone(held['ownership_intervals'][0]['disposed_at'])
        self.assertIsNone(held['ownership_intervals'][1]['disposed_at'])
        self.assertIsNone(held['complete_holding_period_points'])

    def test_production_fragment_rejects_changed_source_generation(self):
        generation = self.fixture.store.dataset_version(DAY)
        self.assertEqual(self.client.get(f'/trades/history/{ROOT}/production?generation={generation}').status_code, 200)
        facts = copy.deepcopy(self.fixture.sources[0])
        facts['matchups'] = {'1': []}
        self.publish(facts)
        r = self.client.get(f'/trades/history/{ROOT}/production?generation={generation}')
        self.assertEqual(r.status_code, 409)
        self.assertIn('Source evidence changed', r.text)

    def test_quote_cards_explain_provider_units_dates_and_retained_incompatible_value(self):
        from src.ui.trade_timeline import render_timeline
        boundary = self.graph().trade_dossier(ROOT)['occurred_at']
        self.fixture.capture('player:12506', boundary, event=boundary)
        g = self.graph()
        d = g.trade_dossier(ROOT)
        body = render_timeline(g.trade_timeline(ROOT), d)
        self.assertIn('FantasyCalc', body)
        self.assertIn('0-1000', body)
        self.assertIn('Normalization version:', body)
        self.assertIn('Source knowledge:', body)
        self.assertIn('Source observation confidence:', body)
        self.fixture.capture('player:12508', boundary, event=boundary, value=5000, semantics=False)
        g = self.graph()
        d = g.trade_dossier(ROOT)
        row = next(a for a in d['trade_time_intelligence']['assets'] if a['asset_id'] == 'DTOS-P-12508')
        self.assertIsNone(row['value'])
        self.assertIsNotNone(row['retained_observation'])
        self.assertIn('lacks compatible', row['admission_reason'])
        body = render_timeline(g.trade_timeline(ROOT), d)
        self.assertIn('raw source value: 5000', body)
        self.assertEqual(d['trade_time_intelligence']['side_totals'], {})

    def test_future_quote_is_visible_only_as_rejected_raw_evidence(self):
        self.fixture.capture('player:12506', '2030-01-01T00:00:00Z', event='2030-01-01T00:00:00Z')
        row = next(a for a in self.graph().trade_dossier(ROOT)['trade_time_intelligence']['assets'] if a['asset_id'] == 'DTOS-P-12506')
        self.assertIsNone(row['value'])
        self.assertIn('not decision-time eligible', row['admission_reason'])
        self.assertIsNotNone(row['retained_observation'])

    def test_archive_owner_filter_uses_historical_manager_not_current_franchise_owner(self):
        r = self.client.get('/transactions?scope=all_history&season=2023&owner=zkobes')
        self.assertIn('1 archived transactions match', r.text)
        r = self.client.get('/transactions?scope=all_history&season=2023&owner=MikeMoss')
        self.assertIn('0 archived transactions match', r.text)
        self.assertIn('season-observed managers', r.text)

    def test_faab_once_grouped_parties_and_unique_asset_count(self):
        r = self.client.get('/trades/history/' + FAAB)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.count('100 FAAB'), 1)
        self.assertIn('Sent', r.text)
        self.assertIn('Received', r.text)
        self.assertIn('Nasty Navel Lasers', r.text)
        self.assertIn('zkobes', r.text)
        archive = self.client.get('/transactions?scope=all_history&season=2023&type=trade')
        self.assertIn('8 assets', archive.text)
        self.assertIn('1 FAAB movement', archive.text)

    def test_unknown_original_pick_is_visible_and_cannot_complete_pricing(self):
        facts = copy.deepcopy(self.fixture.sources[0])
        original = next(t for rows in facts['transactions'].values() for t in rows if t['transaction_id'] == ROOT)
        original['draft_picks'] = [{'season': '2027', 'round': 1, 'previous_owner_id': 4, 'owner_id': 7}]
        self.publish(facts)
        boundary = self.graph().trade_dossier(ROOT)['occurred_at']
        for player in ('12506', '12508'):
            self.fixture.capture('player:' + player, boundary, event=boundary)
        dossier = self.graph().trade_dossier(ROOT)
        self.assertEqual(dossier['trade_time_intelligence']['coverage_state'], 'partial')
        self.assertEqual(dossier['trade_time_intelligence']['side_totals'], {})
        response = self.client.get('/trades/history/' + ROOT)
        self.assertIn('Unresolved original consideration', response.text)
        self.assertIn('original franchise unavailable', response.text)

    def test_unchanged_route_reads_have_zero_durable_growth_after_initialization(self):
        import hashlib
        paths = ['/trades/history/' + ROOT, '/trades/history/' + ROOT + '/production',
                 '/picks/' + PICK, '/transactions?scope=all_history&type=trade']
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200)
        def files():
            return {str(p): (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in Path(self.fixture.temp.name).rglob('*') if p.is_file()}
        before = files()
        for _ in range(5):
            for path in paths:
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(files(), before)


if __name__ == "__main__":
    unittest.main()
