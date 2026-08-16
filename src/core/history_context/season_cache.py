"""Disposable normalized Sleeper completed-season cache."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import threading
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


class SleeperSeasonCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._checksum_lock = threading.RLock()
        self._checksum_cache: dict[Path, tuple[tuple[int, int, int, int], str]] = {}
        self._section_cache: dict[
            tuple[Path, str], tuple[tuple[int, int, int, int], Any]
        ] = {}

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
            self._checksum_cache.pop(path, None)
            for key in tuple(self._section_cache):
                if key[0] == path:
                    self._section_cache.pop(key, None)

    def write(self, season: CachedSeason) -> Path:
        path = self.path(season.league_id, season.season)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "league_id": season.league_id, "season": season.season,
            "status": season.status, "completeness": season.completeness,
            "facts": season.facts, "checksum": season.checksum,
        }, sort_keys=True, separators=(",", ":")).encode()
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                temporary = handle.name
                handle.write(gzip.compress(payload, compresslevel=6))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
            stat = path.stat()
            identity = (
                int(stat.st_dev), int(stat.st_ino), int(stat.st_size),
                int(stat.st_mtime_ns),
            )
            with self._checksum_lock:
                self._checksum_cache[path] = (identity, season.checksum)
                self._section_cache[(path, "transactions")] = (
                    identity, season.facts.get("transactions") or {},
                )
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
        return path

    def read(self, league_id: str, season: int) -> CachedSeason | None:
        path = self.path(league_id, season)
        if not path.exists():
            return None
        payload = json.loads(gzip.decompress(path.read_bytes()))
        candidate = self.normalize(league_id, season, payload["facts"])
        if candidate.checksum != payload.get("checksum"):
            raise ValueError("Sleeper completed-season cache checksum mismatch.")
        stat = path.stat()
        identity = (
            int(stat.st_dev), int(stat.st_ino), int(stat.st_size),
            int(stat.st_mtime_ns),
        )
        with self._checksum_lock:
            self._section_cache[(path, "transactions")] = (
                identity, candidate.facts.get("transactions") or {},
            )
        return candidate

    def section(self, league_id: str, season: int, name: str) -> Any:
        """Read a compact normalized section, reusing it while the archive is unchanged."""
        path = self.path(league_id, season)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        identity = (
            int(stat.st_dev), int(stat.st_ino), int(stat.st_size),
            int(stat.st_mtime_ns),
        )
        key = (path, str(name))
        with self._checksum_lock:
            cached = self._section_cache.get(key)
        if cached is not None and cached[0] == identity:
            return cached[1]
        archive = self.read(league_id, season)
        if archive is None:
            return None
        value = archive.facts.get(name)
        with self._checksum_lock:
            self._section_cache[key] = (identity, value)
        return value

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
                cached = self._checksum_cache.get(path)
            if cached is not None and cached[0] == identity:
                result[season] = cached[1]
                continue
            archive = self.read(league_id, season)
            if archive is None:
                continue
            with self._checksum_lock:
                self._checksum_cache[path] = (identity, archive.checksum)
            result[season] = archive.checksum
        return result

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
        result: dict[str, Any] = {
                "status": "healthy", "ownership": "disposable_provider_cache",
                "completed_seasons": len(files),
                "bytes": sum(path.stat().st_size for path in files),
                "rebuildable": True,
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
