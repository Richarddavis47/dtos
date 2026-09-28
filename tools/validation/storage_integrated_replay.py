"""Private shared-store synthetic interaction proof, not an annual forecast."""
import argparse
import asyncio
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts
from src.core.fois.repository import FOISRepository
from src.core.fois import retention as fois_retention
from src.core.history_context import store as history
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint, ProvenanceType, SourceObservation,
)
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence import retention, provenance_retention
from src.platform.storage_accounting import collect
from src.platform.durable_storage_monitor import DurableStorageMonitor


def fingerprints(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def run():
    with tempfile.TemporaryDirectory(prefix='dtos-integrated-storage-') as folder:
        root = Path(folder)
        projection_path, fois_path, event_path = (root / name for name in ('p.db', 'f.db', 'e.db'))
        repo = FOISRepository(fois_path)
        with repo._connection() as db, db:
            fois_retention.admit(db, expected_digest=fois_retention.inventory_digest(db))
        events = IntelligenceCheckpointStore(event_path)
        pipeline = CheckpointPipeline(IntelligenceMemoryService(events))
        cache = SleeperSeasonCache(root / 'seasons')
        monitor = DurableStorageMonitor(root / 'monitor.json')
        reader = history.CanonicalHistoryStore()
        last, annual = {}, []
        with patch.object(history, 'sleeper_season_cache', cache):
            for year in range(2026, 2033):
                for league in ('synthetic-A', 'synthetic-B'):
                    service = ProjectionService(projection_path, league_id=league)
                    score = FOISEngine().evaluate(FOISFacts(league, league + ':1', 'gm', ()),
                                                  generated_at=f'{year}-09-01T00:00:00+00:00')
                    score = replace(score, score_key=f'{league}:{year}:gm',
                                    evaluation_start_season=year, evaluation_end_season=year)
                    data = {'league': {'league_id': league, 'season': year,
                                      'scoring_settings': {'pass_yd': .04 if league.endswith('A') else .05}},
                            'players': [{'id': 'q', 'position': 'QB'}], 'week': 1}
                    for change in range(12):
                        minute = change + (0 if league.endswith('A') else 12)
                        at = f'{year}-09-01T00:{minute:02}:00+00:00'
                        feed = {week: [{'player_id': 'q', 'season': year, 'week': week,
                                        'stats': {'pass_yd': 200 + change}}] for week in (1, 2, 3)}
                        with patch('src.core.projection_intelligence.service._now', return_value=at):
                            snapshot = service.publish_horizon(feed, data=data, league_id=league,
                                                               season=year, current_week=1)
                        if year == 2026 and league.endswith('A') and change == 0:
                            with closing(sqlite3.connect(projection_path)) as db, db:
                                roots, _ = retention.plan(db)
                                provenance_retention.admit(db, expected_digest=provenance_retention.plan(db, roots)['digest'])
                                retention.collect(db)
                        assessment = replace(score, overall_score=70 + change // 4,
                                             overall_letter_grade='B', brain_snapshot_id=at)
                        repo.save(assessment, at)
                        event = {'transaction_id': f'{league}:{year}:{change}', 'status': 'complete',
                                 'type': 'trade' if change % 2 else 'waiver',
                                 'created': f'{year}-09-02T00:00:00+00:00', 'adds': {'q': 1}}
                        data['projection_intelligence'] = snapshot
                        pipeline.ingest_transactions(data, [event])
                        market_time = f'{year}-09-01T00:{change:02}:00+00:00'
                        market = IntelligenceCheckpoint(
                            checkpoint_id=f'market:{year}:{change}', asset_id='player:q', asset_type='player',
                            timestamp=market_time, season=year, trigger_type=CheckpointTrigger.SEASON_START,
                            provenance_type=ProvenanceType.LIVE_CAPTURED, market_value=5000 + change * 100,
                            confidence=90, evidence_completeness=EvidenceCompleteness.COMPLETE,
                            model_version='synthetic-interaction-1', related_event_id=f'market:{year}:{change}')
                        quote = SourceObservation(
                            provider='SyntheticExternalMarket', raw_value=market.market_value,
                            normalized_value=market.market_value, observed_at=market_time,
                            source_identity=f'market-source:{year}:{change}', temporal_distance_seconds=0,
                            metadata={'scope': 'global', 'format': '12-team-2qb-ppr'})
                        events.put_sparse(market, market_context_id='global:12-team-2qb-ppr', provider_evidence=(quote,))
                    facts = {'league': {'league_id': f'{league}:{year}', 'season': str(year)},
                             'users': [], 'rosters': [], 'transactions': {}}
                    async def fetch(source, season):
                        return {'league': {'league_id': source, 'season': str(season)},
                                'users': [], 'rosters': [], 'transactions': {}}
                    asyncio.run(reader.publish_with_verified_turnover(
                        league, year, cache.normalize(league, year, facts), fetch))
                    assert len(cache.available_seasons(league)) <= 6
                    last[league] = (data, feed, at, assessment, event, snapshot)
                totals, scopes = collect(projection=projection_path, fois=fois_path, events=event_path,
                                         cache_paths=list(cache.root.glob('*/*.json.gz')), disk_root=root)
                assert set(scopes) == set(last), 'Cross-league accounting scope mismatch'
                monitor.record(totals, scopes, now=datetime(year, 9, 3, tzinfo=timezone.utc))
                annual.append({'season': year, 'file_bytes': sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                               'measured_counters': totals})
            # Restart services and use the exact accepted inputs, in reverse
            # league order. No source payload is copied into the report.
            restart_before_bytes = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
            restarted_services = {league: ProjectionService(projection_path, league_id=league) for league in last}
            restarted_repo = FOISRepository(fois_path)
            restarted_pipeline = CheckpointPipeline(IntelligenceMemoryService(IntelligenceCheckpointStore(event_path)))
            restart_growth_bytes = sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) - restart_before_bytes
            before = fingerprints(root)
            for _ in range(100):
                for league, (data, feed, at, assessment, event, snapshot) in reversed(list(last.items())):
                    service = restarted_services[league]
                    with patch('src.core.projection_intelligence.service._now', return_value=at):
                        actual = service.publish_horizon(feed, data=data, league_id=league,
                                                         season=2032, current_week=1)
                    assert actual['projection_snapshot_id'] == snapshot['projection_snapshot_id']
                    restarted_repo.save(assessment, at)
                    restarted_pipeline.ingest_transactions(data, [event])
                    events.put_sparse(market, market_context_id='global:12-team-2qb-ppr', provider_evidence=(quote,))
            after = fingerprints(root)
            assert after == before, ('Unchanged shared-store replay changed: ' + ', '.join(
                name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)))
        return {'scope': 'two synthetic leagues, shared stores, seven seasons, twelve changes per season',
                'annual_observations': annual, 'unchanged_100_replays_byte_identical': True,
                'restart_file_growth_bytes': restart_growth_bytes,
                'restart_and_league_isolation': True, 'maximum_raw_seasons_per_league': 6,
                'global_market_observations': events.market_memory_health()['observation_count'],
                'limitations': ['Not a measured real-league annual forecast or universal boundedness proof.',
                               'Source outage remains a separately validated component.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PASS shared-store interaction/replay rehearsal; private report saved')
