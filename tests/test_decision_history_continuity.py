"""Existing canonical history and observed Market facts reach decision consumers."""
from copy import deepcopy
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.responses import HTMLResponse

from services.trade_intelligence import build_trade_workspace
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.market_trends import MarketTrendService
from src.core.market_trends.current import current_comparison
from src.core.trade_intelligence.evidence_context import build_trade_evidence_context
from src.core.valuation.normalization import prepare_market_normalization
from src.core.valuation.universe import ValuationUniverse
from src.core.valuation_intelligence.engine import _score_asset
from tests import test_personal_rankings as personal
from tests.test_market_observation_producer_identity import checkpoint


def evidence(name, value):
    if os.getenv('DTOS_DECISION_HISTORY_EVIDENCE'):
        root = Path(os.environ['DTOS_DECISION_HISTORY_EVIDENCE'])
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + '.json')).write_text(json.dumps(value, indent=2, default=str))


def publish_market(data, price, at, *, player='a', fmt='dynasty_2qb'):
    """Actual normalizer/valuation producer; all quotes are explicitly fictional."""
    for quote in data['market_data']['providers']['FantasyCalc'].values():
        quote.update(format=fmt, retrieved_at=at, source_updated_at=None)
    data['market_data']['providers']['FantasyCalc'][player]['value'] = price * 12
    data.pop('valuation_intelligence', None)
    prepare_market_normalization(data['market_data'])
    universe = ValuationUniverse(data, {'data': data})
    data['valuation_intelligence'] = {'assets': {
        asset['asset_id']: _score_asset(asset, [], {}, None) for asset in universe.assets}}
    return universe


class DecisionHistoryFixture:
    def __init__(self):
        self.f = personal.PersonalRankingsTradeHTTPTests('test_calculator_keeps_canonical_and_personal_costs_distinct')
        self.f.setUp()
        self.root = Path(self.f.editor.temp.name)
        self.data = self.f.editor.data
        self.memory = IntelligenceCheckpointStore(self.root / 'observations.db')
        for index, price in enumerate((100, 120, 140, 160), 1):
            data = deepcopy(self.data)
            stamp = f'2026-07-0{index}T12:00:00+00:00'
            publish_market(data, price, stamp)
            observations = CheckpointPipeline._market_observations(data, 'player:a')
            assert observations and all(o.observed_at == stamp for o in observations)
            self.memory.put_sparse(replace(checkpoint(str(index), price, stamp), asset_id='player:a'),
                market_context_id='fictional-compatible-format', provider_evidence=observations)
        publish_market(self.data, 250, '2026-08-31T12:00:00+00:00')
        self.f.editor.market.data = deepcopy(self.data)
        self.stack = ExitStack()
        self.stack.enter_context(patch('src.core.trade_intelligence.evidence_context.intelligence_checkpoint_store', self.memory))
        from src.core.gm_behavioral_intelligence.diagnostics import league_gm_observations
        self.stack.enter_context(patch.object(league_gm_observations, '_cache',
            return_value=SleeperSeasonCache(self.root / 'seasons')))

    def close(self):
        self.stack.close()
        self.f.doCleanups()


class DecisionTrendContinuityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = DecisionHistoryFixture()
        self.addCleanup(self.fixture.close)
        self.data, self.memory = self.fixture.data, self.fixture.memory

    def context(self):
        assets = [a for pool in build_trade_workspace(self.data, 1)['pools'].values() for a in pool]
        return build_trade_evidence_context(self.data, assets)

    def test_canonical_current_endpoint_reaches_trade_using_original_package_keys(self):
        expected = MarketTrendService(self.memory).trend_for_asset('player:a', 250,
            current_semantics=current_comparison(self.data, 'player:a', 250))
        current = self.context().trends_by_asset['a']
        for field in ('direction', 'magnitude', 'checkpoint_count', 'comparison_scope', 'comparison_end_at'):
            self.assertEqual(current[field], expected[field])
        self.assertEqual(current['magnitude'], 150)
        self.assertEqual(current['checkpoint_count'], 4)
        self.assertEqual(current['asset_id'], 'player:a')
        self.assertTrue(current['provenance']['current_endpoint_comparable'])
        evidence('trend-join', {'scope': 'Fictional compatible quotes through actual producer and sparse store',
            'canonical': expected, 'trade': current, 'trade_key': 'a'})

    def test_custom_value_is_never_a_neutral_market_observation(self):
        asset = next(a for a in build_trade_workspace(self.data, 1)['pools'][1] if a.asset_id == 'a')
        neutral = build_trade_evidence_context(self.data, [asset]).trends_by_asset['a']
        custom = build_trade_evidence_context(self.data, [replace(asset, trade_value=999)]).trends_by_asset['a']
        self.assertEqual(neutral, custom)
        self.assertEqual(custom['current_value'], 250)

    def test_unknown_and_exact_pick_ids_are_not_guessed_or_globally_substituted(self):
        with patch.object(self.memory, 'market_trend_evidence', wraps=self.memory.market_trend_evidence) as read:
            ctx = build_trade_evidence_context(self.data, [SimpleNamespace(asset_id='2028-R1-3', kind='pick', trade_value=250),
                SimpleNamespace(asset_id='2028-R1-4', kind='pick', trade_value=250),
                SimpleNamespace(asset_id='unknown-id', kind='player', trade_value=250)])
        self.assertEqual(ctx.trends_by_asset, {})
        read.assert_not_called()

    def test_incompatible_or_unbound_current_evidence_keeps_history_only(self):
        original = deepcopy(self.data)
        for change in ('format', 'mismatched_current_price', 'missing_provenance'):
            self.data.clear()
            self.data.update(deepcopy(original))
            if change == 'format':
                publish_market(self.data, 250, '2026-08-31T12:00:00+00:00', fmt='dynasty_1qb')
            elif change == 'mismatched_current_price':
                self.data['valuation_intelligence']['assets']['player:a']['valuation_layers']['market_value']['value'] = 251
            else:
                self.data.pop('valuation_intelligence')
            trend = build_trade_evidence_context(self.data, [SimpleNamespace(asset_id='a', kind='player', market_value=250)]).trends_by_asset['a']
            self.assertEqual(trend['comparison_scope'], 'history_only')
            self.assertFalse(trend['provenance']['current_endpoint_comparable'])
            self.assertEqual(trend['magnitude'], 60)

    def test_genuine_zero_missing_and_knowledge_cutoffs_remain_distinct(self):
        publish_market(self.data, 0, '2026-08-31T12:00:00+00:00')
        zero = build_trade_evidence_context(self.data, [SimpleNamespace(asset_id='a', kind='player', market_value=0)]).trends_by_asset['a']
        self.assertEqual(zero['current_value'], 0)
        self.assertEqual(zero['magnitude'], -100)
        missing = build_trade_evidence_context(self.data, [SimpleNamespace(asset_id='a', kind='player', market_value=None)]).trends_by_asset['a']
        self.assertIsNone(missing['current_value'])
        self.assertEqual(missing['comparison_scope'], 'history_only')
        past = MarketTrendService(self.memory).trend_for_asset('player:a', 250,
            as_of='2026-07-01T12:00:00+00:00', current_semantics=current_comparison(self.data, 'player:a', 0))
        self.assertFalse(past['provenance']['current_endpoint_comparable'])
        self.assertNotEqual(past['magnitude'], 150)

    def test_one_bounded_read_and_no_persistence_on_repeated_context_reads(self):
        before = hashlib.sha256((self.fixture.root / 'observations.db').read_bytes()).hexdigest()
        assets = [SimpleNamespace(asset_id='a', kind='player', market_value=250)] * 500
        targets = ('services.sleeper.sleeper_get', 'services.trade_intelligence.generate_trade_workflow',
            'src.core.fois.service.FOISService._generate_sync',
            'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
            'src.core.trade_intelligence.lineup.optimal_legal_lineup',
            'src.core.asset_market.engine.AssetMarketCache.get')
        with ExitStack() as stack, patch.object(self.memory, 'market_trend_evidence', wraps=self.memory.market_trend_evidence) as read:
            guards = [stack.enter_context(patch(target, side_effect=AssertionError(target))) for target in targets]
            for _ in range(3):
                build_trade_evidence_context(self.data, assets)
            self.assertTrue(all(guard.call_count == 0 for guard in guards))
        self.assertEqual(read.call_count, 3)
        self.assertTrue(all(call.kwargs['asset_ids'] == ('player:a',) for call in read.call_args_list))
        self.assertEqual(hashlib.sha256((self.fixture.root / 'observations.db').read_bytes()).hexdigest(), before)
        evidence('read-cost', {'calls_per_three_reads': dict.fromkeys(targets, 0), 'existing_sparse_batch_reads': 3,
            'batch_unique_assets': 1, 'input_assets': 500, 'database_sha256_before_after': before})

    def test_actual_private_trade_http_and_custom_mode_preserve_values_and_lineups(self):
        f = self.fixture.f
        f.editor.initialize()
        source = deepcopy(self.data)
        # Do not confuse extra historical context with changes to verdict policy.
        with patch.dict(self.data, {'market_trend_summaries': {}}):
            before = f.trade('neutral').json()['evaluation']
        neutral_response = f.trade('neutral')
        self.assertEqual(neutral_response.status_code, 200, neutral_response.text)
        after = neutral_response.json()['evaluation']
        historical = after['dimensions']['historical_counterparty_evidence']
        self.assertIn('a', [r['asset_id'] for r in historical['trend_signals']])
        self.assertIn('recorded neutral Market change +150.00 points', after['explanation_html'])
        self.assertIn('2026-07-01 to 2026-08-31', after['explanation_html'])
        for key in ('values', 'market_evidence', 'lineup_impact', 'recommendation', 'generated_trade_eligible'):
            self.assertEqual(after[key], before[key])
        custom_response = f.trade('custom')
        self.assertEqual(custom_response.status_code, 200, custom_response.text)
        custom = custom_response.json()['evaluation']
        self.assertEqual(custom['market_evidence'], after['market_evidence'])
        self.assertEqual(custom['lineup_impact'], after['lineup_impact'])
        self.assertEqual(custom['dimensions']['historical_counterparty_evidence']['trend_signals'], historical['trend_signals'])
        self.assertEqual(self.data, source)
        evidence('trade-http', {'scope': 'Disposable accounts and fictional prepared quotes', 'before': before,
            'after': after, 'custom': custom, 'saved_revision': f.editor.state()['revision']})


