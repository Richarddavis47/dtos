"""Compact historical reader checkpoints; never a raw season archive.

Explicitly prepared before cache eviction, immutable per observed season.
Coverage is family-specific: only families supported by the retained source
are preserved, and unsupported families remain explicitly unavailable.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zlib

from src.platform.storage_gate import database_gate

FAMILIES = frozenset({
    'league_season', 'franchise_identity', 'roster_snapshot', 'season_standing',
    'player_week', 'matchup', 'trade', 'transaction', 'draft', 'draft_pick',
    'pick_snapshot', 'playoff_bracket', 'playoff_result',
})
MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_STORED_BYTES = 2 * 1024 * 1024
VERSION = 'historical-reader-checkpoint-1'


class HistoricalRecoveryUnavailable(ValueError):
    pass


class HistoricalCheckpoints:
    def __init__(self, cache_root):
        self.root = Path(cache_root) / '.canonical-reader-checkpoints'

    def path(self, league, season):
        scope = hashlib.sha256(str(league).encode()).hexdigest()
        return self.root / scope / f'{int(season)}.checkpoint'

    def read(self, league, season):
        path = self.path(league, season)
        if not path.exists():
            return None
        if path.is_symlink() or path.stat().st_size > MAX_STORED_BYTES:
            raise HistoricalRecoveryUnavailable('Checkpoint file admission violation')
        decoder = zlib.decompressobj()
        raw = decoder.decompress(path.read_bytes(), MAX_RAW_BYTES + 1)
        if len(raw) > MAX_RAW_BYTES or not decoder.eof or decoder.unused_data:
            raise HistoricalRecoveryUnavailable('Checkpoint decoded size/format violation')
        payload = json.loads(raw)
        if (payload.get('version') != VERSION or payload.get('league_id') != str(league)
                or payload.get('season') != int(season)):
            raise HistoricalRecoveryUnavailable('Checkpoint historical scope mismatch')
        rows = payload['records']
        if not set(payload['families']) <= FAMILIES or any(
               row['league_id'] != str(league) or row['season'] != int(season)
               or row['entity_type'] not in payload['families'] for row in rows):
            raise HistoricalRecoveryUnavailable('Checkpoint record scope mismatch')
        if payload['record_digest'] != self.digest(rows):
            raise HistoricalRecoveryUnavailable('Checkpoint checksum mismatch')
        return payload

    @staticmethod
    def digest(rows):
        return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @staticmethod
    def semantic_digest(rows):
        """Order-independent record-set identity, separate from reader sequence.

        Keep all canonical record fields, including temporal knowledge/provenance.
        Only explicit transient cache bookkeeping is excluded. Never deduplicate
        silently: a duplicate natural record key invalidates this comparison.
        """
        identities = [row['record_key'] for row in rows]
        if len(identities) != len(set(identities)):
            raise HistoricalRecoveryUnavailable('Duplicate historical record identity')
        transient = {'cache_path', 'cache_generation', 'cache_rebuilt_at'}
        canonical = sorted(({key: value for key, value in row.items() if key not in transient}
                            for row in rows), key=lambda row: row['record_key'])
        return HistoricalCheckpoints.digest(canonical)

    def index(self, league):
        directory = self.path(league, 2000).parent
        result = {}
        for path in sorted(directory.glob('*.checkpoint')):
            season = int(path.stem)
            result[season] = self.read(league, season)['source_checksum']
        return result

    def preserve(self, *, league, season, source_league, source_checksum, records, families=FAMILIES):
        families = frozenset(families)
        if not families or not families <= FAMILIES:
            raise HistoricalRecoveryUnavailable('Unsupported checkpoint family coverage')
        # Preserve the captured reader sequence: callers paginate this output.
        # Lexical key sorting changes roster 1,2,...,10 into 1,10,2,... and
        # changes provider transaction sequence. Set identity is checked apart.
        records = [row for row in records if row['entity_type'] in families]
        self.semantic_digest(records)
        if not source_league or not source_checksum:
            raise HistoricalRecoveryUnavailable('Missing source identity')
        if any(row['league_id'] != str(league) or row['season'] != int(season) for row in records):
            raise HistoricalRecoveryUnavailable('Cross-scope checkpoint rejected')
        payload = {'version': VERSION, 'league_id': str(league), 'season': int(season),
                   'source_league_id': str(source_league), 'source_checksum': source_checksum,
                   'families': sorted(families), 'records': records,
                   'record_digest': self.digest(records),
                   'roster_precision': 'seasonal_provider_anchor_not_transaction_time'}
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        compressed = zlib.compress(raw)
        if len(raw) > MAX_RAW_BYTES or len(compressed) > MAX_STORED_BYTES:
            raise HistoricalRecoveryUnavailable('Checkpoint size requires review')
        path = self.path(league, season)
        with database_gate(path, exclusive=True):
            existing = self.read(league, season)
            if existing is not None:
                same_metadata = all(existing.get(key) == value for key, value in payload.items()
                                    if key not in {'records', 'record_digest'})
                if not same_metadata or self.semantic_digest(existing['records']) != self.semantic_digest(records):
                    raise HistoricalRecoveryUnavailable('Historical checkpoint changed; explicit reconciliation required')
                return False
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(compressed)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return True
