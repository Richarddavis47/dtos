"""Presentation must not mutate prepared facts, saved intent or start analysis."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from components.asset_intelligence import player_dossier
from services.asset_explanations import player_profile_explanation
from src.core.asset_intelligence import AssetContext, evaluate_player
from tests import test_personal_rankings_store as store_fixtures


class FinalPresentationPreservationTests(unittest.TestCase):
    def test_repeated_dossier_render_preserves_typed_facts_and_saved_intent_without_work(self):
        owner = {'roster_id': 1, 'owner': 'Fixture Manager', 'team_name': 'Fixture Team'}
        context = AssetContext('fixture-league', 1, {'roster_positions': ['QB', 'SUPER_FLEX']})
        source = {'id': 'fixture-qb', 'full_name': 'Fixture Quarterback', 'position': 'QB',
                  'team': 'BUF', 'age': 24, 'bye_week': 7, 'status': 'Active'}
        report = evaluate_player(source, context)
        store = store_fixtures.PersonalRankingsStoreTests()
        store.setUp()
        self.addCleanup(store.doCleanups)
        intent = store_fixtures.document()
        intent['order'].reverse()
        intent['preferences'] = {'player:1': {'target': True}, 'player:2': {'avoid': True}}
        store.save(intent)
        facts_before = store.facts()
        files_before = {str(p.relative_to(store.folder.name)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in Path(store.folder.name).iterdir() if p.is_file()}
        originals = deepcopy((report, owner, context, source))
        # These guards are active only for formatting already-prepared reports.
        # Acquisition/preparation is intentionally outside this read boundary.
        boundaries = (
            'services.sleeper.sleeper_get',
            'src.core.intelligence.team_strength.prepare_for_data',
            'src.core.trade_intelligence.lineup.optimal_legal_lineup',
            'src.core.fois.service.FOISService._generate_sync',
            'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
            'services.trade_intelligence.generate_trade_workflow',
            'sqlite3.connect',
        )
        with ExitStack() as guards:
            guarded = {name: guards.enter_context(patch(name, side_effect=AssertionError(name)))
                       for name in boundaries}
            rendered = [(player_dossier(report, owner, [owner]),
                         player_profile_explanation(report, league_id=context.league_id))
                        for _ in range(20)]
        for item in rendered[1:]:
            self.assertEqual(item, rendered[0])
        for name, operation in guarded.items():
            self.assertEqual(operation.call_count, 0, name)
        self.assertEqual((report, owner, context, source), originals)
        self.assertIsInstance(report.profile.bye_week, str)
        self.assertEqual(report.profile.player_id, 'fixture-qb')
        for _ in range(20):
            self.assertEqual(store.load()['order'], intent['order'])
            self.assertEqual(store.load()['preferences'], intent['preferences'])
        self.assertEqual(store.facts(), facts_before)
        self.assertEqual({str(p.relative_to(store.folder.name)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in Path(store.folder.name).iterdir() if p.is_file()}, files_before)

    def test_zero_and_missing_prices_remain_distinct_after_rendering(self):
        source = {'id': 'fixture-player', 'full_name': 'Fixture Player', 'position': 'WR', 'team': 'BUF'}
        report = evaluate_player(source, AssetContext('fixture-league', 1, {}))
        owner = {'roster_id': 1, 'owner': 'Fixture Manager'}
        observed = []
        for price in (None, 0):
            value = replace(report.core_values.market, score=price)
            prepared = replace(report, core_values=replace(report.core_values, market=value))
            before = deepcopy(prepared)
            html = player_dossier(prepared, owner, [owner])
            observed.append(player_profile_explanation(prepared, league_id='fixture-league'))
            self.assertEqual(prepared, before)
            self.assertIs(prepared.core_values.market.score, price)
            if price is not None:
                self.assertIn('data-availability="available"', html)
                self.assertIn('<strong>0</strong>', html)
                self.assertEqual(next(e.display for e in observed[-1].evidence if e.key == 'market'), '0')
            else:
                self.assertFalse(any(e.key == 'market' for e in observed[-1].evidence))
        self.assertNotEqual(observed[0], observed[1])