class CurrentTransactionPeriodTests(unittest.TestCase):
    def test_active_duplicate_retains_unique_acquired_bucket_and_exact_pick(self):
        from src.core.history_context.store import CanonicalHistoryStore
        raw = {'transaction_id': 'one', 'type': 'trade', 'status': 'complete', 'roster_ids': [1, 2],
            'adds': {'p': 2}, 'drops': {'p': 1}, 'draft_picks': [{'season': '2028', 'round': 1,
                'roster_id': 1, 'previous_owner_id': 2, 'owner_id': 1}]}
        for week in (0, 3):
            data = {'league': {'league_id': 'L', 'season': '2026'}, 'teams': [],
                'season_transactions': {str(week): [raw]}, 'transactions': [raw]}
            saved = deepcopy(data)
            store = CanonicalHistoryStore()
            store.update_current('L', data)
            rows = [r for r in store._current_records('L', 2026) if r['entity_type'] == 'trade']
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['week'], week)
            self.assertEqual(rows[0]['payload']['draft_picks'], raw['draft_picks'])
            self.assertEqual(data, saved)

    def test_explicit_zero_missing_and_conflicting_bucket_contexts(self):
        from src.core.history_context.store import CanonicalHistoryStore
        for explicit, buckets, expected in [({'week': 0}, {}, 0), ({}, {}, None),
                ({}, {'1': [{'transaction_id': 'one'}], '2': [{'transaction_id': 'one'}]}, None),
                ({'leg': 4}, {'3': [{'transaction_id': 'one'}]}, 4)]:
            data = {'league': {'league_id': 'L', 'season': '2026'}, 'teams': [],
                'season_transactions': buckets, 'transactions': [{'transaction_id': 'one', 'type': 'trade', **explicit}]}
            store = CanonicalHistoryStore()
            store.update_current('L', data)
            row = next(r for r in store._current_records('L', 2026) if r['source_record_id'] == 'one')
            self.assertEqual(row['week'], expected)


