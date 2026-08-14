"""Disposable, normalized Sleeper completed-season cache."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
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
    """Cache provider facts for speed without making them permanent DTOS truth."""

    def __init__(self, root: Path):
        self.root = root

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
        return CachedSeason(
            str(league_id), int(season), status, completeness, normalized,
            hashlib.sha256(body.encode()).hexdigest(),
        )

    def _path(self, league_id: str, season: int) -> Path:
        namespace = hashlib.sha256(str(league_id).encode()).hexdigest()[:16]
        return self.root / namespace / f"{int(season)}.json.gz"

    def write(self, season: CachedSeason) -> Path:
        path = self._path(season.league_id, season.season)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "league_id": season.league_id,
            "season": season.season,
            "status": season.status,
            "completeness": season.completeness,
            "facts": season.facts,
            "checksum": season.checksum,
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
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
        return path

    def read(self, league_id: str, season: int) -> CachedSeason | None:
        path = self._path(league_id, season)
        if not path.exists():
            return None
        payload = json.loads(gzip.decompress(path.read_bytes()))
        candidate = self.normalize(league_id, season, payload["facts"])
        if candidate.checksum != payload.get("checksum"):
            raise ValueError("Sleeper completed-season cache checksum mismatch.")
        return candidate

    def delete(self, league_id: str, season: int) -> None:
        self._path(league_id, season).unlink(missing_ok=True)

    async def get_or_rebuild(
        self,
        league_id: str,
        season: int,
        fetch_facts: Callable[[str, int], Awaitable[dict[str, Any] | None]],
    ) -> CachedSeason:
        cached = self.read(league_id, season)
        if cached is not None:
            return cached
        facts = await fetch_facts(str(league_id), int(season))
        rebuilt = self.normalize(str(league_id), int(season), facts or {})
        if facts:
            self.write(rebuilt)
        return rebuilt

    def health(self) -> dict[str, Any]:
        files = list(self.root.rglob("*.json.gz")) if self.root.exists() else []
        return {
            "status": "healthy",
            "ownership": "disposable_provider_cache",
            "completed_seasons": len(files),
            "bytes": sum(path.stat().st_size for path in files),
            "rebuildable": True,
        }
