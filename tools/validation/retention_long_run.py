"""Local temporary-store comparison; never connects to production.

Run with --output pointing to a private report. Small synthetic players are not
a measurement of real-league annual bytes; report those limits explicitly.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts
from src.core.fois.repository import FOISRepository
from src.core.fois import retention as fois_retention
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence import retention, provenance_retention


def measure(path, tables):
    with closing(sqlite3.connect(path)) as db:
        return {'file_bytes': path.stat().st_size,
                'reusable_bytes': db.execute('PRAGMA freelist_count').fetchone()[0]
                * db.execute('PRAGMA page_size').fetchone()[0],
                'rows': {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                         for table in tables}}


def run(*, seasons=4, changes=90):
    reports = {}
    with tempfile.TemporaryDirectory(prefix='dtos-retention-rehearsal-') as folder:
        for admitted in (False, True):
            root = Path(folder) / str(admitted)
            root.mkdir()
            projection_path = root / 'projection.sqlite3'
            projection = ProjectionService(projection_path, league_id='synthetic')
            repo = FOISRepository(root / 'fois.sqlite3')
            if admitted:
                with repo._connection() as db, db:
                    fois_retention.admit(db, expected_digest=fois_retention.inventory_digest(db))
            phase_rows = []
            for season_index in range(seasons):
                year = 2026 + season_index
                score = FOISEngine().evaluate(FOISFacts('synthetic', 'synthetic:1', 'gm', ()),
                                             generated_at=f'{year}-09-01T00:00:00+00:00')
                score = replace(score, evaluation_start_season=year, evaluation_end_season=year,
                                score_key=f'synthetic:{year}:gm')
                for change in range(changes):
                    at = (datetime(year, 9, 1, tzinfo=timezone.utc) + timedelta(minutes=change)).isoformat()
                    data = {'league': {'league_id': 'synthetic', 'season': year,
                                       'scoring_settings': {'pass_yd': .04}},
                            'players': [{'id': 'q', 'position': 'QB'}], 'week': 1}
                    feed = {week: [{'player_id': 'q', 'season': year, 'week': week,
                                    'stats': {'pass_yd': 200 + change}}] for week in (1, 2, 3)}
                    with patch('src.core.projection_intelligence.service._now', return_value=at):
                        projection.publish_horizon(feed, data=data, league_id='synthetic',
                                                   season=year, current_week=1)
                    if admitted and season_index == 0 and change == 0:
                        with closing(sqlite3.connect(projection_path)) as db, db:
                            roots, _ = retention.plan(db)
                            plan = provenance_retention.plan(db, roots)
                            provenance_retention.admit(db, expected_digest=plan['digest'])
                            retention.collect(db)
                    # One real assessment change per 30 source refreshes; the
                    # intervening fingerprints do not change manager quality.
                    value = 70 + 5 * (change // 30)
                    repo.save(replace(score, overall_score=value, overall_letter_grade='B',
                                      brain_snapshot_id=f'{year}:{change}'), f'{year}:{change}')
                phase_rows.append({
                    'season': year,
                    'projection': measure(projection_path, ['projection_source_history', 'projection_snapshots', 'projection_player_states']),
                    'fois': measure(repo.path, ['fois_snapshot_history', 'fois_semantic_states']),
                })
            before = (projection_path.read_bytes(), repo.path.read_bytes())
            for _ in range(100):
                with patch('src.core.projection_intelligence.service._now', return_value=at):
                    projection.publish_horizon(feed, data=data, league_id='synthetic', season=year, current_week=1)
                repo.save(replace(score, overall_score=value, overall_letter_grade='B',
                                  brain_snapshot_id=f'{year}:{change}'), f'{year}:{change}')
            unchanged = before == (projection_path.read_bytes(), repo.path.read_bytes())
            assert unchanged, 'Unchanged replay altered durable database bytes'
            reports['hardened' if admitted else 'prior'] = {
                'seasons': phase_rows, 'unchanged_replay_byte_identical': unchanged,
            }
        final = reports['hardened']['seasons'][-1]
        assert final['projection']['rows']['projection_source_history'] <= min(seasons, 6) * 6
        assert final['fois']['rows']['fois_snapshot_history'] <= seasons * (8 + (changes + 29) // 30)
    return {'scenario': {'seasons': seasons, 'changes_per_season': changes,
                         'players': 1, 'weeks': 3, 'managers': 1},
            'limits': ['Synthetic structural proof, not real annual capacity.',
                       'Sparse event payloads, caches and Market/news ingress require separate proof.'],
            'results': reports}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--changes', type=int, default=90)
    parser.add_argument('--seasons', type=int, default=8)
    args = parser.parse_args()
    report = run(changes=args.changes, seasons=args.seasons)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