class HistoricalContinuityFixture:
    def __init__(self):
        from routes.historical_assets import create_historical_assets_router
        from routes.transactions import create_transactions_router
        from src.core.history_context.store import CanonicalHistoryStore
        from src.core.history_context.metadata import MinimalMetadataStore
        self.editor = personal.PersonalRankingsHTTPTests('test_full_seed_matches_market_and_reads_create_no_rows')
        self.editor.setUp()
        self.root = Path(self.editor.temp.name)
        self.cache = SleeperSeasonCache(self.root / 'season-cache')
        self.stack = ExitStack()
        self.stack.enter_context(patch('src.core.history_context.store.sleeper_season_cache', self.cache))
        self.stack.enter_context(patch('src.core.history_context.store.minimal_metadata_store', MinimalMetadataStore(self.root / 'metadata.db')))
        self.history = CanonicalHistoryStore()
        self.memory = IntelligenceCheckpointStore(self.root / 'observations.db')
        self.stack.enter_context(patch('src.core.intelligence_memory.intelligence_checkpoint_store', self.memory))
        self.stack.enter_context(patch('routes.historical_assets.historical_store', self.history))
        self.stack.enter_context(patch('routes.transactions.canonical_history_store', self.history))
        self.data = self.editor.data
        self.data['league'].update(name='Fictional Continuity League', season='2026', previous_league_id='prior-L',
            settings={'leg': 3}, scoring_settings={'pass_yd': .05}, roster_positions=['QB', 'SUPER_FLEX', 'BN'])
        for team in self.data['teams']:
            team.update(owner_id='account-a' if team['roster_id'] == 1 else 'other-manager',
                team_name='Fictional Harbor' if team['roster_id'] == 1 else 'Fictional Summit')
        self.now_trade = self.trade('now-trade', '2026-08-31T12:00:00+00:00', '1', 2, 1)
        current = [self.now_trade,
            {'transaction_id': 'claim', 'type': 'waiver', 'status': 'complete', 'roster_ids': [2],
                'adds': {'5': 2}, 'settings': {'waiver_bid': 0}},
            *[{'transaction_id': f'failed-{i}', 'type': 'waiver', 'status': 'failed', 'roster_ids': [2],
                'adds': {'3': 2}, 'settings': {'waiver_bid': 7}} for i in range(2)],
            {'transaction_id': 'pending-drop', 'type': 'drop', 'status': 'pending', 'roster_ids': [2], 'drops': {'4': 2}},
            {'transaction_id': 'unknown-drop', 'type': 'drop', 'roster_ids': [2], 'drops': {'5': 2}}]
        self.data.update(week=3, transactions=deepcopy(current), season_transactions={'0': deepcopy(current)})
        past = [self.trade(f'past-{i}', f'2025-09-0{i+1}T12:00:00+00:00', '2', 1 if i % 2 == 0 else 2, 2 if i % 2 == 0 else 1)
                for i in range(5)]
        facts = {'league': {'league_id': 'prior-L', 'season': '2025', 'status': 'complete',
                    'scoring_settings': {'pass_yd': .04}, 'roster_positions': ['QB', 'BN']},
            'rosters': [{'roster_id': 1, 'owner_id': 'previous-manager', 'players': ['3'], 'settings': {'wins': 1, 'losses': 13}},
                        {'roster_id': 2, 'owner_id': 'other-manager', 'players': ['1', '2', '4'], 'settings': {'wins': 13, 'losses': 1}}],
            'users': [{'user_id': 'previous-manager', 'display_name': 'Previous Manager'},
                      {'user_id': 'other-manager', 'display_name': 'Continuing Manager'}],
            'transactions': {str(w): past if w == 1 else [] for w in range(19)},
            'drafts': [], 'draft_picks': [], 'traded_picks': [], 'matchups': {},
            'winners_bracket': [], 'losers_bracket': []}
        self.cache.write(self.cache.normalize('league-1', 2025, facts))
        self.history.update_current('league-1', self.data)
        async def prepared():
            return None
        self.editor.app.include_router(create_historical_assets_router(league_id='league-1',
            require_data=lambda: self.data, page=lambda title, body: HTMLResponse(body)))
        self.editor.app.include_router(create_transactions_router(ensure_fresh=prepared,
            refresh_transactions=prepared, require_data=lambda: self.data, state={},
            page=lambda title, body: HTMLResponse(body)))
        self.client = self.editor.client

    @staticmethod
    def trade(tid, stamp, player, sender, receiver):
        from datetime import datetime
        milliseconds = int(datetime.fromisoformat(stamp).timestamp() * 1000)
        return {'transaction_id': tid, 'type': 'trade', 'status': 'complete', 'roster_ids': [1, 2],
            'adds': {player: receiver}, 'drops': {player: sender}, 'created': milliseconds,
            'status_updated': milliseconds + 1000, 'draft_picks': [{'season': '2028', 'round': 1,
                'roster_id': 1, 'previous_owner_id': receiver, 'owner_id': sender}]}

    def close(self):
        self.stack.close()
        self.editor.doCleanups()


