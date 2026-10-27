"""Exact partial evaluation of the existing saved-cohort slot permutation.

All prices below are disposable controls, never quotes for the named players.
Missing inputs reserve their saved slots and never receive assigned prices.
"""
from copy import deepcopy
from contextlib import ExitStack
from itertools import combinations, product
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from services.personal_rankings import personal_values
from src.core.accounts.personal_store import load_personal
from tests import test_personal_rankings as fixtures
from tests import test_personal_rankings_recovery_trade as recovery


def evidence(name, payload):
    if os.getenv('DTOS_PERSONAL_PARTIAL_EVIDENCE'):
        def sanitize(value):
            if isinstance(value, dict):
                return {key: '[REDACTED fixture credential]' if any(
                    word in key.lower() for word in ('csrf', 'token', 'password', 'cookie', 'authorization'))
                    else sanitize(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [sanitize(item) for item in value]
            return value
        root = Path(os.environ['DTOS_PERSONAL_PARTIAL_EVIDENCE'])
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + '.json')).write_text(json.dumps(sanitize(payload), indent=2))


class PartialSlotProofTests(unittest.TestCase):
    def test_values_agree_with_every_full_completion_at_every_saved_position(self):
        checks = 0
        for size in range(2, 6):
            order = [f'player:{i}' for i in range(size)]
            doc = {'order': order, 'baseline': {'ids': order}}
            for count in range(1, min(2, size - 1) + 1):
                for positions in combinations(range(size), count):
                    known_positions = [i for i in range(size) if i not in positions]
                    for known in product((0, 400, 1000), repeat=len(known_positions)):
                        rows = [{'asset_id': order[i], 'market_value': price}
                                for i, price in zip(known_positions, known)]
                        result = personal_values(doc, {'rows': rows})
                        complete_curves = [sorted([*known, *unknown], reverse=True)
                                           for unknown in product((0, 200, 400, 600, 800, 1000), repeat=count)]
                        expected = {}
                        for i in known_positions:
                            possibilities = {curve[i] for curve in complete_curves}
                            if len(possibilities) == 1:
                                expected[order[i]] = possibilities.pop()
                        self.assertEqual(result['values'], expected, (doc, rows))
                        self.assertFalse(result['available'])
                        self.assertEqual(result['partial_available'], bool(expected))
                        self.assertTrue(all(order[i] not in result['values'] for i in positions))
                        checks += 1
        evidence('slot-proof', {'fixture_cases': checks, 'every_tested_full_completion_agrees': True,
                 'top_middle_bottom_missing_positions': True, 'unsupported_inputs_never_assigned': True})

    def test_no_compression_or_assumed_unrelated_value_in_a_strict_curve(self):
        order = ['player:a', 'player:x', 'player:b']
        result = personal_values({'order': order, 'baseline': {'ids': order}},
                                 {'rows': [{'asset_id': 'player:a', 'market_value': 800},
                                           {'asset_id': 'player:b', 'market_value': 300}]})
        self.assertFalse(result['available'])
        self.assertFalse(result['partial_available'])
        self.assertEqual(result['values'], {})

    def test_equal_slots_zero_and_full_reappearance_preserve_the_original_rule(self):
        order = ['player:a', 'player:x', 'player:b', 'player:c']
        doc = {'order': order, 'baseline': {'ids': order}, 'tiers': ['player:x'],
               'preferences': {'player:x': {'target': True}}, 'revision': 9}
        rows = [{'asset_id': k, 'market_value': 500} for k in order if k != 'player:x']
        saved = deepcopy(doc)
        partial = personal_values(doc, {'rows': rows})
        self.assertEqual(partial['values'], {'player:b': 500})
        self.assertNotIn('player:x', partial['values'])  # Its own slot is exact too, but its price is unsupported.
        full = personal_values(doc, {'rows': [*rows, {'asset_id': 'player:x', 'market_value': 500}]})
        self.assertTrue(full['available'])
        self.assertEqual(full['values'], {key: 500 for key in order})
        rows[-1]['market_value'] = 0
        self.assertNotIn('player:x', personal_values(doc, {'rows': rows})['values'])
        self.assertEqual(doc, saved)
        invalid = deepcopy(doc)
        invalid['order'][-1] = invalid['order'][0]
        self.assertFalse(personal_values(invalid, {'rows': rows})['partial_available'])


