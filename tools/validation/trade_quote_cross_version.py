"""Real v1.21.36 quote publisher -> new reader in disposable separate processes."""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile

BASE = "93c74af40952e906fecfac570454739239196289"


def worker(code, root, publish):
    sys.path.insert(0, str(code))
    from tools.validation.projection_display_cross_version import isolated

    isolated(root)
    os.environ["DTOS_INTELLIGENCE_CHECKPOINT_FILE"] = str(root / "memory.sqlite3")
    from src.core.intelligence_memory.store import IntelligenceCheckpointStore
    from src.core.intelligence_memory.service import IntelligenceMemoryService
    from src.core.intelligence_memory.pipeline import CheckpointPipeline
    from src.core.intelligence_memory.models import (
        CheckpointTrigger,
        ProvenanceType,
        EvidenceCompleteness,
    )
    from tests.test_market_observation_producer_identity import prepared

    store = IntelligenceCheckpointStore(root / "memory.sqlite3")
    cases = [
        ("future", "2026-03-02T00:00:00Z", True, "player"),
        ("stale", "2026-02-01T00:00:00Z", True, "player"),
        ("exact", "2026-03-01T00:00:00Z", True, "player"),
        ("opaque", "2026-03-01T00:00:00Z", False, "player"),
        ("pick", "2026-03-01T00:00:00Z", True, "future_pick"),
    ]

    def retained():
        with closing(sqlite3.connect(root / "memory.sqlite3")) as db:
            return {
                table: db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                for table in (
                    "intelligence_checkpoints",
                    "global_market_observations",
                    "pick_lineage",
                    "exact_pick_lineage",
                )
            }

    if publish:
        service = IntelligenceMemoryService(store)
        for name, quote, explicit, kind in cases:
            data, _ = prepared()
            evidence = tuple(
                replace(r, observed_at=quote, metadata=r.metadata if explicit else {})
                for r in CheckpointPipeline._market_observations(data, "player:1")
            )
            asset = "pick:2027:1:4" if kind == "future_pick" else "player:" + name
            service.capture(
                trigger=CheckpointTrigger.TRADE_EXECUTION,
                asset_id=asset,
                asset_type=kind,
                timestamp="2026-03-01T00:00:00Z",
                season=2026,
                provenance=ProvenanceType.LIVE_CAPTURED,
                market_value=500,
                confidence=90,
                completeness=EvidenceCompleteness.COMPLETE,
                observations=evidence,
                league_id="A",
                event_id=name,
            )
        (root / "before.json").write_text(json.dumps(retained(), sort_keys=True))
        return
    from src.core.historical_memory.graph import HistoricalAssetGraph
    from src.core.history_context.store import CanonicalHistoryStore

    graph = HistoricalAssetGraph(CanonicalHistoryStore(), "A", intelligence_store=store)
    results = {}
    for name, _quote, _explicit, kind in cases:
        asset = "PICK-2027-R1-ORIG4" if kind == "future_pick" else "DTOS-P-" + name
        result = graph._trade_time_intelligence(
            {"occurred_at": "2026-03-01T00:00:00Z"},
            [{"asset_id": asset, "to_franchise_id": "A:franchise:1"}],
        )
        row = result["assets"][0]
        if name in ("future", "opaque"):
            assert row["value"] is None, (name, row)
        else:
            assert row["value"] == 500, (name, row)
        if name == "stale":
            assert (
                row["match_state"] == "DATED_ESTIMATE"
                and row["temporal_confidence"] < 65
            )
            assert row['retained_attachment_at'] == '2026-03-01T00:00:00Z', row
            assert row['observed_at'] == '2026-02-01T00:00:00Z', row
        results[name] = {
            "value": row["value"],
            "state": row["match_state"],
            "quote_at": row["observed_at"],
            "retained_attachment_at": row.get("retained_attachment_at"),
            "confidence": row["temporal_confidence"],
        }
    assert json.loads((root / "before.json").read_text()) == json.loads(
        json.dumps(retained())
    ), "Original stored evidence changed"
    sizes = {p.name: p.stat().st_size for p in root.iterdir() if p.is_file()}
    for _ in range(20):
        graph._trade_time_intelligence(
            {"occurred_at": "2026-03-01T00:00:00Z"},
            [{"asset_id": "DTOS-P-stale", "to_franchise_id": "A:franchise:1"}],
        )
    assert sizes == {p.name: p.stat().st_size for p in root.iterdir() if p.is_file()}, (
        "Reads grew durable files"
    )
    print(
        json.dumps(
            {
                "baseline": BASE,
                "cases": results,
                "original_rows_unchanged": True,
                "repeat_reads_no_growth": True,
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=["publish", "read"])
    parser.add_argument("--code", type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.code, args.root, args.worker == "publish")
        return
    repository = Path(__file__).resolve().parents[2]
    script = Path(__file__).resolve()
    with tempfile.TemporaryDirectory(prefix="dtos-trade-quotes-") as folder:
        root = Path(folder)
        old = root / "old"
        old.mkdir()
        publication = root / "publication"
        publication.mkdir()
        archive = root / "source.tar"
        with archive.open("wb") as output:
            subprocess.run(
                ["git", "archive", BASE], cwd=repository, stdout=output, check=True
            )
        with tarfile.open(archive) as tar:
            tar.extractall(old, filter="data")
        for mode, code in [("publish", old), ("read", repository)]:
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--worker",
                    mode,
                    "--code",
                    str(code),
                    "--root",
                    str(publication),
                ],
                cwd=code,
                check=True,
            )


if __name__ == "__main__":
    main()
