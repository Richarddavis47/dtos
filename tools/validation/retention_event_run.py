"""Measure sparse trade/waiver checkpoint costs in temporary canonical stores."""
import argparse
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore


def run(decisions):
    with tempfile.TemporaryDirectory(prefix='dtos-event-retention-') as folder:
        path = Path(folder) / 'events.sqlite3'
        store = IntelligenceCheckpointStore(path)
        pipeline = CheckpointPipeline(IntelligenceMemoryService(store))
        start = path.stat().st_size
        years = []
        for year in (2026, 2027):
            known = f'{year}-09-01T00:00:00+00:00'
            data = {'league': {'league_id': 'synthetic', 'season': year}, 'week': 2,
                    'scoring_settings': {'rec': 1}, 'projection_intelligence': {
                        'league_id': 'synthetic', 'season': year, 'week': 2,
                        'scoring_settings': {'rec': 1}, 'scoring_profile_id': 'projection-fixture',
                        'projection_snapshot_id': f'g:{year}', 'generated_at': known,
                        'players': {str(n): {'season': year, 'week': 2, 'canonical_projection': 10 + n,
                            'generated_at': known, 'scoring_profile_id': 'projection-fixture',
                            'projection_snapshot_id': f'g:{year}', 'sleeper_evidence_fingerprint': f's:{year}'}
                                    for n in (1, 2)}}}
            for index in range(decisions):
                event = {'transaction_id': f'{year}:{index}', 'status': 'complete',
                         'type': 'trade' if index % 2 else 'waiver',
                         'created': f'{year}-09-02T00:00:00+00:00', 'adds': {'1': 1, '2': 1}}
                pipeline.ingest_transactions(data, [event])
            with closing(sqlite3.connect(path)) as db:
                count = db.execute('SELECT count(*) FROM intelligence_checkpoints').fetchone()[0]
            years.append({'year': year, 'database_bytes': path.stat().st_size, 'checkpoints': count})
        before = path.read_bytes()
        for _ in range(100):
            pipeline.ingest_transactions(data, [event])
        assert before == path.read_bytes()
        assert years[-1]['checkpoints'] == decisions * 4
        growth = years[1]['database_bytes'] - years[0]['database_bytes']
        return {'decisions_per_year': decisions, 'assets_per_decision': 2, 'start_bytes': start,
                'years': years, 'second_year_growth_bytes': growth,
                'bytes_per_asset_event': growth / (decisions * 2),
                'unchanged_100_replays_byte_identical': True,
                'scope': 'Synthetic compact projections; no real-source annual activity forecast.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'normal': run(100), 'heavy': run(1000)}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
