"""Disposable normalized Sleeper completed-season cache."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import threading
import sys
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class CachedSeason:
    league_id: str
    season: int
    status: str
    completeness: dict[str, str]
    facts: dict[str, Any]
    checksum: str


class SeasonSourceUnavailable(ValueError):
    """Retained evidence could not be decoded; the source is not an empty season."""


class SleeperSeasonCache:
    # Two idle runtime contexts x six retained seasons x three compact sections.
    # The separate 8 MiB object budget matches the existing historical memo's
    # small-footprint allowance; this is not a larger decoded-history cache.
    MAX_SECTIONS = 36
    MAX_RESIDENT_BYTES = 8 * 1024 * 1024
    MAX_CHECKSUMS = 12

    def __init__(self, root: Path):
        self.root = Path(root)
        self._checksum_lock = threading.RLock()
        self._checksum_cache = OrderedDict()
        self._section_cache = OrderedDict()
        self._section_sizes = {}
        self._resident_bytes = 0
        self._epoch = 0
        # Only cache refills/decodes serialize. Warm readers and publication do
        # not wait for reconstruction, and no provider call holds either lock.
        self._decode_lock = threading.RLock()
        self._counters = dict(evictions=0, oversized=0, hits=0, misses=0,
                              decodes=0, active_decodes=0, maximum_active_decodes=0)

    @staticmethod
    def _identity(path):
        stat = path.stat()
        return (int(stat.st_dev), int(stat.st_ino), int(stat.st_size), int(stat.st_mtime_ns))

    @staticmethod
    def _object_bytes(value):
        """Conservative Python object estimate; not RSS or serialized bytes."""
        seen, pending, total = set(), [value], 0
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            total += sys.getsizeof(item)
            if isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, (list, tuple)):
                pending.extend(item)
        return total

    def _drop(self, key):
        self._section_cache.pop(key, None)
        self._resident_bytes -= self._section_sizes.pop(key, 0)

    def _invalidate(self, path, identity=None):
        for key, row in tuple(self._section_cache.items()):
            if key[0] == path and (identity is None or row[0] != identity):
                self._drop(key)
        row = self._checksum_cache.get(path)
        if row is not None and (identity is None or row[0] != identity):
            self._checksum_cache.pop(path, None)

    def clear_resident(self):
        """Release cache ownership only; borrowed read-only objects stay valid.

        Epoch fencing prevents an already-running refill from repopulating the
        retired residency after shutdown/clear. There are no cache-owned workers.
        """
        with self._checksum_lock:
            self._epoch += 1
            self._section_cache.clear()
            self._section_sizes.clear()
            self._checksum_cache.clear()
            self._resident_bytes = 0

    def residency(self):
        with self._checksum_lock:
            return {**self._counters, 'sections': len(self._section_cache),
                    'checksums': len(self._checksum_cache), 'resident_bytes': self._resident_bytes,
                    'maximum_sections': self.MAX_SECTIONS,
                    'maximum_resident_bytes': self.MAX_RESIDENT_BYTES,
                    'maximum_checksums': self.MAX_CHECKSUMS}

    def _remember(self, path, identity, archive, epoch, names=('league', 'rosters', 'transactions'), *, checksum=False):
        # Size traversal is outside the short publication/metadata lock.
        rows = [(name, archive.facts.get(name)) for name in names]
        rows = [(name, value, self._object_bytes(value) + self._object_bytes((path, name, identity)))
                for name, value in rows]
        with self._checksum_lock:
            if epoch != self._epoch:
                return
            try:
                if self._identity(path) != identity:
                    return
            except FileNotFoundError:
                return
            self._invalidate(path, identity)
            if checksum:
                self._checksum_cache[path] = (identity, archive.checksum)
                self._checksum_cache.move_to_end(path)
                while len(self._checksum_cache) > self.MAX_CHECKSUMS:
                    self._checksum_cache.popitem(last=False)
            for name, value, size in rows:
                key = (path, name)
                self._drop(key)
                if size > self.MAX_RESIDENT_BYTES:
                    self._counters['oversized'] += 1
                    continue  # Complete evidence is returned, just not retained.
                while self._section_cache and (
                    len(self._section_cache) >= self.MAX_SECTIONS
                    or self._resident_bytes + size > self.MAX_RESIDENT_BYTES
                ):
                    self._drop(next(iter(self._section_cache)))
                    self._counters['evictions'] += 1
                self._section_cache[key] = (identity, value)
                self._section_sizes[key] = size
                self._resident_bytes += size

    def _cached_sections(self, path, names):
        with self._checksum_lock:
            try:
                identity = self._identity(path)
            except FileNotFoundError:
                self._invalidate(path)
                return None
            self._invalidate(path, identity)
            rows = {name: self._section_cache.get((path, name)) for name in names}
            if all(row is not None for row in rows.values()):
                for name in names:
                    self._section_cache.move_to_end((path, name))
                self._counters['hits'] += 1
                return {name: row[1] for name, row in rows.items()}
            return None

    @staticmethod
    def normalize(league_id: str, season: int, facts: dict[str, Any]) -> CachedSeason:
        supported = (
            "league", "users", "rosters", "matchups", "transactions", "drafts",
            "draft_picks", "traded_picks", "winners_bracket", "losers_bracket",
        )
        normalized = {key: facts.get(key) for key in supported if key in facts}
        completeness = {
            key: "available" if facts.get(key) is not None else "unavailable"
            for key in supported
        }
        for key in ("matchups", "transactions"):
            buckets = facts.get(key)
            if isinstance(buckets, dict) and any(value is None for value in buckets.values()):
                completeness[key] = "partial"
        available = sum(value == "available" for value in completeness.values())
        status = "complete" if available == len(supported) else (
            "partial" if available else "unavailable"
        )
        body = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
        return CachedSeason(str(league_id), int(season), status, completeness,
                            normalized, hashlib.sha256(body.encode()).hexdigest())

    def path(self, league_id: str, season: int) -> Path:
        namespace = hashlib.sha256(str(league_id).encode()).hexdigest()[:16]
        return self.root / namespace / f"{int(season)}.json.gz"

    # Retained for test/tool compatibility; canonical callers use ``path``.
    def _path(self, league_id: str, season: int) -> Path:
        return self.path(league_id, season)

    def available_seasons(self, league_id: str) -> tuple[int, ...]:
        """List cached seasons from bounded filenames without opening archives."""
        directory = self.path(league_id, 2000).parent
        if not directory.is_dir():
            return ()
        seasons: list[int] = []
        for candidate in directory.glob("*.json.gz"):
            try:
                seasons.append(int(candidate.name.removesuffix(".json.gz")))
            except ValueError:
                continue
        return tuple(sorted(seasons))

    def delete(self, league_id: str, season: int) -> None:
        path = self.path(league_id, season)
        path.unlink(missing_ok=True)
        with self._checksum_lock:
            self._invalidate(path)

    def write(self, season: CachedSeason, *, verified_evictions: dict[int, str] | None = None) -> Path:
        path = self.path(season.league_id, season.season)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "league_id": season.league_id, "season": season.season,
            "status": season.status, "completeness": season.completeness,
            "facts": season.facts, "checksum": season.checksum,
        }, sort_keys=True, separators=(",", ":")).encode()
        from src.platform.cache_budget import require_season, CacheAdmissionError
        from src.platform.storage_gate import database_gate
        compressed = gzip.compress(payload, compresslevel=6)
        temporary: str | None = None
        with self._checksum_lock:
            epoch = self._epoch
        try:
            with database_gate(self.root / '.season-cache-quota', exclusive=True):
                evictions = verified_evictions or {}
                for year, checksum in evictions.items():
                    old = self.read(season.league_id, year)
                    if year == season.season or old is None or old.checksum != checksum:
                        raise CacheAdmissionError('Verified turnover source changed before publication')
                require_season(path, self.root, len(compressed), excluded=[
                    self.path(season.league_id, year) for year in evictions])
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                    temporary = handle.name
                    handle.write(compressed)
                    handle.flush()
                    os.fsync(handle.fileno())
                identity = self._identity(Path(temporary))
                os.replace(temporary, path)
                # Publish successfully before removing recoverable old caches.
                # Failed admission/preparation therefore preserves every source.
                temporary = None
                for year in evictions:
                    self.delete(season.league_id, year)
            temporary = None
            self._remember(path, identity, season, epoch, checksum=True)
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
        return path

    @staticmethod
    def encoded_size(season: CachedSeason) -> int:
        payload = json.dumps({
            "league_id": season.league_id, "season": season.season,
            "status": season.status, "completeness": season.completeness,
            "facts": season.facts, "checksum": season.checksum,
        }, sort_keys=True, separators=(",", ":")).encode()
        return len(gzip.compress(payload, compresslevel=6))

    def read(self, league_id: str, season: int) -> CachedSeason | None:
        with self._decode_lock:
            with self._checksum_lock:
                epoch = self._epoch
                self._counters['active_decodes'] += 1
                self._counters['maximum_active_decodes'] = max(
                    self._counters['maximum_active_decodes'], self._counters['active_decodes'])
                self._counters['decodes'] += 1
            try:
                return self._read(league_id, season, epoch)
            finally:
                with self._checksum_lock:
                    self._counters['active_decodes'] -= 1

    def _read(self, league_id, season, epoch):
        path = self.path(league_id, season)
        try:
            before = path.stat()
        except FileNotFoundError:
            with self._checksum_lock:
                self._invalidate(path)
            return None
        try:
            payload = json.loads(gzip.decompress(path.read_bytes()))
        except (EOFError, gzip.BadGzipFile, zlib.error) as exc:
            # Do not repair, replace, delete or cache an unreadable publication.
            # Existing retained-source consumers handle a qualified ValueError.
            raise SeasonSourceUnavailable(
                'Sleeper retained season archive is unreadable; original source preserved.'
            ) from exc
        candidate = self.normalize(league_id, season, payload["facts"])
        if candidate.checksum != payload.get("checksum"):
            raise ValueError("Sleeper completed-season cache checksum mismatch.")
        stat = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns):
            raise ValueError('Sleeper completed-season publication changed during read')
        identity = (
            int(stat.st_dev), int(stat.st_ino), int(stat.st_size),
            int(stat.st_mtime_ns),
        )
        self._remember(path, identity, candidate, epoch)
        return candidate

    def section(self, league_id: str, season: int, name: str) -> Any:
        """Read a compact normalized section, reusing it while the archive is unchanged."""
        return self.sections(league_id, season, (str(name),)).get(str(name))

    def sections(self, league_id: str, season: int, names: tuple[str, ...]) -> dict[str, Any]:
        """Borrow read-only sections from one verified snapshot.

        Eviction drops cache references, never mutates a reader's objects. A
        miss reconstructs from the unchanged local archive, without providers
        or durable writes. Only one cold decode per cache instance runs at once.
        """
        path = self.path(league_id, season)
        values = self._cached_sections(path, names)
        if values is not None:
            return values
        with self._decode_lock:
            values = self._cached_sections(path, names)
            if values is not None:
                return values
            with self._checksum_lock:
                self._counters['misses'] += 1
            archive = self.read(league_id, season)
            return {name: archive.facts.get(name) for name in names} if archive is not None else {}

    def checksum_index(self, league_id: str) -> dict[int, str]:
        """Return verified archive identities without repeatedly decoding archives."""
        result: dict[int, str] = {}
        for season in self.available_seasons(league_id):
            path = self.path(league_id, season)
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            identity = (
                int(stat.st_dev), int(stat.st_ino), int(stat.st_size),
                int(stat.st_mtime_ns),
            )
            with self._checksum_lock:
                epoch = self._epoch
                cached = self._checksum_cache.get(path)
                if cached is not None and cached[0] == identity:
                    self._checksum_cache.move_to_end(path)
            if cached is not None and cached[0] == identity:
                result[season] = cached[1]
                continue
            archive = self.read(league_id, season)
            if archive is None:
                continue
            self._remember(path, identity, archive, epoch, names=(), checksum=True)
            result[season] = archive.checksum
        return result

    def prepared_checksum(self, league_id: str, season: int) -> str | None:
        """Return a verified publication identity without opening an archive.

        A byte-identical source refresh may replace the cache file. Its verified
        fact checksum, rather than the retrieval/write clock, remains canonical.
        Unknown or externally replaced files require normal verified preparation.
        """
        path = self.path(league_id, season)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        identity = (int(stat.st_dev), int(stat.st_ino), int(stat.st_size), int(stat.st_mtime_ns))
        with self._checksum_lock:
            cached = self._checksum_cache.get(path)
            return cached[1] if cached is not None and cached[0] == identity else None

    async def get_or_rebuild(
        self, league_id: str, season: int,
        fetch_facts: Callable[[str, int], Awaitable[dict[str, Any] | None]],
    ) -> CachedSeason:
        cached = self.read(league_id, season)
        if cached is not None:
            return cached
        facts = await fetch_facts(str(league_id), int(season))
        rebuilt = self.normalize(league_id, season, facts or {})
        if facts:
            self.write(rebuilt)
        return rebuilt

    def storage_estimate(self, league_id: str, season_count: int) -> dict[str, int]:
        """Estimate a complete root namespace from existing compact archives."""
        files = [
            self.path(league_id, season)
            for season in self.available_seasons(league_id)
        ]
        sizes = [path.stat().st_size for path in files if path.is_file()]
        average = int(sum(sizes) / len(sizes)) if sizes else 512_000
        projected = average * max(0, int(season_count))
        return {
            "cached_bytes": sum(sizes), "average_season_bytes": average,
            "projected_complete_bytes": projected,
            "additional_bytes": max(0, projected - sum(sizes)),
        }

    def health(
        self, league_id: str | None = None, manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        files = list(self.root.rglob("*.json.gz")) if self.root.exists() else []
        from collections import Counter
        from src.platform.cache_budget import SEASON_BUDGET, SEASON_COUNT, SEASON_LEAGUE_BYTES
        namespace_counts = Counter(path.parent for path in files)
        namespace_bytes = Counter()
        for path in files:
            namespace_bytes[path.parent] += path.stat().st_size
        breaches = (
            sum(path.stat().st_size for path in files) > SEASON_BUDGET.maximum_aggregate_bytes
            or any(path.stat().st_size > SEASON_BUDGET.maximum_entry_bytes for path in files)
            or any(count > SEASON_COUNT for count in namespace_counts.values())
            or any(size > SEASON_LEAGUE_BYTES for size in namespace_bytes.values())
        )
        result: dict[str, Any] = {
                "status": "retention_review_required" if breaches else "healthy", "ownership": "disposable_provider_cache",
                "completed_seasons": len(files),
                "bytes": sum(path.stat().st_size for path in files),
                "rebuildable": True,
                "retention": {
                    "maximum_seasons_per_namespace": SEASON_COUNT,
                    "maximum_bytes_per_namespace": SEASON_LEAGUE_BYTES,
                    "maximum_aggregate_bytes": SEASON_BUDGET.maximum_aggregate_bytes,
                    "automatic_eviction": False,
                    "refetchability": "must_be_verified_before_eviction",
                },
        }
        if league_id is not None:
            rows = list((manifest or {}).get("seasons") or [])
            cached = list(self.available_seasons(league_id))
            result["league"] = {
                "discovered_seasons": [row.get("season") for row in rows],
                "cached_seasons": cached,
                "available_not_cached": [
                    row.get("season") for row in rows
                    if row.get("cache_status") == "available_not_cached"
                ],
                "unavailable_seasons": [
                    row.get("season") for row in rows
                    if row.get("cache_status") == "unavailable"
                ],
                "pending_current_seasons": [
                    row.get("season") for row in rows
                    if row.get("cache_status") == "pending_current"
                ],
                "last_error": next((
                    row.get("error") for row in reversed(rows) if row.get("error")
                ), None),
                "storage_estimate": self.storage_estimate(league_id, len(rows)),
            }
        return result
