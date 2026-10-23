"""Prepared Market → account store → authenticated My DTOS HTTP controls."""
from __future__ import annotations

import copy
import random
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.personal_rankings import create_personal_rankings_router
from services.personal_rankings import PersonalRankingError, build_universe, personal_values, to_trade_id
from src.core.accounts import AccountService, AccountStore
from src.core.accounts.personal_store import load_personal
from src.platform.account_context import AccountContextMiddleware


class PreparedMarket:
    """An immutable-directory-shaped fixture; no providers or build factories."""
    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.generation = 'Market-A'
        self.semantic_generation = 'semantic-A'
        self.calls = 0
        self.rows = [
            self.row('player:1', 900, 'QB', 'Elite QB'),
            self.row('player:2', 600, 'WR', 'Older producer'),
            self.row('pick:2028:1:4', 500, 'PICK', '2028 Round 1 (Franchise 4)'),
            self.row('player:3', 300, 'RB', 'Young RB'),
            self.row('pick:2028:1:5', 250, 'PICK', '2028 Round 1 (Franchise 5)'),
            self.row('player:4', 0, 'TE', 'Supported zero'),
            self.row('player:5', None, 'WR', 'Missing price'),
        ]

    @staticmethod
    def row(key, value, position, label):
        return {'asset_id': key, 'asset_type': 'pick' if key.startswith('pick:') else 'player',
                'display_name': label, 'position': position, 'status': 'Active',
                'values': {'market_value': value}}

    def identity(self):
        return {'league_id': self.data['league']['league_id'], 'market_generation': self.generation}

    def directory(self, *, offset=0, limit=250, sort='market', direction='desc', minimum=None):
        self.calls += 1
        selected = [r for r in self.rows if minimum is None or
                    isinstance(r['values']['market_value'], (int, float)) and r['values']['market_value'] >= minimum]
        rows = sorted(selected,
                      key=lambda r: (r['values']['market_value'] if isinstance(r['values']['market_value'], (int, float))
                                     else -1, r['asset_id']), reverse=True)
        return {**self.identity(), 'total': len(rows), 'assets': copy.deepcopy(rows[offset:offset + limit])}


def ranking_data():
    return {'league': {'league_id': 'league-1'}, 'market_data': {'generation': 'providers-A'},
            'players': {str(i): {'full_name': f'Player {i}', 'position': position}
                        for i, position in ((1, 'QB'), (2, 'WR'), (3, 'RB'), (4, 'TE'), (5, 'WR'))},
            'teams': [
                {'roster_id': 1, 'players': [{'id': '1'}, {'id': '3'}],
                 'picks_owned': [{'year': 2028, 'round': 1, 'original_roster_id': 4, 'current_owner_id': 1}]},
                {'roster_id': 2, 'players': [{'id': '2'}, {'id': '4'}, {'id': '5'}],
                 'picks_owned': [{'year': 2028, 'round': 1, 'original_roster_id': 5, 'current_owner_id': 2}]},
            ]}


class PersonalRankingsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AccountStore(Path(self.temp.name) / 'accounts.sqlite3')
        self.service = AccountService(self.store)
        self.tokens = {}
        for name in ('account-a', 'account-b'):
            self.store.create_account(name, name, name, 'fixture-hash', [])
            self.store.link_sleeper(name, sleeper_user_id=name, username=name, display_name=name)
            self.store.upsert_membership(name, {'league_id': 'league-1', 'season': '2026'},
                                         name, 1, name, 'active')
            self.store.activate(name, 'league-1')
            self.tokens[name] = self.service.new_session(name)
        self.data = ranking_data()
        self.market = PreparedMarket(self.data)
        self.app = FastAPI()
        self.app.add_middleware(AccountContextMiddleware, service=self.service, required=True)
        self.app.include_router(create_personal_rankings_router(
            service=self.service, require_data=lambda: self.data, market_model=lambda: self.market,
            page=lambda title, body: HTMLResponse(body)))
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.use_account('account-a')

    def use_account(self, name):
        self.account = name
        token, self.csrf = self.tokens[name]
        self.client.cookies.set('dtos_session', token)

    def state(self):
        response = self.client.get('/api/my-dtos')
        self.assertEqual(response.status_code, 200, response.text)
        directives = {value.strip() for value in response.headers['cache-control'].split(',')}
        self.assertIn('no-store', directives)
        self.assertIn('private', directives)
        return response.json()

    def post(self, command, *, state=None, **fields):
        current = state or self.state()
        return self.client.post('/api/my-dtos', json={
            'command': command, 'expected_revision': current['revision'],
            'market_generation': current['generation'], 'context': current['context'], **fields},
            headers={'X-CSRF-Token': self.csrf})

    def initialize(self):
        response = self.post('initialize')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_full_seed_matches_market_and_reads_create_no_rows(self):
        first = self.state()
        self.assertFalse(first['initialized'])
        self.assertIsNone(load_personal(self.store, 'account-a', 'league-1', 1))
        expected = [r['asset_id'] for r in build_universe(self.data, self.market)['rows']]
        state = self.initialize()
        self.assertEqual([r['asset_id'] for r in state['rows']], expected)
        self.assertEqual(len(expected), 6)
        for row in state['rows']:
            self.assertEqual(row['personal_value'], row['market_value'])
        self.assertNotIn('player:5', expected)
        snapshot = load_personal(self.store, 'account-a', 'league-1', 1)
        self.state()
        self.state()
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), snapshot)
        self.assertNotIn('market_value', str(snapshot))

    def test_reorder_is_global_and_monotone_for_player_and_exact_pick(self):
        state = self.initialize()
        first = self.post('reorder', state=state, asset_id='player:3', to_position=1)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['rows'][0]['asset_id'], 'player:3')
        self.assertEqual(first.json()['rows'][0]['personal_value'], 900)
        second = self.post('reorder', asset_id='pick:2028:1:4', to_position=1)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()['rows'][0]['asset_id'], 'pick:2028:1:4')
        self.assertEqual(second.json()['rows'][0]['personal_value'], 900)
        self.assertEqual(to_trade_id('pick:2028:1:4'), '2028-R1-4')
        self.assertEqual(to_trade_id('pick:2028:1:5'), '2028-R1-5')

    def test_tiers_do_not_change_values_and_neutral_view_preserves_edits(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        before = self.state()
        tiers = self.post('tiers', asset_id='player:3', tier_start=True)
        self.assertEqual(tiers.status_code, 200, tiers.text)
        self.assertEqual([r['personal_value'] for r in before['rows']],
                         [r['personal_value'] for r in tiers.json()['rows']])
        response = self.post('mode', mode='neutral')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['mode'], 'neutral')
        self.assertEqual(response.json()['rows'][0]['asset_id'], 'player:3')
        self.assertTrue(response.json()['rows'][0]['tier_start'])

    def test_preferences_are_exact_owned_and_contradictions_fail_without_mutation(self):
        self.initialize()
        accepted = self.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        doc = load_personal(self.store, 'account-a', 'league-1', 1)
        denied = self.post('preferences', asset_id='pick:2028:1:5', preferences={'protect': True})
        self.assertEqual(denied.status_code, 422, denied.text)
        conflicting = self.post('preferences', asset_id='player:3', preferences={'target': True, 'avoid': True})
        self.assertEqual(conflicting.status_code, 422, conflicting.text)
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), doc)

    def test_restart_is_confirmed_uses_latest_market_and_preserves_flags_only(self):
        self.initialize()
        self.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        self.post('reorder', asset_id='player:3', to_position=1)
        self.post('tiers', asset_id='player:3', tier_start=True)
        before = load_personal(self.store, 'account-a', 'league-1', 1)
        missing_confirm = self.post('restart')
        self.assertEqual(missing_confirm.status_code, 422, missing_confirm.text)
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), before)
        self.market.generation = 'Market-B'
        self.market.rows[1]['values']['market_value'] = 950
        response = self.post('restart', confirmation='RESTART RANKINGS')
        self.assertEqual(response.status_code, 200, response.text)
        state = response.json()
        self.assertEqual(state['rows'][0]['asset_id'], 'player:2')
        self.assertFalse(any(r['tier_start'] for r in state['rows']))
        saved = load_personal(self.store, 'account-a', 'league-1', 1)
        self.assertEqual(saved['preferences'], {'pick:2028:1:4': {'protect': True}})
        self.assertGreater(saved['revision'], before['revision'])

    def test_csrf_foreign_context_and_stale_edits_are_atomic(self):
        state = self.initialize()
        doc = load_personal(self.store, 'account-a', 'league-1', 1)
        csrf = self.client.post('/api/my-dtos', json={'command': 'restart'})
        self.assertEqual(csrf.status_code, 403)
        foreign = self.client.post('/api/my-dtos', json={},
                                  headers={'X-CSRF-Token': self.csrf, 'Origin': 'https://foreign.example'})
        self.assertEqual(foreign.status_code, 403)
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), doc)
        self.post('reorder', asset_id='player:3', to_position=1)
        latest = load_personal(self.store, 'account-a', 'league-1', 1)
        stale = self.post('reorder', state=state, asset_id='player:2', to_position=1)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), latest)
        self.use_account('account-b')
        self.assertFalse(self.state()['initialized'])
        other = self.post('initialize', state=state)
        self.assertEqual(other.status_code, 409, other.text)
        self.assertIsNone(load_personal(self.store, 'account-b', 'league-1', 1))

    def test_new_asset_does_not_silently_reprice_saved_cohort_and_removed_withholds(self):
        self.initialize()
        original = self.state()
        self.data['players']['6'] = {'full_name': 'New QB', 'position': 'QB'}
        self.market.rows.append(self.market.row('player:6', 990, 'QB', 'New QB'))
        self.market.generation = 'Market-new'
        new = self.state()
        self.assertEqual(new['new_asset_ids'], ['player:6'])
        by_id = {r['asset_id']: r for r in new['rows']}
        self.assertIsNone(by_id['player:6']['personal_value'])
        self.assertFalse(by_id['player:6']['custom_ranked'])
        self.assertEqual({r['asset_id']: r['personal_value'] for r in original['rows']},
                         {r['asset_id']: by_id[r['asset_id']]['personal_value'] for r in original['rows']})
        self.market.rows = [r for r in self.market.rows if r['asset_id'] != 'player:2']
        self.market.generation = 'Market-removed'
        removed = self.state()
        self.assertFalse(removed['personal_available'])
        self.assertTrue(all(r['personal_value'] is None for r in removed['rows']))
        self.assertIn('player:2', [r['asset_id'] for r in removed['rows']])

    def test_missing_boolean_unidentified_retired_and_foreign_league_are_not_priced(self):
        for key, value in (('player:1', True), ('player:2', float('inf'))):
            next(r for r in self.market.rows if r['asset_id'] == key)['values']['market_value'] = value
        self.market.rows.append(self.market.row('unknown', 1000, 'QB', 'Unknown'))
        self.market.rows[3]['status'] = 'Retired'
        universe = build_universe(self.data, self.market)
        admitted = {r['asset_id'] for r in universe['rows']}
        self.assertFalse({'player:1', 'player:2', 'player:3', 'player:5', 'unknown'} & admitted)
        self.assertIn('player:4', admitted)
        self.assertEqual(next(r['market_value'] for r in universe['rows'] if r['asset_id'] == 'player:4'), 0)
        self.market.data['league']['league_id'] = 'foreign'
        with self.assertRaises(PersonalRankingError):
            build_universe(self.data, self.market)

    def test_reads_and_edits_never_invoke_expensive_factories(self):
        targets = (
            'services.sleeper.sleeper_get',
            'services.trade_intelligence.generate_trade_workflow',
            'services.team_headquarters.build_team_headquarters',
            'src.core.intelligence.orchestrator.IntelligenceOrchestrator.analyze',
            'src.core.intelligence.roster_diagnostics._compute',
            'src.core.trade_intelligence.lineup.optimal_legal_lineup',
            'src.core.intelligence.team_strength.prepare_for_data',
            'src.core.fois.service.FOISService._generate_sync',
            'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
            'src.core.market_trends.service.MarketTrendService.trend_for_asset',
            'src.core.asset_market.engine.AssetMarketCache.get',
        )
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(target, side_effect=AssertionError(target)))
                     for target in targets]
            self.initialize()
            for _ in range(3):
                self.state()
                self.assertEqual(self.post('reorder', asset_id='player:3', to_position=1).status_code, 200)
                self.assertEqual(self.post('mode', mode='neutral').status_code, 200)
                self.assertEqual(self.post('mode', mode='custom').status_code, 200)
            for spy in spies:
                spy.assert_not_called()

    def test_duplicate_ownership_and_mixed_id_kind_are_withheld(self):
        self.data['teams'][1]['players'].append({'id': '1'})
        malformed = self.market.row('pick:2028:1:4', 950, 'QB', 'Wrong identity kind')
        malformed['asset_type'] = 'player'
        self.market.rows = [r for r in self.market.rows if r['asset_id'] != 'pick:2028:1:4']
        self.market.rows.insert(0, malformed)
        admitted = {row['asset_id'] for row in build_universe(self.data, self.market)['rows']}
        self.assertNotIn('player:1', admitted)
        self.assertNotIn('pick:2028:1:4', admitted)
        self.assertIn('player:2', admitted)

    def test_missing_mismatched_and_racing_generation_are_not_admitted(self):
        self.market.data['market_data'].pop('generation')
        with self.assertRaises(PersonalRankingError) as missing:
            build_universe(self.data, self.market)
        self.assertEqual(missing.exception.code, 'market_source_changed')
        self.market.data['market_data']['generation'] = 'providers-B'
        with self.assertRaises(PersonalRankingError):
            build_universe(self.data, self.market)
        self.market.data['market_data']['generation'] = 'providers-A'
        directory = self.market.directory

        def changed_page(**kwargs):
            result = directory(**kwargs)
            result['market_generation'] = 'replacement-B'
            return result

        with patch.object(self.market, 'directory', side_effect=changed_page):
            with self.assertRaises(PersonalRankingError) as race:
                build_universe(self.data, self.market)
        self.assertEqual(race.exception.code, 'market_source_changed')


