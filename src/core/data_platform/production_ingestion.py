"""Global nflverse ingestion entry point for a background worker or operator job.

No route imports this module. Inputs contain public player identities and
source-backed game times, never league rosters or private intelligence.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Mapping

import httpx

from src.core.historical_memory.providers import NflverseProvider, normalize_nflverse_row

from .global_evidence import GlobalEvidenceStore
from .global_production import GlobalProduction
from .ingestion import ingest
from .normalization.identity import PlayerIdentityResolver
from .source_snapshot import download_snapshot


METHOD_VERSION = "nflverse-global-production-v3"


def ingest_production(client: httpx.Client, store: GlobalEvidenceStore, *, season: int,
                      identities: PlayerIdentityResolver, game_dates: Mapping[str, str],
                      retrieved_at: str, temporary_directory: Path) -> dict:
    """Pin source and all normalization dependencies before resumable ingestion.

    Modern observations never claim their historical publication time. Source
    outages propagate to the background caller; they do not erase prior facts.
    """
    if isinstance(season, bool) or not isinstance(season, int) or season < 1999:
        raise ValueError("Unsupported production season.")
    url = NflverseProvider.url_template.format(season=season)
    with download_snapshot(client, url, directory=temporary_directory) as snapshot:
        identity = hashlib.sha256(json.dumps({
            "source": snapshot.sha256, "method": METHOD_VERSION,
            "players": identities.mapping_fingerprint("GSIS"),
            "game_dates": dict(game_dates),
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        skipped = {"identity_unresolved": 0, "game_time_unavailable": 0}
        visited = 0

        def rows():
            nonlocal visited
            with snapshot.path.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                if not {"player_id", "season", "week", "game_id"}.issubset(reader.fieldnames or []):
                    raise ValueError("Production source schema is incomplete.")
                for row in reader:
                    normalized = normalize_nflverse_row(row)
                    if normalized.get("season") != season:
                        raise ValueError("Production source contains a different season.")
                    visited += 1
                    yield normalized

        def facts():
            return GlobalProduction.facts(rows(), identities=identities, game_dates=game_dates, skipped=skipped)

        prior = store.ingestion_checkpoint(f"nflverse/production/{season}")
        unchanged = bool(prior and prior["source_identity"] == identity and prior["complete"])
        result = ingest(store, key=f"nflverse/production/{season}", source_identity=identity,
                        facts=facts, retrieved_at=retrieved_at)
        return {**result, "source_sha256": snapshot.sha256, "source_bytes": snapshot.bytes_downloaded,
                "source_identity": identity, "unchanged_revision": unchanged,
                "source_rows_examined": visited,
                "coverage": None if unchanged else skipped,
                "coverage_reason": "unchanged revision; prior coverage applies" if unchanged else "source examined"}
