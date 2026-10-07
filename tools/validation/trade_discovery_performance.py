"""Repeatable read-only discovery benchmark over a sanitized frozen publication.

Create one fixture, then mount it into baseline and current source trees. Profiled
phase times are inclusive and overlap; unprofiled samples include response JSON.
No manager account, provider refresh, trade submission or Sleeper mutation.
"""

import argparse
import cProfile
import json
from pathlib import Path
import pstats
import statistics
import time
from unittest.mock import patch

from src.core.projection_intelligence.service import ProjectionService
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from services.trade_intelligence import generate_trade_workflow, assist_trade_request


def work_profile(profiler):
    stats = pstats.Stats(profiler).stats
    functions = []
    for (filename, _, function), (_, calls, own, cumulative, _) in stats.items():
        functions.append(
            {
                "module": filename.replace("\\", "/").rsplit("/", 1)[-1],
                "function": function,
                "calls": calls,
                "self_seconds": own,
                "inclusive_seconds": cumulative,
            }
        )
    functions.sort(key=lambda row: -row["inclusive_seconds"])
    return {"functions": functions, "inclusive_times_overlap": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="current")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument(
        "--budget",
        action="store_true",
        help="Future filter exhausts the unchanged 180-evaluation budget",
    )
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 10:
        parser.error("Repeat count must be bounded to 1–10.")
    if args.prepare:
        from tests.trade_performance_fixture import prepare_fixture

        prepare_fixture(args.fixture)
    root = args.fixture
    data = json.loads((root / "data.json").read_text())
    for team in data["team_strength"]["teams"].values():
        team["weekly"] = {int(k): v for k, v in team["weekly"].items()}
    reader = ProjectionService(root / "projections.sqlite3")
    output = args.output
    output.mkdir(exist_ok=True)
    label = args.label
    repeats = args.repeat
    profiled = args.profile
    rows = []
    business = []

    def clean(value):
        if isinstance(value, dict):
            return {
                k: clean(v)
                for k, v in value.items()
                if not (
                    str(k).endswith("_seconds")
                    or str(k).endswith("_duration_ms")
                    or k in ("timings_seconds", "performance", "reuse")
                )
            }
        if isinstance(value, (tuple, list)):
            return [clean(v) for v in value]
        return value

    with (
        patch(
            "services.trade_intelligence._trade_projection_service", return_value=reader
        ),
        patch.object(data_platform, "warehouse", SnapshotWarehouse()),
    ):
        for run in range(repeats):
            from src.core.intelligence.cache import intelligence_cache

            intelligence_cache.invalidate()
            try:
                from src.core.trade_intelligence.lineup_memo import lineup_store

                lineup_store.clear()
            except ImportError:
                pass
            families = []
            for flow in (
                ("recommended", "next")
                if args.budget
                else (
                    "recommended",
                    "warm_recommended",
                    "next",
                    "shop",
                    "trade_for",
                    "cheaper",
                )
            ):
                p = {
                    "workflow": "recommended"
                    if flow in ("next", "warm_recommended")
                    else flow,
                    "active_roster_id": 1,
                    "strategy": "RETOOL",
                }
                if args.budget:
                    p["recommendation_filter"] = "future"
                if flow == "next":
                    p["excluded_recommendation_families"] = families
                if flow == "shop":
                    p["asset_id"] = "1-QB-0"
                if flow == "trade_for":
                    p["asset_id"] = "2-WR-12"
                if flow == "cheaper":
                    p.update(
                        partner_roster_id=2,
                        assets_sent=["1-QB-0", "1-QB-1"],
                        assets_received=["2-WR-12"],
                        instruction="make it cheaper",
                    )
                profiler = cProfile.Profile()
                start = time.perf_counter()
                if profiled:
                    profiler.enable()
                result = (
                    assist_trade_request
                    if flow == "cheaper"
                    else generate_trade_workflow
                )(data, p)
                # Include JSON serialization in manager-facing pipeline wall time.
                serialization_start = time.perf_counter()
                json.dumps(result, default=str)
                serialization_seconds = time.perf_counter() - serialization_start
                if profiled:
                    profiler.disable()
                elapsed = time.perf_counter() - start
                if flow == "recommended":
                    families = [r["family_id"] for r in result["results"]]
                if profiled:
                    profiler.dump_stats(str(output / f"{label}-{flow}.prof"))
                    with (output / f"{label}-{flow}-profile.txt").open("w") as target:
                        pstats.Stats(profiler, stream=target).sort_stats(
                            "cumulative"
                        ).print_stats(50)
                evidence = result.get("search_evidence", {})
                row = {
                    "run": run,
                    "workflow": flow,
                    "seconds": elapsed,
                    "count": result["count"],
                    "evaluated": evidence.get("full_evaluations"),
                    "timings": evidence.get("timings_seconds"),
                    "reuse": evidence.get("reuse"),
                }
                row["response_serialization_seconds"] = serialization_seconds
                if profiled:
                    row["work_profile"] = work_profile(profiler)
                rows.append(row)
                business.append({"run": run, "workflow": flow, "result": clean(result)})
                (output / f"{label}-measurements.json").write_text(
                    json.dumps(rows, indent=2)
                )
                (output / f"{label}-business.json").write_text(
                    json.dumps(business, sort_keys=True, default=str)
                )
                print(json.dumps(row), flush=True)
    for flow in {r["workflow"] for r in rows}:
        values = [r["seconds"] for r in rows if r["workflow"] == flow]
        print(flow, "p50", statistics.median(values), "worst", max(values))

    if args.reference:
        reference = json.loads(args.reference.read_text())
        # Compare the manager-facing JSON boundary: integer week keys and other
        # JSON-converted values must use the same representation on both sides.
        actual = json.loads((output / f"{label}-business.json").read_text())
        assert actual == reference, "Discovery intelligence differs from reference"
        print("All business responses exactly match reference.")


if __name__ == "__main__":
    main()