class PersonalRankingsTradeHTTPTests(unittest.TestCase):
    """The actual saved editor order reaches Calculator and Trade evaluation."""
    def setUp(self):
        from tests.test_capital_strategy_reconciliation import CapitalStrategyTests
        from routes.trades import create_trades_router
        from services.personal_rankings import personal_bootstrap, resolve_personal_context, validate_personal_context
        from services.trade_intelligence import build_trade_workspace
        self.capital = CapitalStrategyTests('test_strategy_changes_fit_never_market_or_lineups')
        self.capital.setUp()
        self.addCleanup(self.capital.doCleanups)
        self.capital.prices(c=500, d=300, b=0)
        self.capital.data['market_data']['generation'] = 'providers-A'
        self.editor = PersonalRankingsHTTPTests('test_full_seed_matches_market_and_reads_create_no_rows')
        self.editor.setUp()
        self.addCleanup(self.editor.doCleanups)
        self.editor.data = self.capital.data
        self.editor.market = PreparedMarket(self.capital.data)
        self.reader_patch = patch('services.trade_intelligence._trade_projection_service', return_value=self.capital.reader)
        self.reader_patch.start()
        self.addCleanup(self.reader_patch.stop)
        workspace = build_trade_workspace(self.capital.data, 1)
        self.editor.market.rows = []
        for pool in workspace['pools'].values():
            for asset in pool:
                key = ('player:' + asset.asset_id if asset.kind == 'player'
                       else f'pick:{asset.season}:{asset.round}:{asset.original_roster_id}')
                self.editor.market.rows.append(self.editor.market.row(key, asset.trade_value,
                    asset.position or 'PICK', asset.label))
        def dependencies():
            return {'store': self.editor.store, 'market_reader': self.editor.market}
        self.editor.app.include_router(create_trades_router(
            ensure_fresh=AsyncMock(), require_data=lambda: self.editor.data,
            page=lambda title, body: HTMLResponse(body),
            personal_resolver=lambda data, payload: resolve_personal_context(data, payload, **dependencies()),
            personal_validator=lambda data, payload, context: validate_personal_context(data, payload, context, **dependencies()),
            personal_bootstrap=lambda data, active: personal_bootstrap(data, active, **dependencies())))

    def trade(self, mode='custom', endpoint='evaluate', **overrides):
        state = self.editor.state()
        response = self.editor.client.get('/api/trades/workspace')
        self.assertEqual(response.status_code, 200, response.text)
        payload = {'workflow': 'create', 'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['a'], 'assets_received': ['2028-R1-4'], 'strategy': 'REBUILD',
                   'workspace_context': response.json()['workspace_context'],
                   'valuation_mode': mode, 'personal_revision': state['revision'],
                   'personal_market_generation': state['generation'], **overrides}
        return self.editor.client.post('/api/trades/' + endpoint, json=payload,
                                      headers={'X-CSRF-Token': self.editor.csrf})

    def test_editor_reorder_changes_custom_http_decision_but_preserves_neutral(self):
        self.editor.initialize()
        neutral = self.trade('neutral')
        self.assertEqual(neutral.status_code, 200, neutral.text)
        self.assertEqual(neutral.json()['evaluation']['recommendation'], 'WORTH PURSUING')
        moved = self.editor.post('reorder', asset_id='player:a', to_position=1)
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()['rows'][0]['personal_value'], 500)
        personal = self.trade('custom')
        self.assertEqual(personal.status_code, 200, personal.text)
        chosen = personal.json()['evaluation']
        self.assertNotEqual(chosen['recommendation'], neutral.json()['evaluation']['recommendation'])
        self.assertEqual(chosen['neutral_assessment']['recommendation'], 'WORTH PURSUING')
        self.assertEqual(chosen['personal_value_evidence']['sent']['total'], 500)
        for key in ('market_evidence', 'lineup_impact', 'multi_horizon_impact'):
            self.assertEqual(chosen[key], neutral.json()['evaluation'][key], key)
        again = self.trade('neutral')
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()['evaluation']['recommendation'], 'WORTH PURSUING')
        self.assertEqual(again.json()['evaluation']['market_evidence'], neutral.json()['evaluation']['market_evidence'])

    def test_calculator_keeps_canonical_and_personal_costs_distinct(self):
        self.editor.initialize()
        self.editor.post('reorder', asset_id='player:a', to_position=1)
        response = self.trade('custom', endpoint='calculate')
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value['market']['sent']['total'], 250)
        self.assertEqual(value['market']['received']['total'], 250)
        self.assertEqual(value['personal']['sent']['total'], 500)
        self.assertEqual(value['personal']['received']['total'], 250)

    def test_client_cannot_inject_server_owned_personal_prices(self):
        self.editor.initialize()
        response = self.trade('custom', _personal_context={'mode': 'custom', 'values': {'a': 0}})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertNotIn('evaluation', response.json())

    def test_missing_prepared_market_does_not_block_neutral_workspace(self):
        self.editor.market = None
        response = self.editor.client.get('/api/trades/workspace')
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['personalization']['mode'], 'neutral')
        self.assertFalse(payload['personalization']['available'])
        self.assertIn('workspace_context', payload)
        self.assertTrue(payload['teams'])

    def test_edit_during_evaluation_rejects_result_and_later_retry_recovers(self):
        from services.trade_intelligence import evaluate_trade_request
        from src.core.accounts.personal_store import save_personal
        self.editor.initialize()

        def evaluate_then_edit(*args, **kwargs):
            result = evaluate_trade_request(*args, **kwargs)
            old = load_personal(self.editor.store, 'account-a', 'league-1', 1)
            document = {key: value for key, value in old.items()
                        if key not in {'revision', 'created_at', 'updated_at'}}
            document['mode'] = 'neutral'
            save_personal(self.editor.store, 'account-a', 'league-1', 1,
                          document, expected_revision=old['revision'])
            return result

        with patch('routes.trades.evaluate_trade_request', side_effect=evaluate_then_edit):
            changed = self.trade('custom')
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(changed.json()['detail']['code'], 'personal_context_changed')
        self.assertNotIn('evaluation', changed.json())
        retry = self.trade('neutral')
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()['evaluation']['recommendation'], 'WORTH PURSUING')

    def test_session_revocation_during_evaluation_withholds_successful_response(self):
        from services.trade_intelligence import evaluate_trade_request
        self.editor.initialize()
        before = load_personal(self.editor.store, 'account-a', 'league-1', 1)

        def evaluate_then_revoke(*args, **kwargs):
            result = evaluate_trade_request(*args, **kwargs)
            token, _csrf = self.editor.tokens['account-a']
            self.editor.store.revoke_session(token)
            return result

        with patch('routes.trades.evaluate_trade_request', side_effect=evaluate_then_revoke):
            revoked = self.trade('custom')
        self.assertEqual(revoked.status_code, 403, revoked.text)
        self.assertEqual(revoked.json()['detail']['code'], 'personal_scope_revoked')
        self.assertNotIn('evaluation', revoked.json())
        self.assertEqual(load_personal(self.editor.store, 'account-a', 'league-1', 1), before)