class HistoricalConsumerContinuityTests(unittest.TestCase):
    def setUp(self):
        self.f = HistoricalContinuityFixture()
        self.addCleanup(self.f.close)

    def test_current_source_bucket_survives_actual_private_archive_http_and_html(self):
        f = self.f
        response = f.client.get('/api/history/transactions?season=2026&week=0')
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()['records']
        self.assertEqual(len(rows), 6)
        trade = next(row for row in rows if row['sleeper_transaction_id'] == 'now-trade')
        self.assertEqual(trade['week'], 0)
        self.assertEqual(trade['draft_picks'], f.now_trade['draft_picks'])
        page = f.client.get('/transactions?scope=current_season&week=0')
        self.assertEqual(page.status_code, 200, page.text)
        self.assertIn('now-trade', page.text)
        self.assertIn('2026 Week 0', page.text)
        dossier = f.client.get('/trades/history/now-trade')
        self.assertEqual(dossier.status_code, 200, dossier.text)
        self.assertIn('2028 Round 1', dossier.text)
        self.assertNotIn('past-0', page.text)
        all_history = f.client.get('/api/history/transactions').json()['records']
        self.assertEqual(len([row for row in all_history if row['season'] == 2025]), 5)
        self.assertEqual(len([row for row in all_history if row['season'] == 2026]), 6)
        evidence('history-http', {'scope': 'Two fictional source seasons through canonical cache, graph, authorized HTTP and HTML',
            'week_zero_response': response.json(), 'historical_records': all_history, 'html_contains_recovered_transaction': True})

    def test_previous_owner_decisions_are_franchise_history_not_successor_history(self):
        from src.core.gm_behavioral_intelligence.diagnostics import LeagueGMObservations
        report = LeagueGMObservations(self.f.cache).report(self.f.data)
        self.assertEqual(report['teams']['1']['franchise']['trades'], 6)
        self.assertEqual(report['teams']['1']['manager']['trades'], 0)
        self.assertEqual(report['teams']['2']['manager']['trades'], 5)
        activity = report['activity']['total']
        self.assertEqual(activity['completed_waivers'], 1)
        self.assertEqual(activity['waiver_attempts']['failed'], 2)
        self.assertEqual(activity['completed_drops'], 6)  # Completed trade departures only.
        self.assertEqual(activity['faab_spent'], 0)
        self.assertEqual(activity['other_attempts']['pending'], 1)
        self.assertEqual(activity['other_attempts']['unknown'], 1)
        seasons = {r['season']: r['payload'] for r in self.f.history.records('league-1', 'league_season', limit=None)[1]}
        self.assertEqual(seasons[2025]['scoring_settings']['pass_yd'], .04)
        self.assertEqual(seasons[2026]['scoring_settings']['pass_yd'], .05)
        evidence('manager-and-activity', {'report': report, 'season_rules': seasons,
            'scope': 'Fictional multi-season ownership and transactions; no grade or intent inferred'})

    def test_repeated_reads_make_no_provider_or_analytical_writes_and_scope_does_not_leak(self):
        f = self.f
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in f.cache.root.glob('*.gz')}
        with patch('services.sleeper.sleeper_get', side_effect=AssertionError('provider')):
            for _ in range(3):
                self.assertEqual(f.client.get('/api/history/transactions?week=0').status_code, 200)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in f.cache.root.glob('*.gz')})
        f.editor.store.upsert_membership('account-a', {'league_id': 'other-L', 'season': '2026'},
            'account-a', 1, 'Other franchise', 'active')
        f.editor.store.activate('account-a', 'other-L')
        # Personal context must reject a stale page scoped to the old source.
        self.assertEqual(f.client.get('/api/my-dtos').status_code, 403)
        self.assertEqual(f.history.records('other-L', 'trade', limit=None)[0], 0)

    def test_historical_source_http_records_reach_canonical_draft_and_transaction_consumers(self):
        import asyncio
        import httpx
        from src.core.intelligence_memory.sleeper_source import SleeperHistoricalSource
        f = self.f
        facts = deepcopy(f.cache.read('league-1', 2025).facts)
        draft = {'draft_id': 'rookie-D', 'league_id': 'prior-L', 'status': 'complete',
            'type': 'linear', 'start_time': 1745715619387,
            'settings': {'rounds': 3}, 'draft_order': {'previous-manager': 1, 'other-manager': 2}}
        # Selecting roster 2 is deliberately distinct from the traded original 1.
        selection = {'draft_id': 'rookie-D', 'player_id': '2', 'roster_id': 2,
            'round': 1, 'draft_slot': 1, 'pick_no': 1, 'picked_by': 'other-manager'}
        paths = []
        def upstream(request):
            path = request.url.path.removeprefix('/v1')
            paths.append(path)
            if path == '/league/prior-L':
                value = facts['league']
            elif '/transactions/' in path:
                value = facts['transactions'].get(path.rsplit('/', 1)[-1], [])
            elif '/matchups/' in path:
                value = []
            elif path == '/league/prior-L/drafts':
                value = [draft]
            elif path == '/draft/rookie-D':
                value = draft
            elif path == '/draft/rookie-D/picks':
                value = [selection]
            else:
                value = facts.get(path.rsplit('/', 1)[-1], [])
            return httpx.Response(200, json=value)
        real_client = httpx.AsyncClient
        def client(**kwargs):
            return real_client(**kwargs, transport=httpx.MockTransport(upstream))
        with patch('src.core.intelligence_memory.sleeper_source.httpx.AsyncClient', side_effect=client):
            acquired = asyncio.run(SleeperHistoricalSource().completed_season_facts('prior-L', 2025))
        f.cache.write(f.cache.normalize('league-1', 2025, acquired))
        rows = f.client.get('/api/history/transactions?season=2025').json()['records']
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row['week'] == 1 for row in rows))
        self.assertEqual(rows[0]['draft_picks'][0]['roster_id'], 1)
        picks = f.history.records('league-1', 'draft_pick', limit=None)[1]
        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0]['payload']['selecting_roster_id'], 2)
        self.assertEqual(picks[0]['payload']['player_id'], '2')
        self.assertIn('/league/prior-L/transactions/0', paths)
        self.assertIn('/league/prior-L/transactions/18', paths)
        evidence('historical-source-http', {'scope': 'Disposable JSON HTTP transport; real SleeperHistoricalSource, cache and canonical consumers',
            'requested_paths': paths, 'transaction_records': rows, 'draft_records': picks})