class FourAssetPartialHTTPTests(unittest.TestCase):
    def test_four_named_missing_inputs_keep_order_tiers_flags_revision_and_exact_slots(self):
        f = fixtures.PersonalRankingsHTTPTests('test_full_seed_matches_market_and_reads_create_no_rows')
        f.setUp()
        self.addCleanup(f.doCleanups)
        names = {'13602': ('Jack Strand', 'QB'), '13075': ('Myles Price', 'WR'),
                 '3155': ('Laquon Treadwell', 'WR'), '11593': ('Brevyn Spann-Ford', 'TE')}
        for row in f.market.rows:
            if row['values']['market_value'] is not None:
                row['values']['market_value'] = 500
        for pid, (name, position) in names.items():
            f.data['players'][pid] = {'full_name': name, 'position': position}
            f.market.rows.append(f.market.row('player:' + pid, 500, position, name))
        f.initialize()
        f.post('reorder', asset_id='player:1', to_position=10)
        f.post('reorder', asset_id='player:2', to_position=10)
        f.post('reorder', asset_id='player:1', to_position=5)
        f.post('reorder', asset_id='player:2', to_position=6)
        f.post('tiers', asset_id='player:1', tier_start=True)
        f.post('preferences', asset_id='player:1', preferences={'protect': True})
        f.post('preferences', asset_id='player:13075', preferences={'target': True})
        f.post('preferences', asset_id='player:3155', preferences={'avoid': True})
        saved = load_personal(f.store, 'account-a', 'league-1', 1)
        before = f.state()
        for row in f.market.rows:
            if row['asset_id'].removeprefix('player:') in names:
                row['values']['market_value'] = None
        f.market.generation = 'Market-B'
        after = f.state()
        targets = ('services.sleeper.sleeper_get', 'services.trade_intelligence.generate_trade_workflow',
                   'services.team_headquarters.build_team_headquarters',
                   'src.core.intelligence.orchestrator.IntelligenceOrchestrator.analyze',
                   'src.core.intelligence.roster_diagnostics._compute',
                   'src.core.trade_intelligence.lineup.optimal_legal_lineup',
                   'src.core.intelligence.team_strength.prepare_for_data',
                   'src.core.fois.service.FOISService._generate_sync',
                   'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
                   'src.core.market_trends.service.MarketTrendService.trend_for_asset',
                   'src.core.asset_market.engine.AssetMarketCache.get')
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(target, side_effect=AssertionError(target))) for target in targets]
            for _ in range(3):
                self.assertEqual(f.state()['revision'], saved['revision'])
            for spy in spies:
                spy.assert_not_called()
        self.assertFalse(after['personal_available'])
        self.assertTrue(after['personal_partial_available'])
        self.assertEqual({r['asset_id']: r['personal_value'] for r in after['rows']
                          if r['personal_value_available']}, {'player:1': 500, 'player:2': 500})
        self.assertEqual({i['asset_id'] for i in after['compatibility_issues']}, {'player:' + pid for pid in names})
        self.assertEqual([r['asset_id'] for r in after['rows'] if r['custom_ranked']], saved['order'])
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)
        for row in after['rows']:
            if row['personal_value_available']:
                self.assertEqual(row['personal_value'], next(r['personal_value'] for r in before['rows'] if r['asset_id'] == row['asset_id']))
        f.use_account('account-b')
        self.assertFalse(f.state()['initialized'])
        f.use_account('account-a')
        self.assertEqual(f.state()['revision'], saved['revision'])
        old_data, old_market = f.data, f.market
        f.store.upsert_membership('account-a', {'league_id': 'league-2', 'season': '2026'},
                                  'account-a', 1, 'Other franchise', 'active')
        f.store.activate('account-a', 'league-2')
        # A changed active membership cannot accidentally read the old league.
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 403)
        f.data = deepcopy(old_data)
        f.data['league']['league_id'] = 'league-2'
        f.data['market_data']['generation'] = 'providers-league-2'
        f.market = fixtures.PreparedMarket(f.data)
        f.market.generation = 'Market-league-2'
        self.assertFalse(f.state()['initialized'])
        f.initialize()
        self.assertEqual(f.state()['revision'], 1)
        self.assertNotEqual(load_personal(f.store, 'account-a', 'league-2', 1), saved)
        f.store.activate('account-a', 'league-1')
        f.data, f.market = old_data, old_market
        self.assertEqual(f.state()['revision'], saved['revision'])
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)
        f.market.data['market_data']['generation'] = 'foreign-source'
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 409)
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)
        evidence('four-asset-http', {'scope': 'Fictional prices and disposable accounts, not production compatibility',
                 'before': before, 'after': after, 'saved_document_unchanged': True})


class PartialTradeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = recovery.PersonalRankingsRecoveryTradeTests('test_priced_inactive_player_remains_usable_across_all_custom_workflows')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def missing(self):
        f = self.f
        f.make_one_price_unavailable()
        f.editor.data['market_data']['providers']['FantasyCalc']['b']['value'] = None
        f.editor.data['market_data']['generation'] = 'providers-B'
        f.editor.market.data = deepcopy(f.editor.data)

    def test_supported_package_and_all_workflows_remain_usable_without_repricing(self):
        f = self.f
        before = f.fixture.trade('custom').json()['evaluation']
        saved = f.document()
        self.missing()
        state = f.editor.state()
        bootstrap = f.editor.client.get('/api/trades/workspace').json()['personalization']
        self.assertTrue(bootstrap['available'])
        self.assertTrue(bootstrap['personal_partial_available'])
        self.assertNotIn('b', bootstrap['values'])
        results = []
        for endpoint, payload in f.operations:
            r = f.fixture.trade('custom', endpoint=endpoint, **payload)
            self.assertEqual(r.status_code, 200, r.text)
            for offer in r.json().get('results', []):
                proposal = offer.get('proposal') or {}
                for key in [*proposal.get('assets_sent', []), *proposal.get('assets_received', [])]:
                    self.assertIn(key, bootstrap['values'])
            results.append({'endpoint': endpoint, 'workflow': payload.get('workflow'), 'status': r.status_code,
                            'count': r.json().get('count')})
        after = f.fixture.trade('custom').json()['evaluation']
        for side in ('sent', 'received'):
            self.assertEqual(after['personal_value_evidence'][side], before['personal_value_evidence'][side])
        self.assertEqual(after['recommendation'], before['recommendation'])
        self.assertEqual(after['personal_value_evidence']['ranking_availability'], 'partial')
        neutral = f.fixture.trade('neutral').json()['evaluation']
        for key in ('market_evidence', 'lineup_impact', 'multi_horizon_impact', 'counterparty_summary'):
            self.assertEqual(after[key], neutral[key])
        self.assertEqual(f.document(), saved)
        evidence('supported-workflows', {'operations': results, 'state': state,
                 'saved_document_unchanged': True, 'custom_evaluation': after, 'neutral_evaluation': neutral})

    def test_mixed_or_dependent_packages_withhold_custom_but_preserve_neutral(self):
        f = self.f
        self.missing()
        for fields in ({'assets_sent': ['b']}, {'assets_received': ['c']}):
            r = f.fixture.trade('custom', **fields)
            self.assertEqual(r.status_code, 422, r.text)
            self.assertEqual(r.json()['detail']['code'], 'personal_evidence_unavailable')
            self.assertNotIn('evaluation', r.json())
            calculator = f.fixture.trade('custom', endpoint='calculate', **fields)
            self.assertEqual(calculator.status_code, 200, calculator.text)
            self.assertEqual(calculator.json()['personal']['verdict'], 'UNAVAILABLE')
            self.assertIn('unavailable_reason', calculator.json()['personal'])
        neutral = f.fixture.trade('neutral', endpoint='calculate', assets_received=['c'])
        self.assertEqual(neutral.status_code, 200)
        self.assertEqual(neutral.json()['market']['received']['total'], 500)
        self.assertNotIn('personal', neutral.json())

    def test_partial_publication_still_fences_source_revision_and_revoked_membership(self):
        from services.trade_intelligence import evaluate_trade_request
        f = self.f
        self.missing()
        saved = f.document()

        def source_transition(*args, **kwargs):
            result = evaluate_trade_request(*args, **kwargs)
            f.editor.market.generation += '-changed'
            return result

        with patch('routes.trades.evaluate_trade_request', side_effect=source_transition):
            response = f.fixture.trade('custom')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['detail']['code'], 'personal_context_changed')
        self.assertNotIn('evaluation', response.json())
        self.assertEqual(f.document(), saved)
        self.assertEqual(f.fixture.trade('custom').status_code, 200)

        def revision_transition(*args, **kwargs):
            result = evaluate_trade_request(*args, **kwargs)
            self.assertEqual(f.editor.post('preferences', asset_id='player:e', preferences={'target': True}).status_code, 200)
            return result

        with patch('routes.trades.evaluate_trade_request', side_effect=revision_transition):
            response = f.fixture.trade('custom')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['detail']['code'], 'personal_context_changed')
        self.assertNotIn('evaluation', response.json())

        def revoked(*args, **kwargs):
            result = evaluate_trade_request(*args, **kwargs)
            f.editor.store.revoke_session(f.editor.tokens['account-a'][0])
            return result

        with patch('routes.trades.evaluate_trade_request', side_effect=revoked):
            response = f.fixture.trade('custom')
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()['detail']['code'], 'personal_scope_revoked')
        self.assertNotIn('evaluation', response.json())



