"""Prepared Player/Card reads preserve persisted projection evidence."""
import copy
from contextlib import closing
import json
import sqlite3
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from services.player_projection_view import player_projection_view, player_projection_views
from src.ui.design_system import player_summary
from src.ui.player_projections import player_projection_panel
from src.core.trade_intelligence.horizon_impact import evaluate_horizon_impact
from tests import test_batch5_trade_horizons as trade_fixtures


class PlayerReadContractTests(trade_fixtures.TradeHorizonTests):
    # Inherit the established prepared trade/strength fixture and its safety
    # checks; no new pricing/projection method is introduced.
    def test_player_card_dossier_team_trade_share_exact_week_evidence(self):
        pinned = self.service.snapshot()
        impact = evaluate_horizon_impact(self.data, self.proposal(), self.service)
        for week in (2, 3):
            for side in impact['sides'].values():
                for entry in side['weekly'][week]['pre']['optimal']['entries']:
                    pid = entry['asset_id']
                    canonical = self.service.week_snapshot(week, generation_snapshot=pinned)['players'][pid]['canonical_projection']
                    view = player_projection_view(self.data, pid, self.service, week)
                    self.assertEqual(view['value'], canonical)
                    self.assertEqual(entry['projected_points'], canonical)
                    card = player_summary(player_id=pid, name=pid, position='QB', nfl_team=None, projection=view)
                    self.assertIn('Sleeper ' + view['display'], card)
                    self.assertIn('>' + view['display'] + '</strong>', player_projection_panel(view))

    def test_100_browse_card_reads_no_growth_or_reconstruction(self):
        path = Path(self.service._database_file)
        files = [Path(str(path) + suffix) for suffix in ('', '-wal', '-shm')]
        tables = ('projection_snapshots', 'projection_player_states', 'projection_source_history')
        def disk():
            with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as connection:
                counts = {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables}
            return counts, [f.stat().st_size if f.exists() else 0 for f in files]
        before, original = disk(), copy.deepcopy(self.data)
        timings = {'card_list_seconds': [], 'dossier_week_panel_seconds': []}
        with patch.object(self.service, 'publish_horizon', side_effect=AssertionError('UI publication')), \
                patch('src.core.intelligence.team_strength.prepare_team_strength', side_effect=AssertionError('UI strength rebuild')), \
                patch('src.core.intelligence.orchestrator.IntelligenceOrchestrator.analyze', side_effect=AssertionError('UI intelligence construction')):
            for index in range(100):
                week = 2 + index % 2
                start = perf_counter()
                views = player_projection_views(self.data, ['a', 'b', 'c', 'd'], self.service, week)
                for pid, view in views.items():
                    player_summary(player_id=pid, name=pid, position='QB', nfl_team=None, projection=view)
                timings['card_list_seconds'].append(perf_counter() - start)
                start = perf_counter()
                player_projection_panel(player_projection_view(self.data, 'a', self.service, week))
                timings['dossier_week_panel_seconds'].append(perf_counter() - start)
        self.assertEqual(disk(), before)
        self.assertEqual(self.data, original)
        print(json.dumps({'scope': 'four-player durable fixture; projection contribution only, not parent-page latency',
                          'iterations': 100, 'row_file_growth': 0,
                          'max_seconds': {key: max(values) for key, values in timings.items()}}))