class MyTeamActivityContinuityTests(unittest.TestCase):
    @staticmethod
    def fixture():
        from tests import test_my_team_outlook_http as outlook
        f = outlook.MyTeamOutlookHTTPTests('test_actual_my_team_takeaway_precedes_roster_and_capital')
        f.setUp()
        player = next(iter(f.data['players']))
        f.data['transactions'] = [{'transaction_id': 'activity-' + str(i), 'type': kind,
            'status': status, 'roster_ids': [1], 'created': 1790000000000 + i,
            'adds' if kind == 'waiver' else 'drops': {player: 1}, 'settings': {'waiver_bid': 0}}
            for i, (kind, status) in enumerate([('waiver', 'complete'), ('waiver', 'failed'),
                ('waiver', 'pending'), ('waiver', 'cancelled'), ('drop', 'failed'), ('drop', None)])]
        return f

    def test_actual_my_team_http_distinguishes_completed_actions_from_attempts(self):
        from services.team_headquarters import _timeline
        f = self.fixture()
        self.addCleanup(f.doCleanups)
        original = deepcopy(f.data['transactions'])
        response = f.client.get('/teams/1')
        self.assertEqual(response.status_code, 200, response.text)
        for label in ('Failed waiver attempt', 'Pending waiver attempt', 'Cancelled waiver attempt',
                      'Failed drop attempt', 'Unknown-status drop attempt'):
            self.assertIn(label, response.text)
        rows = _timeline(f.data, 1)
        self.assertEqual([r['actions'] for r in rows].count('1 added'), 1)
        self.assertEqual([r['actions'] for r in rows].count('No completed roster move verified'), 5)
        self.assertEqual(f.data['transactions'], original)
        evidence('my-team-activity', {'scope': 'Disposable authenticated actual My Team producer and HTML route',
            'source_statuses': [r['status'] for r in original], 'timeline': rows, 'status': response.status_code})
