"""Print bounded local storage evidence for Batch 7 transition preparation."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.history_context.metadata import MinimalMetadataStore  # noqa: E402
from src.core.projection_intelligence.service import ProjectionService  # noqa: E402


def payload(season: int, week: int, yards: int) -> list[dict]:
    return [{'player_id': 'q', 'season': season, 'week': week,
             'player': {'position': 'QB'}, 'stats': {'pass_yd': yards},
             'updated_at': '2026-09-01T12:00:00+00:00'}]


def file_bytes(path: Path) -> dict[str, int]:
    return {candidate.name: candidate.stat().st_size
            for candidate in sorted(path.parent.glob(path.name + '*'))}


def counts(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path)) as connection:
        return {table: connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                for table in ('projection_snapshots', 'projection_player_states',
                              'projection_source_history', 'sleeper_projection_snapshots',
                              'projection_publication_heads')}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='dtos-batch7-storage-') as directory:
        root = Path(directory)
        path = root / 'projection.sqlite3'
        league = {'league_id': 'storage-a', 'season': '2026',
                  'scoring_settings': {'pass_yd': .04}}
        data = {'league': league, 'season': 2026, 'week': 1,
                'scoring_settings': league['scoring_settings'],
                'players': {'q': {'id': 'q', 'position': 'QB', 'team': 'A'}}}
        service = ProjectionService(path, league_id='storage-a')
        first = service.publish_horizon({1: payload(2026, 1, 250)}, data=data,
                                        league_id='storage-a', season=2026, current_week=1)
        initial = {'files': file_bytes(path), 'rows': counts(path)}
        for _ in range(5):
            replay = service.publish_horizon({1: payload(2026, 1, 250)}, data=data,
                                             league_id='storage-a', season=2026, current_week=1)
            assert replay['horizon_generation'] == first['horizon_generation']
        unchanged = {'files': file_bytes(path), 'rows': counts(path)}
        changed = service.publish_horizon({1: payload(2026, 1, 300)}, data=data,
                                          league_id='storage-a', season=2026, current_week=1)
        changed_state = {'files': file_bytes(path), 'rows': counts(path)}
        restored = ProjectionService(path, league_id='storage-a')
        restart_data = {'league': league, 'season': 2026, 'week': 1,
                        'scoring_settings': league['scoring_settings']}
        assert restored.restore_into(restart_data)
        restarted = {'files': file_bytes(path), 'rows': counts(path)}

        metadata_path = root / 'metadata.sqlite3'
        metadata = MinimalMetadataStore(metadata_path)
        assert metadata.record_sync_generation('storage-a', 'g1')
        metadata_before = file_bytes(metadata_path)
        assert not metadata.record_sync_generation('storage-a', 'g1')
        metadata_after = file_bytes(metadata_path)
        print(json.dumps({
            'scope': 'temporary local synthetic semantic projection transition; no production data',
            'unchanged_replay_count': 5,
            'initial': initial,
            'unchanged': unchanged,
            'unchanged_growth_bytes': sum(unchanged['files'].values()) - sum(initial['files'].values()),
            'unchanged_row_growth': {key: unchanged['rows'][key] - initial['rows'][key] for key in initial['rows']},
            'changed': changed_state,
            'changed_generation': changed['horizon_generation'],
            'changed_growth_bytes': sum(changed_state['files'].values()) - sum(unchanged['files'].values()),
            'restart': restarted,
            'restart_growth_bytes': sum(restarted['files'].values()) - sum(changed_state['files'].values()),
            'sync_marker_unchanged_growth_bytes': sum(metadata_after.values()) - sum(metadata_before.values()),
            'durable_classification': {
                'projection_snapshots': 'canonical required, semantic identity deduplicated',
                'projection_player_states': 'bounded derived, content-addressed',
                'source_history': 'canonical required, semantic transitions only',
                'temporary_database': 'ephemeral validation and removed on exit',
            },
        }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