def curve_calibration(edits=1000):
    """Deterministic positional/pick moves over one prepared 200-asset curve."""
    randomizer = random.Random(2187)
    ids = [f'player:{index + 1}' for index in range(197)] + [
        'pick:2028:1:4', 'pick:2028:1:5', 'pick:2029:1:4']
    rows = [{'asset_id': key, 'market_value': (199 - index) * 5}
            for index, key in enumerate(ids)]
    universe = {'rows': rows, 'generation': 'calibration-current-A'}
    source = copy.deepcopy(universe)
    document = {'baseline': {'generation': 'seed-A', 'ids': ids.copy()},
                'order': ids.copy(), 'tiers': []}
    initial = personal_values(document, universe)
    if not initial['available'] or initial['values'] != {r['asset_id']: r['market_value'] for r in rows}:
        raise AssertionError('Zero-edit values did not equal the complete neutral curve.')
    total = sum(initial['values'].values())
    moved_higher = moved_lower = tier_changes = 0
    for sequence in range(edits):
        before = personal_values(document, universe)['values']
        origin, destination = randomizer.randrange(len(ids)), randomizer.randrange(len(ids))
        key = document['order'].pop(origin)
        document['order'].insert(destination, key)
        after = personal_values(document, universe)
        if not after['available'] or sum(after['values'].values()) != total:
            raise AssertionError('A reorder changed cohort value supply or availability.')
        if destination < origin:
            moved_higher += 1
            if after['values'][key] < before[key]:
                raise AssertionError('Moving higher lowered a personal price.')
        elif destination > origin:
            moved_lower += 1
            if after['values'][key] > before[key]:
                raise AssertionError('Moving lower raised a personal price.')
        if min(after['values'].values()) != 0 or max(after['values'].values()) != 995:
            raise AssertionError('The adapter extrapolated beyond the canonical curve.')
        if list(after['values']) != document['order']:
            raise AssertionError('Personal values lost exact global asset order.')
        if sequence % 10 == 0:
            document['tiers'] = document['order'][::7]
            tier_changes += 1
            if personal_values(document, universe)['values'] != after['values']:
                raise AssertionError('Tier labels changed cardinal prices.')
    if universe != source:
        raise AssertionError('Personal changes mutated neutral source evidence.')
    return {'edits': edits, 'seed': 2187, 'assets': len(ids), 'exact_picks': 3,
            'moves_higher': moved_higher, 'moves_lower': moved_lower,
            'tier_changes': tier_changes, 'minimum_value': 0, 'maximum_value': 995,
            'cohort_total_before': total, 'cohort_total_after': total,
            'source_unchanged': True, 'zero_edit_parity': True}


class PersonalCurveCalibrationTests(unittest.TestCase):
    def test_thousand_edits_preserve_curve_monotonicity_identity_and_tiers(self):
        evidence = curve_calibration()
        self.assertEqual(evidence['edits'], 1000)
        self.assertGreater(evidence['moves_higher'], 0)
        self.assertGreater(evidence['moves_lower'], 0)
        self.assertEqual(evidence['tier_changes'], 100)
        self.assertEqual(evidence['cohort_total_before'], evidence['cohort_total_after'])


if __name__ == '__main__':
    unittest.main()
