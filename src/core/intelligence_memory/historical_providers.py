"""Approved, bounded historical-market provider adapters."""
from __future__ import annotations

import csv
import io
from collections import OrderedDict
from datetime import datetime
from threading import RLock
from typing import Any, Callable

import httpx

from .models import SourceObservation

DYNASTYPROCESS_REPOSITORY = "dynastyprocess/data"
DYNASTYPROCESS_VALUES_PATH = "files/values.csv"
DYNASTYPROCESS_IDS_PATH = "files/db_playerids.csv"


class DynastyProcessHistoricalProvider:
    """Read one repository snapshot at/before an event; retain no archive on disk."""

    provider_id = "dynastyprocess"

    def __init__(
        self, *, timeout: float = 20,
        get_json: Callable[[str, dict[str, str]], Any] | None = None,
        get_text: Callable[[str], str] | None = None,
        maximum_snapshots: int = 8,
    ) -> None:
        self.timeout = timeout
        self.maximum_snapshots = max(1, int(maximum_snapshots))
        self._get_json = get_json or self._http_json
        self._get_text = get_text or self._http_text
        self._snapshots: OrderedDict[str, tuple[dict[str, dict[str, str]], tuple[dict[str, str], ...]]] = OrderedDict()
        self._commit_months: dict[str, tuple[str, str] | None] = {}
        self._lock = RLock()
        self.requests = self.bytes_downloaded = self.snapshot_hits = 0

    def _http_json(self, url: str, params: dict[str, str]) -> Any:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url, params=params, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            self.requests += 1
            self.bytes_downloaded += len(response.content)
            return response.json()

    def _http_text(self, url: str) -> str:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            self.requests += 1
            self.bytes_downloaded += len(response.content)
            return response.text

    def _commit(self, at_or_before: str) -> tuple[str, str] | None:
        month = at_or_before[:7]
        with self._lock:
            cached = self._commit_months.get(month)
            if cached and cached[1] <= at_or_before:
                return cached
        rows = self._get_json(
            f"https://api.github.com/repos/{DYNASTYPROCESS_REPOSITORY}/commits",
            {"path": DYNASTYPROCESS_VALUES_PATH, "until": at_or_before, "per_page": "1"},
        )
        if not isinstance(rows, list) or not rows:
            result = None
            with self._lock:
                self._commit_months[month] = result
            return result
        row = rows[0]
        stamp = (((row.get("commit") or {}).get("committer") or {}).get("date"))
        result = str(row.get("sha") or ""), str(stamp or "")
        with self._lock:
            self._commit_months[month] = result
        return result

    def _snapshot(self, sha: str) -> tuple[dict[str, dict[str, str]], tuple[dict[str, str], ...]]:
        with self._lock:
            cached = self._snapshots.get(sha)
            if cached:
                self.snapshot_hits += 1
                self._snapshots.move_to_end(sha)
                return cached
        base = f"https://raw.githubusercontent.com/{DYNASTYPROCESS_REPOSITORY}/{sha}/files"
        values_text = self._get_text(f"{base}/values.csv")
        ids_text = self._get_text(f"{base}/db_playerids.csv")
        identities = {
            str(row.get("sleeper_id")): row
            for row in csv.DictReader(io.StringIO(ids_text))
            if row.get("sleeper_id") not in {None, "", "NA"}
        }
        values = tuple(csv.DictReader(io.StringIO(values_text)))
        result = identities, values
        with self._lock:
            self._snapshots[sha] = result
            while len(self._snapshots) > self.maximum_snapshots:
                self._snapshots.popitem(last=False)
        return result

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value not in {None, "", "NA"} else None
        except (TypeError, ValueError):
            return None

    def observations(self, **context: str):
        commit = self._commit(context["at_or_before"])
        if not commit or not commit[0] or not commit[1]:
            return ()
        sha, observed_at = commit
        identities, rows = self._snapshot(sha)
        asset_id = context["asset_id"]
        matched: list[dict[str, str]] = []
        if context["asset_type"] == "player":
            sleeper_id = asset_id.removeprefix("player:")
            identity = identities.get(sleeper_id) or {}
            fp_id = str(identity.get("fantasypros_id") or "")
            matched = [row for row in rows if fp_id and str(row.get("fp_id") or "") == fp_id]
        elif context["asset_type"] == "future_pick":
            parts = asset_id.removeprefix("pick:").split(":")
            if len(parts) >= 2:
                season, round_number = parts[:2]
                label = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}.get(round_number)
                if label:
                    prefixes = {f"{season} Early {label}", f"{season} Mid {label}", f"{season} Late {label}"}
                    matched = [row for row in rows if str(row.get("player") or "") in prefixes]
        values = [self._number(row.get("value_2qb")) for row in matched]
        values = [value for value in values if value is not None]
        if not values:
            return ()
        value = sum(values) / len(values)
        return (SourceObservation(
            provider=self.provider_id, raw_value=value, normalized_value=value,
            observed_at=observed_at, source_identity=f"github:{sha[:12]}:{asset_id}",
            temporal_distance_seconds=int((
                datetime.fromisoformat(context["at_or_before"].replace("Z", "+00:00"))
                - datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            ).total_seconds()),
            metadata={
                "repository": DYNASTYPROCESS_REPOSITORY,
                "snapshot_commit": sha[:12], "format": "2QB",
                "matching": "fantasypros_to_sleeper" if context["asset_type"] == "player" else "generic_pick_round_average",
            },
        ),)

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.provider_id, "source": "approved_open_repository_history",
            "asset_types": ["player", "future_pick"], "timestamp_precision": "repository_commit",
            "availability": "best_effort", "snapshot_cache_entries": len(self._snapshots),
            "provider_requests": self.requests, "bytes_downloaded": self.bytes_downloaded,
            "snapshot_cache_hits": self.snapshot_hits, "permanent_snapshot_bytes": 0,
        }
