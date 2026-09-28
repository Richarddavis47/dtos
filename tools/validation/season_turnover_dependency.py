"""Private local acceptance probe; never changes retained fixtures/production.

Tests the historical-reader consequence of proposed eviction in an isolated
copy. A failed preservation check is a blocker, not permission to evict.
"""
import argparse
import asyncio
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch


def run(sources):
    reports = []
    with tempfile.TemporaryDirectory(prefix='dtos-turnover-reader-probe-') as folder:
        root = Path(folder)
        with patch.dict(os.environ, {'DTOS_METADATA_DB_FILE': str(root / 'metadata.db'),
                                    'DTOS_HISTORY_STORAGE_ROOT': str(root),
                                    'DTOS_SLEEPER_SEASON_CACHE_ROOT': str(root / 'seasons')}):
            from src.core.history_context.season_cache import SleeperSeasonCache
            from src.core.history_context import store as history
        cache = SleeperSeasonCache(root / 'seasons')
        cases = []
        for label, source in sources:
            archives = sorted(Path(source).glob('*/*.json.gz'))
            if not archives:
                raise ValueError('Retained local season fixture unavailable')
            identities = []
            for archive in archives:
                raw = archive.read_bytes()
                payload = json.loads(gzip.decompress(raw))
                normalized = cache.normalize(payload['league_id'], payload['season'], payload['facts'])
                if normalized.checksum != payload['checksum']:
                    raise ValueError('Retained fixture checksum mismatch')
                cache.write(normalized)
                identities.append({'league': normalized.league_id, 'season': normalized.season,
                                   'checksum': normalized.checksum,
                                   'fixture_sha256': hashlib.sha256(raw).hexdigest(),
                                   'source_league': str(normalized.facts['league'].get('league_id'))})
            cases.append((label, sorted(identities, key=lambda item: item['season'])))
        with patch.object(history, 'sleeper_season_cache', cache):
            reader = history.CanonicalHistoryStore()
            for label, identities in cases:
                oldest, newest = identities[0], identities[-1]
                league, season = oldest['league'], oldest['season']
                original = cache.read(league, season)
                reader.preserve_reader_checkpoint(league, season, current_season=newest['season'] + 1)
                from src.core.history_context.recovery import HistoricalCheckpoints, HistoricalRecoveryUnavailable
                checkpoints = HistoricalCheckpoints(cache.root)
                checkpoint = checkpoints.read(league, season)
                families = checkpoint['families']
                def fingerprint(selected_reader):
                    return {kind: {'count': result[0], 'digest': checkpoints.digest(result[1]),
                                   'semantic_set_digest': checkpoints.semantic_digest(result[1])}
                            for kind in families
                            for result in [selected_reader.records(league, kind, season=season, limit=None)]}
                before = fingerprint(reader)
                prior = reader.records(league, None, season=newest['season'], limit=None)
                size = cache.path(league, season).stat().st_size
                # This path is inside the newly created isolated temporary
                # directory; the retained source fixtures remain untouched.
                cache.delete(league, season)
                immediately = fingerprint(reader)
                restarted_cache = SleeperSeasonCache(cache.root)
                with patch.object(history, 'sleeper_season_cache', restarted_cache):
                    restarted = history.CanonicalHistoryStore()
                    after = fingerprint(restarted)
                    prior_preserved = prior == restarted.records(league, None, season=newest['season'], limit=None)
                    async def offline(*args):
                        raise OSError('simulated temporary upstream outage')
                    outage = asyncio.run(restarted.recover_historical_season(league, season, offline))
                    outage_equal = fingerprint(restarted) == before
                    from src.core.history_context.recovery import FAMILIES
                    excluded = {}
                    for family in sorted(FAMILIES - set(families)):
                        if family not in families:
                            try:
                                restarted.records(league, family, season=season)
                            except HistoricalRecoveryUnavailable:
                                excluded[family] = 'explicit_unavailable_requires_source_recovery'
                    async def replay_source(source_league, source_season):
                        assert (source_league, source_season) == (oldest['source_league'], season)
                        return original.facts
                    recovery = asyncio.run(restarted.recover_historical_season(league, season, replay_source))
                restored = fingerprint(reader)
                reports.append({'league_label': label, 'season': season,
                                'source_identity': oldest, 'temporary_cache_bytes': size,
                                'covered_families': families, 'explicit_excluded_families': excluded,
                                'before': before, 'immediately_after_eviction': immediately,
                                'after_proposed_eviction_and_restart': after,
                                'after_local_restore': restored, 'prior_season_preserved': prior_preserved,
                                'historical_truth_visible_after_eviction': before == immediately == after == restored,
                                'temporary_outage': outage, 'outage_fingerprints_equal': outage_equal,
                                'rebuild_from_retained_source_replay': recovery,
                                'canonical_checkpoint_bytes': checkpoints.path(league, season).stat().st_size,
                                'cache_files_after_rebuild': len(cache.available_seasons(league)),
                                'original_fixture_unchanged': all(
                                    hashlib.sha256(path.read_bytes()).hexdigest() == identity['fixture_sha256']
                                    for identity in identities
                                    for path in Path(dict(sources)[label]).glob(f"*/{identity['season']}.json.gz")),
                                'upstream_refetch_exercised': False})
        accepted = all(row['historical_truth_visible_after_eviction']
                       and row['outage_fingerprints_equal'] and row['prior_season_preserved']
                       and row['rebuild_from_retained_source_replay']['state'] == 'cached'
                       for row in reports)
        return {'scope': 'retained historical fixtures; Day Traders identity sanitized; no live upstream or production access',
                'cases': reports, 'turnover_acceptance': all(row['historical_truth_visible_after_eviction']
                    and row['outage_fingerprints_equal'] and row['prior_season_preserved'] for row in reports),
                'acceptance_scope': 'Every family supported by each retained source fixture; unsupported families explicitly unavailable',
                'whole_season_eviction_safe_in_local_rehearsal': accepted,
                'production_eviction_authorized': False,
                'remaining': 'Live provider equality and production retention admission are release/production acceptance work.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--day-traders', type=Path, required=True)
    parser.add_argument('--super-flexxxin', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run([('Day Traders', args.day_traders), ('Super Flexxxin', args.super_flexxxin)])
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['turnover_acceptance'] else 1)