class CanonicalPartialPublicationTests(unittest.TestCase):
    def test_one_publication_supplies_directory_dossier_trade_and_custom_values(self):
        from datetime import datetime, timezone
        from fastapi.responses import HTMLResponse
        from routes.trades import create_trades_router
        from services.personal_rankings import personal_bootstrap, resolve_personal_context, validate_personal_context
        from src.core.provider_network import build_provider_network
        from src.core.valuation_intelligence import build_valuation_intelligence
        from src.core.valuation.normalization import prepare_market_normalization
        from tests import test_personal_rankings_availability as canonical

        f = canonical.CanonicalRankingAvailabilityTests('test_real_market_ready_without_synthetic_provider_timestamp')
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.addCleanup(f.cache.clear)
        data = deepcopy(f.data)
        # Canonical synchronized team rows carry player identity and position;
        # the editor-only fixture intentionally omits these Trade inputs.
        for team in data['teams']:
            for player in team['players']:
                player.update(data['players'][player['id']])
        data['market_data'] = {'providers': {'FantasyCalc': {
            key: {'value': 6000, 'confidence': 90, 'format': 'dynasty_2qb'} for key in data['players']}},
            'pick_quotes': {'FantasyCalc': [{'provider': 'FantasyCalc', 'market_format': 'fc:12:2qb:ppr',
                'year': 2028, 'round': 1, 'pick_type': 'generic_round', 'availability': 'current',
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'value': 6000, 'confidence': 80}]}}

        def publish(candidate):
            candidate.pop('valuation_intelligence', None)
            prepare_market_normalization(candidate['market_data'])
            build_provider_network(candidate, {})
            build_valuation_intelligence(candidate, {})
            f.publish(candidate)

        publish(data)
        f.initialize()
        f.post('reorder', asset_id='player:1', to_position=3)
        f.post('reorder', asset_id='player:4', to_position=4)
        before = f.state()
        saved = load_personal(f.store, 'account-a', 'league-1', 1)
        candidate = deepcopy(f.data)
        candidate['market_data']['providers']['FantasyCalc']['2']['value'] = None
        publish(candidate)
        after = f.state()
        self.assertTrue(after['personal_partial_available'])
        self.assertFalse(after['personal_available'])
        rows = {r['asset_id']: r for r in after['rows']}
        self.assertIsNone(rows['player:2']['market_value'])
        directory = {r['asset_id']: r for r in f.market.directory(minimum=0, limit=250)['assets']}
        for key in ('player:1', 'player:4'):
            self.assertEqual(rows[key]['personal_value'], 500)
            self.assertEqual(rows[key]['market_value'], 500)
            self.assertEqual(directory[key]['values']['market_value'], 500)
            self.assertEqual(f.market.detail(key)['asset']['values']['market_value'], 500)

        def dependencies():
            return {'store': f.store, 'market_reader': f.market}

        f.app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: f.data,
            page=lambda title, body: HTMLResponse(body),
            personal_resolver=lambda d, p: resolve_personal_context(d, p, **dependencies()),
            personal_validator=lambda d, p, c: validate_personal_context(d, p, c, **dependencies()),
            personal_bootstrap=lambda d, active: personal_bootstrap(d, active, **dependencies())))
        workspace = f.client.get('/api/trades/workspace?mode=calculator').json()
        response = f.client.post('/api/trades/calculate', json={'active_roster_id': 1, 'partner_roster_id': 2,
            'assets_sent': ['1'], 'assets_received': ['4'], 'valuation_mode': 'custom',
            'personal_revision': after['revision'], 'personal_market_generation': after['generation'],
            'workspace_context': workspace['workspace_context']}, headers={'x-csrf-token': f.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['personal']['sent']['total'], 500)
        self.assertEqual(response.json()['market']['received']['total'], 500)
        self.assertEqual(load_personal(f.store, 'account-a', 'league-1', 1), saved)
        self.assertEqual(before['revision'], after['revision'])
        evidence('canonical-cross-surface', {'fixture_native_quotes': 6000, 'canonical_value': 500,
                 'personal_value': 500, 'one_publication': f.market.identity(),
                 'before': before, 'after': after, 'trade_calculator': response.json(),
                 'saved_document_unchanged': True})
