"""Two-phase Actions publisher. Never merges PRs or updates a branch ref."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

ALLOWED_PATHS = {
    ".github/workflows/canonical-release-recovery.yml",
    ".github/release-plans/2251.json",
    ".github/release-plans/2251-recovery-001.part",
    ".github/release-plans/2251-recovery-002.part",
    ".github/release-plans/2251-recovery-003.part",
    ".github/release-plans/2251-recovery-004.part",
    ".github/release-plans/2251-prior.zip",
    ".github/release-plans/2251-prior-001.part",
    ".github/release-plans/2251-prior-002.part",
    ".github/release-plans/2251-prior-003.part",
    ".github/release-plans/2251-prior-004.part",
    ".github/release-plans/README.md",
    "tools/release/__init__.py",
    "tools/release/publish.py",
    "tests/test_release_publisher.py",
}
TOKEN = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def api(path, body=None):
    args = ["gh", "api", path]
    if body is None:
        return json.loads(command(*args))
    # A structured input file preserves literal strings and never exposes GH_TOKEN.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as stream:
        json.dump(body, stream)
        stream.flush()
        return json.loads(
            command(
                *args,
                "--method",
                "POST" if path.endswith(("/tags", "/refs")) else "PATCH",
                "--input",
                stream.name,
            )
        )


def download(path, destination):
    args = ["gh", "api", path]
    if path.endswith("/logs"):
        # Match the established publisher: retain ANSI bytes in a file, never
        # render downloaded logs directly in the terminal.
        args.append("--allow-escape-sequences")
    with destination.open("wb") as stream:
        subprocess.run(args, stdout=stream, check=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def verify_zip(path):
    """Reject paths/symlinks/duplicates before reading any artifact member."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate archive member")
        require(
            sum(x.file_size for x in archive.infolist()) < 512 * 1024**2,
            "Oversized archive",
        )
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            require(
                not name.is_absolute()
                and ".." not in name.parts
                and "\\" not in item.filename,
                "Unsafe archive member",
            )
            require(
                (item.external_attr >> 16) & 0o170000 != 0o120000, "Archive symlink"
            )
            if not item.is_dir() and name.suffix in {
                ".log",
                ".json",
                ".jsonl",
                ".md",
                ".txt",
                ".py",
                ".html",
                ".js",
            }:
                require(
                    not TOKEN.search(archive.read(item)),
                    "Credential-shaped material in evidence; manual review required",
                )
        require(archive.testzip() is None, "Archive CRC mismatch")


def verify_canonical_sums(archive, manifest, prefix=""):
    name = prefix + "SHA256SUMS"
    require(name in archive.namelist(), "Canonical checksum list missing")
    entries = [line.split("  ", 1) for line in archive.read(name).decode().splitlines()]
    require(all(len(row) == 2 for row in entries), "Malformed canonical checksum list")
    expected = {row["name"]: row["sha256"] for row in manifest}
    require(
        len(entries) == len(expected) and {row[1] for row in entries} == set(expected),
        "Canonical checksum population mismatch",
    )
    for sha, member in entries:
        require(
            sha == expected[member]
            and hashlib.sha256(archive.read(prefix + member)).hexdigest() == sha,
            "Canonical checksum list mismatch",
        )


def verify_canonical(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("result.json"))
        require(
            result["head"] == plan["candidate"] and result["tree"] == plan["tree"],
            "Canonical source mismatch",
        )
        require(
            result["passed"] is True and result["exit_code"] == 0,
            "Canonical did not pass",
        )
        require(
            str(result.get("python", "")).split(" ", 1)[0] == plan["python_version"],
            "Canonical Python runtime mismatch",
        )
        require(
            result["cgroup_limit"] == 2147483648
            and result["cpus"] == 2
            and result["network"] == "none",
            "Canonical resource contract mismatch",
        )
        require(
            not result["final_memory"]["cgroup_memory_events"].get("oom_kill"),
            "Canonical OOM event",
        )
        manifest = json.loads(archive.read("manifest.json"))
        require(
            len(manifest) == plan["canonical_entries"],
            "Canonical manifest population mismatch",
        )
        names = set()
        for entry in manifest:
            require(entry["name"] not in names, "Duplicate canonical manifest row")
            names.add(entry["name"])
            data = archive.read(entry["name"])
            require(
                len(data) == entry["bytes"]
                and hashlib.sha256(data).hexdigest() == entry["sha256"],
                "Canonical payload checksum mismatch",
            )
        verify_canonical_sums(archive, manifest)
        events = Counter(
            json.loads(line)["event"]
            for line in archive.read("tests.jsonl").splitlines()
        )
        require(
            events["start"] == events["stop"] == plan["canonical_tests"]
            and not any(events[x] for x in ("failure", "error", "skip")),
            "Incomplete/failed canonical tests",
        )
        trace = [
            json.loads(line)
            for line in archive.read("canonical-trace.jsonl").splitlines()
        ]
        require(
            any(
                x.get("event") == "validator_final_summary" and x.get("gates") == 10
                for x in trace
            ),
            "Ten-gate final summary missing",
        )
        completed = [x for x in trace if x.get("event") == "validation_child_completed"]
        require(
            len(completed) == 10 and all(x["return_code"] == 0 for x in completed),
            "Incomplete canonical gate execution",
        )
        return result


def verify_current_history(path, plan):
    """Verify source-pinned restored-history browser controls, never live proof."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read("browser.json"))
        require(
            report.get("head") == plan["candidate"]
            and report.get("tree") == plan["tree"]
            and report.get("working_tree_clean") is True,
            "Current history source mismatch",
        )
        rows = report.get("records", [])
        expected = {
            (league, width, height)
            for league in ("Granite-shaped", "Day-shaped", "Arkham-shaped")
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900))
        }
        require(
            len(rows) == 12
            and {(r["league_control"], r["width"], r["height"]) for r in rows}
            == expected,
            "Current history browser population incomplete",
        )
        require(
            all(
                r.get("retrieved") == [1, 2, 3, 5, 6, 7, 8]
                and r.get("failed") == [4]
                and r.get("keyboard") is True
                and r.get("overflow") is False
                and r.get("extra_disclosure_requests") == 0
                and r.get("touch_emulated") is (r["width"] < 1000)
                for r in rows
            ),
            "Current history lifecycle or accessibility control failed",
        )
        pngs = [n for n in archive.namelist() if n.endswith(".png")]
        require(
            len(pngs) == 12
            and all(archive.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in pngs),
            "Current history screenshots missing",
        )
    return report


def verify_history_followthrough(path, plan):
    """Validate the actual origin/branch/Back sequence on the pinned source."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read("browser.json"))
        require(
            report.get("head") == plan["candidate"]
            and report.get("tree") == plan["tree"]
            and report.get("working_tree_clean") is True,
            "History follow-through source mismatch",
        )
        rows = report.get("records", [])
        controls = (
            "Day retained chain plus disposable pagination",
            "Arkham retained history and scope reset",
        )
        expected = {
            (control, w, h)
            for control in controls
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        }
        require(
            len(rows) == 8
            and {(r["control"], r["width"], r["height"]) for r in rows} == expected,
            "History follow-through browser population incomplete",
        )
        require(
            report.get("errors") == [] and report.get("server_thread_reaped") is True,
            "History browser error or server cleanup failed",
        )
        for row in rows:
            require(row.get("overflow") is False, "History browser overflow")
            if row["control"] == controls[1]:
                require(
                    row.get("source_qualified") is True
                    and row.get("old_league_replay") is False,
                    "History selected-league qualification failed",
                )
                continue
            chain = row.get("chain", [])
            require(
                len(chain) == 16 and chain[0].startswith("/history/team/"),
                "History journey incomplete",
            )
            history, player = chain[0], chain[4]
            root = "/trades/history/" + row["original"]
            pick = "/picks/" + row["pick"] + "?from_trade=" + row["original"]
            later = "/trades/history/" + row["later"] + "?from_trade=" + row["original"]
            require(
                player.startswith("/players/")
                and player.endswith("?from_trade=" + row["original"]),
                "History player origin missing",
            )
            require(
                chain[:15]
                == [
                    history,
                    history + "?events_page=2",
                    root,
                    pick,
                    player,
                    later,
                    root,
                    later,
                    player,
                    pick,
                    root,
                    history + "?events_page=2",
                    history,
                    history + "?events_page=2",
                    history + "?events_page=2",
                ]
                and chain[15].startswith("/history/team/")
                and chain[15] != history,
                "History branch, origin, pagination or Forward/reload sequence changed",
            )
            require(
                row.get("pagination_return") is True
                and row.get("forward_reload") is True
                and row.get("keyboard") is True
                and row.get("touch_emulated") is (row["width"] < 500)
                and row.get("extra_disclosure_requests") == 0,
                "History interaction control failed",
            )
        requests = report.get("requests", [])
        require(
            requests
            and any(
                r["path"] == "/api/account/navigation-context" and r["status"] == 200
                for r in requests
            )
            and not any(
                "/sync" in r["path"] or "/trades/recommended" in r["path"]
                for r in requests
            ),
            "History verified context missing or unexpected heavyweight request",
        )
        pngs = [n for n in archive.namelist() if n.endswith(".png") and "/" not in n]
        require(
            len(pngs) == 8
            and all(archive.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in pngs),
            "History follow-through screenshots missing",
        )
    return report


def verify_market_history(path, plan):
    """Require actual cache transitions on the pinned source, never live proof."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read("browser.json"))
        require(
            report.get("head") == plan["candidate"]
            and report.get("tree") == plan["tree"]
            and report.get("working_tree_clean") is True,
            "Market history source mismatch",
        )
        rows = report.get("records", [])
        expected = {
            (league, w, h)
            for league in ("1314695233040052224", "1319750579458686976")
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        }
        require(
            len(rows) == 8
            and {(r["league"], *r["viewport"]) for r in rows} == expected,
            "Market history browser population incomplete",
        )
        require(
            report.get("errors") == [] and report.get("browser_closed") is True,
            "Market history browser errors or cleanup failed",
        )
        for row in rows:
            require(
                row.get("before") == {"magnitude": 100, "checkpoint_count": 2},
                "Market baseline changed",
            )
            updated, boundary = row.get("updated", {}), row.get("boundary", {})
            require(
                updated.get("magnitude") == 120
                and updated.get("checkpoint_count") == 3
                and updated.get("comparison_start_at") == "2026-06-01T12:00:00Z"
                and updated.get("comparison_end_at") == "2026-08-31T12:00:00+00:00"
                and updated.get("comparison_scope") == "historical_to_current"
                and updated.get("comparison_units") == "0-1000"
                and updated.get("confidence") == "low",
                "Market comparison evidence mismatch",
            )
            require(
                boundary.get("magnitude") is None
                and boundary.get("checkpoint_count") == 4
                and boundary.get("direction") == "not_comparable"
                and boundary.get("comparison_reasons")
                == ["INCOMPATIBLE_OBSERVATION_BOUNDARY"],
                "Market compatibility boundary lost",
            )
            require(
                row.get("price_publication_unchanged") is True
                and row.get("overflow") is False
                and row.get("keyboard") is True
                and row.get("disclosure_extra_requests") == 0
                and row.get("source_catalogue_not_participation") is True,
                "Market cache, provider or accessibility control failed",
            )
        for key in ("before_memory", "after_memory"):
            memory = report.get(key, {})
            require(
                memory.get("cgroup_limit_bytes") == 2147483648
                and not memory.get("cgroup_memory_events", {}).get("oom")
                and not memory.get("cgroup_memory_events", {}).get("oom_kill"),
                "Market constrained memory evidence failed",
            )
        requests = report.get("requests", [])
        require(
            requests
            and not any(
                "/sync" in r["path"]
                or "/trades/recommended" in r["path"]
                or "/fois/rebuild" in r["path"]
                for r in requests
            ),
            "Unexpected heavyweight Market request",
        )
        pngs = [n for n in archive.namelist() if n.endswith(".png")]
        require(
            len(pngs) == 24
            and all(archive.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in pngs),
            "Market history screenshots missing",
        )
    return report


def verify_current_production(path, plan):
    """Pinned source-to-screen evidence, not a claim of live league recovery."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read("browser.json"))
        require(
            report.get("head") == plan["candidate"]
            and report.get("tree") == plan["tree"]
            and report.get("working_tree_clean") is True,
            "Production coverage source mismatch",
        )
        rows = report.get("records", [])
        expected = {
            (league, w, h)
            for league in ("1314695233040052224", "1319750579458686976")
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        }
        require(
            len(rows) == 8
            and {(r["league"], *r["viewport"]) for r in rows} == expected,
            "Production coverage browser population incomplete",
        )
        require(
            report.get("errors") == [] and report.get("browser_closed") is True,
            "Production coverage browser errors or cleanup failed",
        )
        for row in rows:
            complete, partial = row.get("complete", {}), row.get("partial", {})
            require(
                complete.get("fantasy_points") == 18
                and complete.get("observation_count") == 8
                and complete.get("scored_count") == 8
                and complete.get("season") == 2026
                and complete.get("weeks") == list(range(1, 9)),
                "Complete production evidence mismatch",
            )
            require(
                partial.get("fantasy_points") is None
                and partial.get("observation_count") == 8
                and partial.get("scored_count") == 7
                and partial.get("missing_components") == ["conflicting_sleeper_scores"],
                "Missing production incorrectly calculated",
            )
            require(
                row.get("retained_failure") is True
                and row.get("keyboard") is True
                and row.get("overflow") is False
                and row.get("extra_disclosure_requests") == 0
                and row.get("touch_emulated") is (row["viewport"][0] < 1000),
                "Production retained-data or accessibility control failed",
            )
        for key in ("before_memory", "after_memory"):
            memory = report.get(key, {})
            require(
                memory.get("cgroup_limit_bytes") == 2147483648
                and not memory.get("cgroup_memory_events", {}).get("oom")
                and not memory.get("cgroup_memory_events", {}).get("oom_kill"),
                "Production constrained memory evidence failed",
            )
        requests = report.get("requests", [])
        require(
            requests
            and not any(
                "/sync" in r["path"]
                or "/trades/recommended" in r["path"]
                or "/fois/rebuild" in r["path"]
                for r in requests
            ),
            "Unexpected heavyweight production request",
        )
        pngs = [n for n in archive.namelist() if n.endswith(".png")]
        require(
            len(pngs) == 24
            and all(archive.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in pngs),
            "Production coverage screenshots missing",
        )
    return report


def verify_trade_resource(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("result.json"))
        require(
            result["head"] == plan["candidate"] and result["tree"] == plan["tree"],
            "Trade resource source mismatch",
        )
        require(
            result.get("passed") is True
            and result.get("complete") is True
            and result.get("working_tree_clean") is True,
            "Trade resource acceptance incomplete or dirty",
        )
        require(
            result.get("cleanup", {}).get("harness_scratch_exists_after") is False
            and result.get("cleanup", {}).get("trade_lease_available") is True,
            "Trade scratch/lease cleanup missing",
        )
        require(
            result["kernel_peak"] <= 2147483648
            and result["one_qb_http_evaluation"]["passed"] is True,
            "Trade enforced memory or one-QB control failed",
        )
        require(
            len(result["operations"]) >= 2
            and all(x["full_evaluations"] == 180 for x in result["operations"]),
            "Real Trade execution missing",
        )
        require(
            len({x["business_digest"] for x in result["operations"]}) == 1,
            "Trade recovery changed intelligence",
        )
        require(
            result["actual_cancel"]["evaluations_started"] > 0
            and result["file_cache_recovery"]["completed_evaluations"] == 180
            and result["file_cache_recovery"]["content_still_valid"] is True,
            "Trade cleanup/reclaim evidence missing",
        )
        require(
            result["states"]
            and all(
                x["cgroup_limit_bytes"] == 2147483648
                and not x["cgroup_memory_events"].get("oom")
                and not x["cgroup_memory_events"].get("oom_kill")
                for x in result["states"]
            ),
            "Trade container or OOM evidence failed",
        )
        require(
            result["liveness"]
            and all(
                type(x.get("server_duration_ms")) in (int, float)
                and x["server_duration_ms"] == x.get("milliseconds")
                and x["server_duration_ms"] < 500
                and type(x.get("client_elapsed_ms")) in (int, float)
                and x["client_elapsed_ms"] >= 0
                for x in result["liveness"]
            ),
            "Trade overlapping server liveness failed",
        )
        for line in archive.read("SHA256SUMS").decode().splitlines():
            expected, name = line.split("  ", 1)
            require(
                name in {"result.json", "raw.log", "preparation.log"}
                and hashlib.sha256(archive.read(name)).hexdigest() == expected,
                "Trade artifact checksum mismatch",
            )
        require(
            {
                line.split("  ", 1)[1]
                for line in archive.read("SHA256SUMS").decode().splitlines()
            }
            == {"result.json", "raw.log", "preparation.log"},
            "Trade attachment manifest incomplete",
        )
    return result


def verify_restoration_unused(path, plan):
    """Exact-source completion and deferral; no private Granite recovery claim."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("evidence/result.json"))
        require(
            result.get("head") == plan["candidate"]
            and result.get("tree") == plan["tree"]
            and result.get("working_tree_clean") is True,
            "Restoration source mismatch",
        )
        require(
            result.get("passed") is True
            and result.get("scratch_removed") is True
            and result.get("explicit_retry_completed") is True
            and result.get("expired_released_active_and_fresh_preserved") is True
            and result.get("fois_reserve_preserved") is True,
            "Restoration execution or ownership incomplete",
        )
        before, after = result["before_plan"], result["recovery"]
        require(
            before["would_admit"] is False
            and after["would_admit"] is True
            and before["required_bytes"] == after["required_bytes"]
            and after["expired_entries"] == 3
            and result["raw_bytes_released"] > 0,
            "Restoration guard or unused-reference recovery not established",
        )
        require(
            result["unsafe_pressure_deferred"]["would_admit"] is False
            and result["fois_reserved_plan"]["would_admit"] is False
            and result["fois_reserved_plan"]["required_bytes"]
            > before["required_bytes"],
            "Restoration pressure or FOIS safeguards incomplete",
        )
        require(
            0 < result["kernel_lifetime_peak_bytes"] <= 2147483648
            and result["samples"]
            and all(
                x["cgroup_limit_bytes"] == 2147483648
                and not x["cgroup_memory_events"].get("oom")
                and not x["cgroup_memory_events"].get("oom_kill")
                for x in result["samples"]
            ),
            "Restoration constrained memory evidence failed",
        )
        require(
            all(x.get("resource_tracker") is True for x in result["cleanup_processes"]),
            "Restoration retained application workers",
        )
        require(
            len(result["liveness"]) == 4
            and all(
                0 <= x["server_ms"] < 500 and x["client_ms"] >= 0
                for x in result["liveness"]
            ),
            "Restoration liveness failed",
        )
        checks = [
            line.split("  ", 1)
            for line in archive.read("SHA256SUMS").decode().splitlines()
        ]
        require(
            len(checks) == 3
            and {n for _, n in checks}
            == {"evidence/result.json", "raw.log", "prior-study.zip"},
            "Restoration checksum manifest incomplete",
        )
        for expected, name in checks:
            require(
                hashlib.sha256(archive.read(name)).hexdigest() == expected,
                "Restoration checksum mismatch",
            )
        require(
            hashlib.sha256(archive.read("prior-study.zip")).hexdigest()
            == "df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439"
            == result["prior_archive_sha256"],
            "Restoration prior input changed",
        )
    return result


def verify_actuals_restoration(path, plan):
    result = verify_restoration_unused(path, plan)
    actual = result.get("native_actuals") or {}
    require(
        actual.get("passed") is True
        and actual.get("method") == "sleeper-matchup-actuals-v1"
        and actual.get("source_generation")
        and actual["source_generation"] == actual.get("admitted_generation")
        and actual.get("expected_first_scores") == [0, -2.125]
        and actual.get("admitted_first_scores") == actual["expected_first_scores"]
        and actual.get("league_id")
        and actual.get("season")
        and actual.get("scoring_fingerprint")
        and type(actual.get("observations")) is int
        and actual["observations"] > 0,
        "Native actuals restoration parity or source identity missing",
    )
    return result


def verify_resident_refresh(path, plan):
    """Real terminal ownership, active readers and capacity recovery; not live parity."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("evidence/result.json"))
        require(
            result.get("schema") == "resident-refresh-ownership-v2"
            and result.get("passed") is True
            and result.get("head") == plan["candidate"]
            and result.get("tree") == plan["tree"]
            and result.get("working_tree_clean") is True,
            "Resident refresh source or completion mismatch",
        )
        require(
            result.get("cgroup_limit") == 2147483648
            and result.get("swap_limit") == 0
            and result.get("cpus") == 2
            and result.get("network") == "none"
            and result.get("children_after") == []
            and result.get("scratch_removed") is True
            and result.get("source_values_preserved") is True,
            "Resident refresh resource/cleanup proof missing",
        )
        cases = result.get("cases", [])
        require(
            len(cases) == 4
            and [
                (x.get("name"), x.get("failed_refresh"), x.get("reader"))
                for x in cases[:3]
            ]
            == [
                ("oneqb", False, False),
                ("oneqb", True, False),
                ("superflex", False, True),
            ],
            "Resident refresh case population mismatch",
        )
        for case in cases[:3]:
            require(
                case.get("completed") is True
                and case.get("invalid_restore_preserved_current") is True
                and case.get("repeated_switches") == 3
                and case.get("cancellation_writer_drained") is True
                and case.get("old_released_without_reader") is (not case["reader"])
                and re.fullmatch("[0-9a-f]{64}", case.get("source_digest", "")),
                "Resident refresh real execution/ownership missing",
            )
        reader = cases[2]
        require(
            all(
                reader.get(k) is True
                for k in ("pressure_deferred", "fois_protected", "recovery_completed")
            )
            and type(reader.get("relieved_fixture_bytes")) is int
            and reader["relieved_fixture_bytes"] > 0
            and reader.get("owner_release_plan", {}).get("telemetry_valid") is True
            and reader.get("recovery_plan", {}).get("would_admit") is True,
            "Resident refresh deferral/FOIS/recovery missing",
        )
        global_owner = cases[3]
        require(
            global_owner.get("name") == "global-evidence"
            and all(
                global_owner.get(k) is True
                for k in (
                    "completed",
                    "old_released_without_reader",
                    "source_acquisition_mocked",
                    "source_restoration_completed",
                    "scheduler_cancelled",
                )
            )
            and re.fullmatch("[0-9a-f]{64}", global_owner.get("source_digest", "")),
            "Global scheduler ownership/restoration proof missing",
        )
        samples = result.get("samples", [])
        require(
            samples
            and all(
                x.get("cgroup_limit_bytes") == 2147483648
                and not x.get("cgroup_memory_events", {}).get("oom_kill")
                for x in samples
            ),
            "Resident refresh cgroup evidence missing",
        )
        require(
            result.get("liveness")
            and all(
                isinstance(x.get("server_ms"), (int, float))
                and 0 <= x["server_ms"] < 500
                for x in result["liveness"]
            ),
            "Resident refresh liveness failed",
        )
        for line in archive.read("SHA256SUMS").decode().splitlines():
            expected, name = line.split("  ", 1)
            require(
                name in {"evidence/result.json", "raw.log"}
                and hashlib.sha256(archive.read(name)).hexdigest() == expected,
                "Resident refresh checksum mismatch",
            )
        require(
            {
                line.split("  ", 1)[1]
                for line in archive.read("SHA256SUMS").decode().splitlines()
            }
            == {"evidence/result.json", "raw.log"},
            "Resident refresh checksum population missing",
        )
    return result


def verify_local_recovery(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("local-canonical/result.json"))
        require(
            result["head"] == plan["candidate"] and result["tree"] == plan["tree"],
            "Local canonical source mismatch",
        )
        require(
            result["passed"] is True
            and result["exit_code"] == 0
            and result["cgroup_limit"] == 2147483648
            and result["cpus"] == 2
            and result["network"] == "none",
            "Local canonical acceptance missing",
        )
        require(
            str(result.get("python", "")).split(" ", 1)[0] == plan["python_version"],
            "Local canonical Python runtime mismatch",
        )
        require(
            not result["final_memory"]["cgroup_memory_events"].get("oom_kill"),
            "Local canonical OOM",
        )
        events = Counter(
            json.loads(line)["event"]
            for line in archive.read("local-canonical/tests.jsonl").splitlines()
        )
        require(
            events["start"] == events["stop"] == plan["canonical_tests"]
            and not any(events[x] for x in ("failure", "error", "skip")),
            "Local regression incomplete",
        )
        trace = [
            json.loads(line)
            for line in archive.read(
                "local-canonical/canonical-trace.jsonl"
            ).splitlines()
        ]
        completed = [x for x in trace if x.get("event") == "validation_child_completed"]
        require(
            len(completed) == 10
            and all(x["return_code"] == 0 for x in completed)
            and any(
                x.get("event") == "validator_final_summary" and x.get("gates") == 10
                for x in trace
            ),
            "Local canonical gates incomplete",
        )
        require(
            "local-canonical/manifest.json" in archive.namelist(),
            "Local canonical manifest missing",
        )
        manifest = json.loads(archive.read("local-canonical/manifest.json"))
        require(
            len(manifest) == plan["local_canonical_entries"],
            "Local canonical manifest population mismatch",
        )
        names = set()
        for entry in manifest:
            require(
                entry["name"] not in names, "Duplicate local canonical manifest row"
            )
            names.add(entry["name"])
            payload = archive.read("local-canonical/" + entry["name"])
            require(
                len(payload) == entry["bytes"]
                and hashlib.sha256(payload).hexdigest() == entry["sha256"],
                "Local canonical payload checksum mismatch",
            )
        verify_canonical_sums(archive, manifest, "local-canonical/")
    return result


def verify_trade_time_market(path, plan):
    """Per-asset feature evidence; supplied live counts are never fixture parity."""
    with zipfile.ZipFile(path) as archive:
        phone = json.loads(archive.read("feature/browser.json"))
        feature = json.loads(archive.read("feature/feature.json"))
        supplied = json.loads(archive.read("supplied-screen.json"))
    require(
        phone.get("head") == feature.get("head") == plan["candidate"]
        and phone.get("tree") == feature.get("tree") == plan["tree"]
        and phone.get("working_tree_clean") is True
        and feature.get("working_tree_clean") is True,
        "Trade-time feature source mismatch",
    )
    records = phone.get("records", [])
    require(
        len(records) == 4
        and {(r.get("width"), r.get("height")) for r in records}
        == {(320, 432), (375, 667), (390, 844), (1280, 900)},
        "Trade-time phone coverage missing",
    )
    require(
        all(
            r.get("keyboard") is True
            and r.get("overflow") is False
            and r.get("touch_emulated") is (r["width"] < 500)
            and r.get("source_value") == 321
            and r.get("age_seconds") == 3600
            and r.get("extra_disclosure_requests") == 0
            and r.get("errors") == []
            for r in records
        ),
        "Trade-time disclosure evidence failed",
    )
    cases = feature.get("cases", [])
    expected = {
        "newer_incompatible": 400,
        "newer_foreign": 400,
        "partial_old": 275,
        "zero": 0,
        "conflicting": None,
    }
    require(
        len(cases) == len(expected) and {r.get("case") for r in cases} == set(expected),
        "Trade-time matched population missing",
    )
    require(
        all(
            r.get("selected_value") == expected[r["case"]]
            and r.get("package_totals_displayed") is False
            and r.get("retained_fixture_values")
            for r in cases
        ),
        "Trade-time quote selection mismatch",
    )
    require(
        supplied.get("provenance", "").startswith("Supplied Main Chat")
        and supplied.get("exhaustive") is False
        and supplied.get("complete_package_coverage") == "Not established"
        and supplied.get("historical_league_format_parity") == "Not established",
        "Supplied coverage overstated",
    )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Disposable per-asset feature and phone controls; live coverage attributed to Main Chat",
    }


def verify_activation_deferral(path, plan, prefix="browser/activation/"):
    """Require typed deferral and a real explicit retry, never a live-access claim."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:

        def report(name):
            row = json.loads(archive.read(prefix + name + ".json"))
            require(
                row.get("commit") == plan["candidate"]
                and row.get("tree") == plan["tree"]
                and row.get("working_tree_clean") is True,
                "Activation source mismatch",
            )
            require(
                row.get("physical_safari_tested") is False
                and row.get("scope")
                == "Disposable authenticated native route/manager/guard controls; modeled telemetry identified, not live Granite",
                "Activation scope mismatch",
            )
            return row["observations"]

        deferred = report("typed-capacity")
        require(
            deferred.get("html") == 503
            and deferred.get("api", {}).get("status") == "deferred"
            and deferred["api"].get("code") == "league_preparation_waiting"
            and deferred.get("retry_after") == "60"
            and deferred.get("account_unchanged") is True
            and deferred.get("source_requests") == 0
            and deferred.get("actual_hydrations") == 1,
            "Typed activation deferral missing",
        )
        retry = report("real-recovery")
        require(
            retry.get("initial") == 503
            and retry.get("explicit_retry") == 303
            and retry.get("warm") is True
            and retry.get("source_values_preserved") is True
            and retry.get("source_requests") == 0
            and retry.get("limitation")
            == "Small compatible fixture, actual enforced memory telemetry; not private Granite payload or live acceptance",
            "Actual activation retry completion missing",
        )
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            row = report("phone-" + str(width))
            require(
                row.get("viewport") == [width, height]
                and row.get("status") == 503
                and row.get("retry_after") == "60"
                and all(
                    row.get(k) is True
                    for k in (
                        "no_overflow",
                        "no_new_source_requests",
                        "account_unchanged",
                    )
                ),
                "Activation phone coverage missing",
            )
            require(
                archive.read(prefix + "phone-" + str(width) + ".png").startswith(
                    b"\x89PNG\r\n\x1a\n"
                ),
                "Activation phone image missing",
            )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Disposable native activation routes with guarded actual retry; live Granite access unverified",
    }


def verify_front_office_workflow(path, plan, prefix="browser/front-office-workflow/"):
    """Pin native workflow evidence without requiring discovery to endorse an offer."""
    verify_zip(path)
    views = {(320, 432), (375, 667), (390, 844), (1280, 900)}
    protected = {"2029-R1-1", "a"}

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def ids(value):
        return (
            isinstance(value, list)
            and bool(value)
            and all(text(x) for x in value)
            and len(value) == len(set(value))
        )

    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)

    def view_rows(value, name):
        require(
            isinstance(value, list)
            and len(value) == 4
            and all(isinstance(r, dict) for r in value)
            and {(r.get("width"), r.get("height")) for r in value} == views,
            "Front office viewport coverage missing: " + name,
        )
        return value

    with zipfile.ZipFile(path) as archive:
        for name in ("1qb-k-def-journey", "superflex-journey"):
            report = json.loads(archive.read(prefix + name + ".json"))
            require(
                isinstance(report, dict)
                and report.get("commit") == plan["candidate"]
                and report.get("tree") == plan["tree"]
                and report.get("working_tree_clean") is True,
                "Front office source mismatch",
            )
            require(
                report.get("source")
                == "Disposable authenticated prepared Sleeper fixture; native search and canonical evaluator"
                and report.get("physical_safari_tested") is False,
                "Front office scope mismatch",
            )
            row = report.get("observations")
            require(isinstance(row, dict), "Front office observations missing")
            require(
                archive.read(prefix + name + ".png").startswith(b"\x89PNG\r\n\x1a\n"),
                "Front office journey image missing",
            )
            slots = row.get("league_slots")
            require(
                isinstance(slots, list)
                and all(text(s) for s in slots)
                and slots.count("QB") == 1
                and (
                    slots.count("SUPER_FLEX") == 1
                    and "K" not in slots
                    and "DEF" not in slots
                    if name == "superflex-journey"
                    else "SUPER_FLEX" not in slots
                    and slots.count("K") == slots.count("DEF") == 1
                ),
                "Front office league configuration missing",
            )
            handoff, payload = row.get("handoff"), row.get("generation_payload")
            require(
                isinstance(handoff, dict) and isinstance(payload, dict),
                "Front office handoff/request missing",
            )
            position, href = handoff.get("position"), handoff.get("href")
            require(
                position in ("QB", "RB", "WR", "TE") and text(href),
                "Front office need identity missing",
            )
            url = urlsplit(href)
            query = parse_qs(url.query, keep_blank_values=True)
            fingerprint = query.get("team_need", [None])[0]
            require(
                not url.scheme
                and not url.netloc
                and url.path == "/trades/recommended"
                and query == {"front_office": ["1"], "team_need": [fingerprint]}
                and isinstance(fingerprint, str)
                and re.fullmatch("[0-9a-f]{64}", fingerprint),
                "Front office need fingerprint mismatch",
            )
            require(
                handoff.get("existing_my_team_reused") is True
                and text(handoff.get("explanation"))
                and position + " addition" in handoff["explanation"]
                and "Change or clear, then Generate" in handoff["explanation"]
                and handoff.get("initial_choice")
                == {"fingerprint": fingerprint, "position": position, "manual": False}
                and handoff.get("edited_choice")
                == {"fingerprint": fingerprint, "position": "", "manual": True},
                "Front office editable need reason missing",
            )
            for view in view_rows(row.get("home"), "home"):
                require(
                    text(view.get("title"))
                    and view.get("href") == href
                    and view.get("action") == f"Explore {position} trades →",
                    "Front office Home handoff mismatch",
                )
            for view in view_rows(row.get("protection_views"), "protections"):
                require(
                    ids(view.get("exact_ids")) and set(view["exact_ids"]) == protected,
                    "Front office protected viewport identity mismatch",
                )
            context = payload.get("workspace_context")
            require(
                isinstance(context, dict)
                and text(context.get("binding"))
                and context.get("league_id") == "league-1"
                and context.get("roster_id") == payload.get("active_roster_id") == 1
                and payload.get("workflow") == "recommended"
                and payload.get("partner_roster_id") == 0
                and payload.get("recommendation_position") == position
                and ids(payload.get("protected_assets"))
                and set(payload["protected_assets"]) == protected,
                "Front office authorized generation scope mismatch",
            )
            constraints = row.get("applied_constraints")
            require(
                isinstance(constraints, dict)
                and ids(constraints.get("protected_assets"))
                and set(constraints["protected_assets"]) == protected
                and ids(row.get("exact_protected_ids"))
                and set(row["exact_protected_ids"]) == protected,
                "Front office applied protection snapshot mismatch",
            )
            pools = row.get("outgoing_pools")
            require(
                isinstance(pools, list)
                and bool(pools)
                and all(ids(pool) for pool in pools)
                and any("2029-R1-3" in pool for pool in pools)
                and all(protected.isdisjoint(pool) for pool in pools)
                and row.get("distinct_same_round_pick") == "2029-R1-3"
                and row.get("distinct_pick_remained_eligible") is True,
                "Front office actual construction isolation missing",
            )
            native = row.get("native_offers")
            require(
                isinstance(native, list), "Front office native offer population missing"
            )
            for offer in native:
                require(
                    isinstance(offer, dict)
                    and offer.get("family")
                    in ("results", "exploratory_results", "near_misses")
                    and isinstance(offer.get("proposal"), dict),
                    "Front office native offer malformed",
                )
                proposal = offer["proposal"]
                require(
                    proposal.get("active_roster_id") == 1
                    and type(proposal.get("partner_roster_id")) is int
                    and proposal["partner_roster_id"] > 1
                    and ids(proposal.get("assets_sent"))
                    and ids(proposal.get("assets_received"))
                    and protected.isdisjoint(proposal["assets_sent"]),
                    "Front office protected asset escaped to native offer",
                )
                require(
                    "recommendation" in offer
                    and (
                        text(offer["recommendation"])
                        or offer["family"] == "near_misses"
                        and offer["recommendation"] is None
                    )
                    and type(offer.get("exploration")) is bool
                    and (
                        offer.get("generated_trade_eligible") is None
                        or type(offer.get("generated_trade_eligible")) is bool
                    )
                    and (
                        offer["family"] != "exploratory_results"
                        or offer["exploration"] is True
                    )
                    and (
                        offer.get("generated_trade_eligible") is not True
                        or offer["family"] == "results"
                        and offer["exploration"] is False
                    ),
                    "Front office native offer qualification missing",
                )
            prior = row.get("prior_search")
            require(
                isinstance(prior, dict)
                and prior.get("position") == position
                and prior.get("type") == payload.get("recommendation_filter")
                and type(prior.get("count")) is int
                and prior["count"]
                == sum(offer["family"] != "near_misses" for offer in native)
                and isinstance(prior.get("protections"), list)
                and len(prior["protections"]) == 2
                and all(
                    isinstance(fact, dict) and text(fact.get("label"))
                    for fact in prior["protections"]
                )
                and {fact.get("id") for fact in prior["protections"]} == protected,
                "Front office prior applied settings missing",
            )
            ledger, requests = row.get("post_ledger"), row.get("post_requests")
            paths = ["/api/trades/generate"] + ["/api/trades/evaluate"] * 3
            require(
                isinstance(ledger, list)
                and len(ledger) == 4
                and all(isinstance(r, dict) for r in ledger)
                and [r.get("path") for r in ledger] == paths
                and all(
                    r.get("status") == 200 and isinstance(r.get("payload"), dict)
                    for r in ledger
                )
                and requests == [["POST", route, 200] for route in paths]
                and ledger[0]["payload"] == payload,
                "Front office unexpected or incomplete POST ledger",
            )
            for index, entry in enumerate(ledger[1:]):
                request = entry["payload"]
                bound = request.get("workspace_context")
                require(
                    isinstance(bound, dict)
                    and bound.get("binding") == context["binding"]
                    and bound.get("league_id") == context["league_id"]
                    and bound.get("roster_id") == 1
                    and request.get("active_roster_id") == 1
                    and request.get("partner_roster_id") == 2
                    and request.get("protected_assets") == []
                    and request.get("assets_sent")
                    == (["2028-R1-3", "a"] if index == 1 else ["a"])
                    and request.get("assets_received") == [["d"], ["c"], ["f"]][index],
                    "Front office independent Evaluate or replacement scope mismatch",
                )
            evaluations, selected = (
                row.get("actual_evaluations"),
                row.get("comparison_offers"),
            )
            require(
                isinstance(evaluations, list)
                and len(evaluations) == 2
                and all(
                    isinstance(e, dict)
                    and "recommendation" in e
                    and (e["recommendation"] is None or text(e["recommendation"]))
                    and isinstance(e.get("market"), dict)
                    for e in evaluations
                )
                and isinstance(selected, list)
                and len(selected) == 2
                and all(isinstance(e, dict) for e in selected),
                "Front office two native assessments missing",
            )
            baselines = []
            for index, offer in enumerate(selected):
                base, summary, identity = (
                    offer.get("baseline"),
                    offer.get("summary"),
                    offer.get("identity"),
                )
                require(
                    isinstance(base, dict)
                    and isinstance(summary, dict)
                    and isinstance(identity, dict)
                    and offer.get("scope")
                    == {
                        "binding": context["binding"],
                        "league": context["league_id"],
                        "roster": 1,
                    }
                    and base.get("league") == context["league_id"]
                    and base.get("roster") == 1
                    and base.get("ownership") == context.get("ownership_generation")
                    and all(
                        text(base.get(k))
                        for k in ("ownership", "lineup", "scoring", "projection")
                    )
                    and type(base.get("season")) is int
                    and base["season"] > 0
                    and type(base.get("week")) is int
                    and base["week"] > 0
                    and base.get("provider") == "Sleeper"
                    and identity.get("binding") == context["binding"]
                    and identity.get("ownership") == base["ownership"]
                    and text(identity.get("market"))
                    and text(summary.get("verdict"))
                    and summary.get("mode") in ("neutral", "custom"),
                    "Front office source-qualified comparison missing",
                )
                proposal = {
                    key: ledger[index + 1]["payload"][key]
                    for key in (
                        "active_roster_id",
                        "partner_roster_id",
                        "assets_sent",
                        "assets_received",
                    )
                }
                require(
                    offer.get("proposal") == proposal,
                    "Front office comparison package/order mismatch",
                )
                try:
                    package = json.loads(identity.get("package", "null"))
                except (TypeError, ValueError):
                    package = None
                require(
                    package
                    == [
                        proposal["partner_roster_id"],
                        sorted(proposal["assets_sent"]),
                        sorted(proposal["assets_received"]),
                    ],
                    "Front office assessment package identity mismatch",
                )
                market = evaluations[index]["market"]
                require(
                    isinstance(market.get("sent"), dict)
                    and isinstance(market.get("received"), dict)
                    and summary.get("neutral")
                    == {
                        "availability": market.get("availability"),
                        "sent": market["sent"].get("total"),
                        "received": market["received"].get("total"),
                    },
                    "Front office recorded Market values changed",
                )
                lineup = summary.get("lineup")
                require(
                    isinstance(lineup, dict)
                    and lineup.get("state") == "supported"
                    and all(
                        finite(lineup.get(k))
                        for k in ("pre_total", "post_total", "delta")
                    )
                    and lineup.get("weeks") == [base["week"]]
                    and math.isclose(
                        lineup["post_total"] - lineup["pre_total"],
                        lineup["delta"],
                        rel_tol=0,
                        abs_tol=1e-8,
                    ),
                    "Front office supported comparison numbers missing",
                )
                native_lineup = evaluations[index].get("lineup")
                require(
                    isinstance(native_lineup, dict)
                    and all(
                        native_lineup.get(k) == lineup.get(k)
                        for k in ("state", "weeks", "pre_total", "post_total", "delta")
                    )
                    and all(
                        native_lineup.get(source) == lineup.get(source) == base[stored]
                        for source, stored in (
                            ("season", "season"),
                            ("league_id", "league"),
                            ("scoring_profile_id", "scoring"),
                            ("projection_generation", "projection"),
                        )
                    ),
                    "Front office original lineup evidence changed",
                )
                baselines.append(base)
            require(
                baselines[0] == baselines[1]
                and selected[0]["summary"]["lineup"]["pre_total"]
                == selected[1]["summary"]["lineup"]["pre_total"]
                and selected[0]["identity"]["market"]
                == selected[1]["identity"]["market"],
                "Front office shared comparison source mismatch",
            )
            expected_draft = {
                "partner": 2,
                "sent": ["2028-R1-3", "a"],
                "received": ["c"],
            }
            for view in view_rows(
                row.get("comparison_and_history"), "comparison/history"
            ):
                require(
                    view.get("exact_draft") == expected_draft
                    and view.get("panel_state") in ("recorded", "retained")
                    and view.get("keep_option") == "Keep the roster · no trade"
                    and view.get("comparison_retained") is True
                    and view.get("history_qualification") == "retained"
                    and view.get("history_return_without_post") is True,
                    "Front office retained comparison/history control missing",
                )
            replacement = row.get("replacement")
            require(
                isinstance(replacement, dict)
                and row.get("reload_retained") is True
                and replacement.get("selected_proposals")
                == [
                    {
                        key: ledger[3]["payload"][key]
                        for key in (
                            "active_roster_id",
                            "partner_roster_id",
                            "assets_sent",
                            "assets_received",
                        )
                    },
                    selected[1]["proposal"],
                ]
                and replacement.get("remaining_proposals") == [selected[1]["proposal"]]
                and replacement.get("draft")
                == {"partner": 2, "sent": ["a"], "received": ["f"]},
                "Front office reload or replacement/removal missing",
            )
            scope = row.get("scope_change")
            require(
                isinstance(scope, dict)
                and scope.get("old") == context["binding"]
                and text(scope.get("current"))
                and scope["old"] != scope["current"]
                and scope.get("temporary_state_cleared") is True
                and ids(scope.get("before_protections"))
                and set(scope["before_protections"]) == protected
                and scope.get("before_position") == "QB"
                and scope.get("before_draft") == replacement["draft"]
                and row.get("saved_goal_and_rankings_unchanged") is True,
                "Front office league clearing or saved preferences changed",
            )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Disposable native prepared 1QB/K/DEF and Superflex workflows; no qualified-discovery, live owner or physical Safari claim",
    }


def verify_recommended_protections(path, plan, prefix="browser/protections/"):
    """Exact native exclusions and independent draft controls on the pinned source."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:

        def report(name):
            row = json.loads(archive.read(prefix + name + ".json"))
            require(
                row.get("commit") == plan["candidate"]
                and row.get("tree") == plan["tree"]
                and row.get("working_tree_clean") is True,
                "Recommended protection source mismatch",
            )
            require(
                row.get("source")
                == "Disposable prepared Sleeper fixture; actual authenticated routes, canonical search and admission"
                and row.get("physical_safari_tested") is False,
                "Recommended protection scope invalid",
            )
            return row["observations"]

        expected = {"2029-R1-1", "a"}
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            row = report("phone-" + str(width))
            require(
                row.get("width") == width
                and row.get("height") == height
                and set(row.get("exact_ids", [])) == expected
                and row.get("no_search_from_controls") is True,
                "Recommended phone control missing",
            )
            require(
                archive.read(prefix + "phone-" + str(width) + ".png").startswith(
                    b"\x89PNG\r\n\x1a\n"
                ),
                "Recommended phone screenshot missing",
            )
        row = report("exact-native-search")
        pools = row.get("candidate_pools", [])
        offers = row.get("offers", [])
        require(
            set(row.get("payload", {}).get("protected_assets", [])) == expected
            and set(row.get("constraints", {}).get("protected_assets", [])) == expected,
            "Native protection request/result mismatch",
        )
        require(
            pools
            and any("2029-R1-3" in pool for pool in pools)
            and all(expected.isdisjoint(pool) for pool in pools),
            "Exact pick construction isolation missing",
        )
        require(
            offers
            and all(
                expected.isdisjoint(offer["proposal"]["assets_sent"])
                for offer in offers
            )
            and row.get("saved_preferences_unchanged") is True,
            "Protected asset escaped to native results",
        )
        row = report("clear-and-prior-results")
        require(
            row.get("old_results_not_relabeled") is True
            and row.get("clearing_did_not_search") is True
            and row.get("second_constraints", {}).get("protected_assets") == []
            and "2029-R1-1"
            in row.get("first_constraints", {}).get("protected_assets", []),
            "Cleared protections or old search identity missing",
        )
        row = report("draft-and-scope")
        require(
            row.get("real_evaluations") == 2
            and all(
                row.get(k) is True
                for k in (
                    "recommended_controls_not_applied_to_evaluate",
                    "original_draft_retained",
                    "comparison_proposals_retained",
                    "reload_retained",
                    "league_switch_cleared",
                )
            ),
            "Recommended draft/scope isolation missing",
        )
        row = report("completed-zero-result")
        require(
            row.get("completed") is True
            and row.get("no_protection_causality_claim") is True
            and not row.get("body", {}).get("results")
            and not row.get("body", {}).get("exploratory_results")
            and row.get("payload", {}).get("protected_assets"),
            "Native completed zero search missing",
        )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Exact temporary exclusions through actual fixture search/admission and phone UI; not owner live acceptance",
    }


def verify_offer_comparison(path, plan, prefix="browser/offer-comparison/"):
    """Require source-bound native evaluations and a request-free phone review."""
    verify_zip(path)
    views = {(320, 432), (375, 667), (390, 844), (1280, 900)}
    with zipfile.ZipFile(path) as archive:

        def report(name):
            row = json.loads(archive.read(prefix + name + ".json"))
            require(
                row.get("commit") == plan["candidate"]
                and row.get("tree") == plan["tree"]
                and row.get("working_tree_clean") is True,
                "Offer comparison source mismatch",
            )
            require(
                row.get("source")
                == "Disposable authenticated prepared Sleeper fixture; actual canonical evaluator"
                and row.get("physical_safari_tested") is False,
                "Offer comparison evidence scope",
            )
            return row.get("observations")

        rows = report("phone-round-trips")
        require(
            isinstance(rows, list)
            and len(rows) == 4
            and {(r.get("width"), r.get("height")) for r in rows} == views
            and all(
                r.get("preserved_draft") is True and r.get("no_http") is True
                for r in rows
            ),
            "Offer comparison phone round trip missing",
        )
        for width, height in views:
            row = report("phone-" + str(width))
            require(
                row.get("width") == width
                and row.get("height") == height
                and row.get("independent_evaluations") == 2
                and all(
                    row.get(k) is True
                    for k in (
                        "no_http",
                        "higher_gain_higher_cost",
                        "asset_order_preserved",
                    )
                ),
                "Offer comparison actual native evaluation missing",
            )
            gains, costs = row.get("native_deltas"), row.get("native_sent_market")
            require(
                isinstance(gains, list)
                and isinstance(costs, list)
                and len(gains) == len(costs) == 2
                and all(
                    type(v) in (int, float) and math.isfinite(v) for v in gains + costs
                )
                and gains[1] > gains[0]
                and costs[1] > costs[0],
                "Offer comparison gain/cost control invalid",
            )
            require(
                archive.read(prefix + "phone-" + str(width) + ".png").startswith(
                    b"\x89PNG\r\n\x1a\n"
                ),
                "Offer comparison phone screenshot missing",
            )
        controls = {
            "superflex-depth-replace-remove": (
                "missing_depth_qualified",
                "counterparty_attached",
                "explicit_replacement",
                "no_http",
            ),
            "neutral-custom": (
                "neutral_values_match_originals",
                "custom_values_match_original",
                "modes_separate",
                "no_http",
            ),
            "partial-pair": (
                "supported_individual_delta_preserved",
                "incomplete_other_lineup_unknown",
                "no_http",
            ),
            "two-generations": (
                "incompatible_generations_withheld",
                "original_packages_retained",
                "no_http",
            ),
            "aged-incompatible": (
                "shared_numbers_withheld",
                "retained_offer_visible",
                "no_http",
            ),
            "retained-reload": (
                "same_prepared_generation",
                "retained_qualification_visible",
                "exact_draft",
                "no_http",
            ),
            "custom-incomplete-reload": (
                "same_prepared_generation",
                "original_incomplete_lineup_preserved",
                "draft_mode_does_not_mutate_selected_assessment",
                "retained_qualification_visible",
                "exact_draft",
                "no_http",
            ),
            "recommendation-league-scope": (
                "no_comparison_search",
                "no_adoption",
                "league_switch_discards_comparison",
            ),
        }
        for name, keys in controls.items():
            row = report(name)
            require(
                all(row.get(k) is True for k in keys),
                "Offer comparison control missing: " + name,
            )
            if name == "recommendation-league-scope":
                require(
                    row.get("real_searches") == 1
                    and type(row.get("qualified_source_offers")) is int
                    and row["qualified_source_offers"] > 0,
                    "Offer comparison qualified native control absent",
                )
            if name in ("partial-pair", "two-generations", "neutral-custom"):
                require(
                    row.get("actual_evaluations") == 2,
                    "Offer comparison actual evaluation count missing",
                )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Disposable authenticated canonical 1QB/K/DEF and Superflex; original recorded offers only; no live owner/Safari claim",
    }


def verify_team_need_handoff(path, plan, prefix="browser/team-need/"):
    """Require source-bound real browser transitions, not deferred execution."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        reports = {}
        for name in (
            "phone-round-trips",
            "superflex-depth-and-stale",
            "real-search-and-prior-context",
            "league-switch",
        ):
            row = json.loads(archive.read(prefix + name + ".json"))
            require(
                row.get("commit") == plan["candidate"]
                and row.get("tree") == plan["tree"],
                "Team need source mismatch",
            )
            require(
                row.get("source") == "disposable authenticated prepared Sleeper fixture"
                and row.get("physical_safari_tested") is False,
                "Team need scope mismatch",
            )
            reports[name] = row.get("observations")
        rows = reports["phone-round-trips"]
        require(
            isinstance(rows, list)
            and len(rows) == 4
            and {(r.get("width"), r.get("height")) for r in rows}
            == {(320, 432), (375, 667), (390, 844), (1280, 900)},
            "Team need phone controls missing",
        )
        require(
            all(
                r.get("handoff") == "RB starter"
                and r.get("draft_and_custom_preserved") is True
                and r.get("changed_and_cleared_after_reload") is True
                and r.get("no_automatic_search") is True
                and r.get("position_visible_on_entry") is True
                and r.get("position_clear_of_back_bar") is True
                and r.get("type_filter_preserves_need_reason") is True
                and r.get("back") == "My Team"
                and r.get("overflow") == 0
                for r in rows
            ),
            "Team need draft or explicit search control failed",
        )
        depth = reports["superflex-depth-and-stale"]
        require(
            all(
                depth.get(k) is True
                for k in (
                    "depth_distinct",
                    "stale_hint_rejected",
                    "general_shortcut",
                    "no_automatic_search",
                    "stale_manual_filter_preserved",
                )
            ),
            "Team need depth or stale control failed",
        )
        real = reports["real-search-and-prior-context"]
        require(
            real.get("real_evaluations") is True
            and isinstance(real.get("prior_contexts"), int)
            and real["prior_contexts"] > 0
            and real.get("position_applied_only_on_generate") is True
            and real.get("old_results_separate") is True
            and real.get("explicit_reset_clears_prior_context") is True,
            "Team need completed evaluation absent",
        )
        switch = reports["league-switch"]
        require(
            all(
                switch.get(k) is True
                for k in (
                    "hint_discarded",
                    "old_draft_not_loaded",
                    "no_automatic_search",
                )
            ),
            "Team need league isolation failed",
        )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Disposable authenticated 1QB/K/DEF and Superflex source; real explicit evaluation; live owner acceptance unverified",
    }


def verify_partner_history_links(path, plan, prefix="trade-partner-history/"):
    """Require the actual source-pinned two-way browser journey, not seed data."""
    verify_zip(path)
    views = {(320, 432), (375, 667), (390, 844), (1280, 900)}
    with zipfile.ZipFile(path) as archive:
        for name, route in (("evaluation", "evaluate"), ("recommendation", "generate")):
            report = json.loads(archive.read(prefix + name + "-round-trip.json"))
            require(
                report.get("commit") == plan["candidate"]
                and report.get("tree") == plan["tree"],
                "Partner history feature source mismatch",
            )
            require(
                report.get("source")
                == "disposable prepared league; real authenticated HTTP and evaluator"
                and report.get("physical_safari_tested") is False,
                "Partner history evidence scope",
            )
            rows = report.get("checks", [])
            require(
                len(rows) == 4
                and {tuple(r.get("viewport", [])) for r in rows} == views,
                "Partner history viewports missing",
            )
            first = rows[0]
            for row in rows:
                require(
                    row.get("post_requests") == [["POST", "/api/trades/" + route, 200]],
                    "Partner history must not start another evaluation or search",
                )
                require(
                    row.get("draft") == first.get("draft"),
                    "Partner history changed original draft",
                )
                if name == "evaluation":
                    require(
                        row.get("mode") == "custom"
                        and row.get("filters") == first.get("filters")
                        and row.get("filters", {}).get("sent", {}).get("q") == "a"
                        and row.get("draft")
                        == {"sent": ["a"], "received": ["2028-R1-4"], "partner": 2},
                        "Partner history lost Custom evaluation, filters or exact pick",
                    )
                else:
                    proposal = row.get("preview", {})
                    require(
                        proposal == first.get("preview")
                        and proposal.get("partner_roster_id") == 2
                        and bool(proposal.get("assets_sent"))
                        and bool(proposal.get("assets_received"))
                        and row.get("draft")
                        == {"sent": [], "received": [], "partner": 0},
                        "Partner history lost preview or adopted the offer",
                    )
        expected = {
            prefix + flow + "-" + str(width) + "-" + stage + ".png"
            for flow in ("create", "recommended")
            for width, _ in views
            for stage in ("history", "returned")
        }
        observed = {
            n for n in archive.namelist() if n.startswith(prefix) and n.endswith(".png")
        }
        require(
            observed == expected
            and all(archive.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in observed),
            "Partner history phone and return screenshots missing",
        )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Disposable real authenticated round trips; no claim of live owner acceptance",
    }


def verify_completed_trade_browser(path, plan, prefix="completed-trade-observations/"):
    """Verify a separate named replay; preserve the original history journey."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read(prefix + "browser.json"))
        require(
            report.get("head") == plan["candidate"]
            and report.get("tree") == plan["tree"]
            and report.get("working_tree_clean") is True,
            "Completed trade feature source mismatch",
        )
        controls = (
            "Day retained trades; disposable waiver pagination",
            "Arkham sparse retained source",
        )
        expected = {
            (control, w, h)
            for control in controls
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        }
        rows = report.get("records", [])
        require(
            len(rows) == 8
            and {(r.get("control"), r.get("width"), r.get("height")) for r in rows}
            == expected,
            "Completed trade feature viewport population missing",
        )
        require(
            report.get("errors") == [] and report.get("server_thread_reaped") is True,
            "Completed trade feature errors or leaked server",
        )
        require(
            "retained source replay" in report.get("scope", "").lower()
            and "no fresh production observation" in report.get("scope", "").lower(),
            "Completed trade replay overstated as live",
        )
        for row in rows:
            require(row.get("overflow") is False, "Completed trade feature overflow")
            known = row["control"] == controls[0]
            require(
                all(
                    k in row
                    for k in ("supported_trades", "firsts_received", "firsts_sent")
                ),
                "Completed trade feature result fields unrecorded",
            )
            require(
                row.get("supported_trades") == (2 if known else None)
                and row.get("firsts_received") == (3 if known else None)
                and row.get("firsts_sent") == (1 if known else None),
                "Completed trade counts or unknown boundary changed",
            )
            require(
                row.get("keyboard") is known
                and row.get("contextual_back") is known
                and row.get("touch_emulated") is (known and row["width"] < 1000),
                "Completed trade feature interaction missing",
            )
        pngs = [
            n for n in archive.namelist() if n.startswith(prefix) and n.endswith(".png")
        ]
        require(
            len(pngs) == 8
            and all(archive.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in pngs),
            "Completed trade feature screenshots missing",
        )
        if prefix == "completed-trade-observations/":
            all_pngs = [n for n in archive.namelist() if n.endswith(".png")]
            require(
                len(all_pngs) == 16
                and all("/" not in n or n.startswith(prefix) for n in all_pngs),
                "Unexpected history screenshot namespace",
            )
    return {
        "passed": True,
        "head": plan["candidate"],
        "tree": plan["tree"],
        "scope": "Source-bound retained replay/disposable browser controls; authenticated live acceptance separate",
    }


def verify_completed_trade_cases(path, plan):
    with zipfile.ZipFile(path) as archive:
        feature = json.loads(archive.read("feature/feature.json"))
    require(
        feature.get("head") == plan["candidate"]
        and feature.get("tree") == plan["tree"]
        and feature.get("working_tree_clean") is True
        and feature.get("live_observation") is False,
        "Completed trade matched-case source or provenance mismatch",
    )
    require(
        feature.get("source_fixture_sha256")
        == "012de53aeefa4cfb4cb7de717910fa829f399b23d6f6ad7962598afe8c76833f",
        "Retained source fixture changed",
    )
    expected = {
        "retained_day": (2, 3, 1, 1, 1),
        "multi_team": (1, 2, 1, 1, 1),
        "partial_pick": (1, 1, None, 1, None),
        "supported_zero": (1, 0, 0, 0, 0),
        "unknown": (None, None, None, None, None),
    }
    cases = feature.get("cases", [])
    require(
        len(cases) == len(expected) and {r.get("case") for r in cases} == set(expected),
        "Completed trade matched population incomplete",
    )
    fields = (
        "completed_trades",
        "firsts_received",
        "firsts_sent",
        "receiving_trades",
        "sending_trades",
    )
    for case in cases:
        row = case.get("summary", {})
        require(all(k in row for k in fields), "Completed trade case fields unrecorded")
        require(
            tuple(row.get(k) for k in fields) == expected[case["case"]],
            "Completed trade asset/deal or missing-value mismatch",
        )
        require(
            row.get("state") == ("unknown" if case["case"] == "unknown" else "partial"),
            "Partial history overstated",
        )
        require(
            len(row.get("references", [])) <= 12, "Unbounded completed trade references"
        )
    by_name = {r["case"]: r["summary"] for r in cases}
    require(
        feature.get("raw_retained_expectations")
        == dict(zip(fields, expected["retained_day"])),
        "Raw retained comparison missing",
    )
    retained = by_name["retained_day"]
    require(
        retained.get("dated_trades") == 2
        and retained.get("first_completion_at", "").startswith("2026-03-01T")
        and retained.get("last_completion_at", "").startswith("2026-10-11T"),
        "Retained completion window mismatch",
    )
    incoming = {
        pick for ref in retained["references"] for pick in ref["firsts_received"]
    }
    outgoing = {pick for ref in retained["references"] for pick in ref["firsts_sent"]}
    require(
        incoming == {"PICK-2026-R1-ORIG8", "PICK-2027-R1-ORIG7", "PICK-2028-R1-ORIG7"}
        and outgoing == {"PICK-2026-R1-ORIG5"},
        "Exact retained pick direction/original franchise mismatch",
    )
    require(
        by_name["partial_pick"].get("pick_counts_complete_in_sample") is False
        and by_name["supported_zero"].get("pick_counts_complete_in_sample") is True,
        "Incomplete evidence silently became zero",
    )
    return {
        "passed": True,
        "matched_cases": 5,
        "source_fixture_sha256": feature["source_fixture_sha256"],
    }


def verify_franchise_progress_tests(path, plan, prefix=""):
    with zipfile.ZipFile(path) as archive:
        rows = [
            json.loads(line)
            for line in archive.read(prefix + "tests.jsonl").splitlines()
        ]
    selected = [
        r for r in rows if "test_franchise_trade_progress." in r.get("test", "")
    ]
    starts = [r["test"] for r in selected if r.get("event") == "start"]
    stops = [r["test"] for r in selected if r.get("event") == "stop"]
    require(
        plan.get("franchise_progress_tests") == 16
        and len(starts) == len(set(starts)) == 16
        and Counter(starts) == Counter(stops)
        and not any(r.get("event") in {"error", "failure", "skip"} for r in selected),
        "Franchise movement regression population incomplete or failed",
    )
    return starts


def verify_franchise_progress_browser(
    path, plan, prefix="completed-trade-observations/"
):
    result = verify_completed_trade_browser(path, plan, prefix=prefix)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read(prefix + "browser.json"))
    for row in report["records"]:
        known = row["control"].startswith("Day retained")
        require(
            row.get("season_filter") == (2026 if known else None)
            and row.get("filtered_pagination_conversion_return") is known
            and row.get("gross_player_transfers") == ([1, 3] if known else None)
            and row.get("gross_pick_transfers") == ([5, 2] if known else None),
            "Franchise movement season/transfer/conversion journey missing",
        )
    return {**result, "period_roundtrips": 4, "unknown_controls": 4}


def verify_franchise_progress_cases(path, plan):
    verify_completed_trade_cases(path, plan)
    with zipfile.ZipFile(path) as archive:
        feature = json.loads(archive.read("feature/feature.json"))
    rows = {r["case"]: r["summary"] for r in feature["cases"]}
    for kind, expected in (("player", (1, 3, -2)), ("pick", (5, 2, 3))):
        counts = rows["retained_day"].get("movements", {}).get(kind, {})
        require(
            tuple(counts.get(k) for k in ("acquired", "sent", "net")) == expected
            and counts.get("complete_in_sample") is True,
            "Retained gross/net movement mismatch",
        )
    unknown = rows["unknown"]
    require(
        unknown.get("assets") == []
        and all(
            unknown.get("movements", {}).get(kind, {}).get(k) is None
            for kind in ("player", "pick")
            for k in ("acquired", "sent", "net")
        ),
        "Unknown period turned into movement zero",
    )
    partial = rows["partial_pick"].get("movements", {})
    require(
        partial.get("pick", {}).get("net") is None
        and partial.get("pick", {}).get("complete_in_sample") is False
        and partial.get("player", {}).get("complete_in_sample") is True,
        "Incomplete picks contaminated supported player movement",
    )
    assets = rows["retained_day"].get("assets", [])
    converted = [
        a for a in assets if a.get("kind") == "player" and a.get("id") == "13346"
    ]
    require(
        len(converted) == 1
        and converted[0].get("acquired") == 0
        and converted[0].get("sent") == 1,
        "Pick conversion recounted as trade acquisition",
    )
    for row in rows.values():
        require(
            len(row.get("assets", [])) <= 256
            and all(len(a.get("references", [])) <= 4 for a in row.get("assets", [])),
            "Unbounded franchise movement detail",
        )
    return {
        "passed": True,
        "scope": "Retained source replay and disposable controls, not owner live acceptance",
    }


def verify_acquisition_tests(path, plan, prefix=""):
    with zipfile.ZipFile(path) as archive:
        rows = [
            json.loads(line)
            for line in archive.read(prefix + "tests.jsonl").splitlines()
        ]
    selected = [
        r
        for r in rows
        if r.get("test", "")
        .removeprefix("tests.")
        .startswith("test_trade_for_acquisition")
    ]
    starts = [r["test"] for r in selected if r.get("event") == "start"]
    stops = [r["test"] for r in selected if r.get("event") == "stop"]
    require(
        plan.get("acquisition_tests") == 20
        and len(starts) == len(set(starts)) == 20
        and Counter(starts) == Counter(stops)
        and not any(r.get("event") in {"failure", "error", "skip"} for r in selected),
        "Acquisition cost/fit regression incomplete or failed",
    )
    require(
        any(
            "AcquisitionIntegrationTests.test_actual_bounded_search" in name
            for name in starts
        )
        and any(
            "AcquisitionBrowserTests.test_cost_fit_preview" in name for name in starts
        ),
        "Actual search and rendered journey controls missing",
    )
    return starts


NORMAL_EXECUTION_TESTS = (
    "test_rebuild_discovery_browser.RebuildDiscoveryBrowserTests.test_real_unseeded_generation_and_zero_results_at_four_viewports",
    "test_rebuild_roster_space_browser.RebuildRosterSpaceBrowserTests.test_full_rosters_unseeded_strategies_and_qualified_zero_states_at_four_sizes",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_initial_reads_never_discover_and_intent_routes_are_distinct",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_unseeded_goals_and_exact_pick_exclusions_are_request_only",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_progress_duplicate_cancel_strategy_and_late_response",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_failure_retry_is_safe_and_does_not_reset_inputs",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_targeted_shop_entry_keeps_context_but_explicit_search_focuses_result",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_preparation_failure_retry_and_ready_controls",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_custom_neutral_modes_and_saved_rankings_survive_discovery",
    "test_trade_workflow_experience.TradeWorkflowExperienceTests.test_four_viewports_controls_results_disclosures_and_focus",
)


def verify_normal_execution_tests(path, plan, prefix=""):
    require(
        plan.get("fixture_isolation_tests") == 10, "Normal execution population missing"
    )
    with zipfile.ZipFile(path) as archive:
        rows = [
            json.loads(line)
            for line in archive.read(prefix + "tests.jsonl").splitlines()
        ]
    expected = set(NORMAL_EXECUTION_TESTS)
    selected = [row for row in rows if row.get("test") in expected]
    require(
        all(
            sum(
                row.get("test") == name and row.get("event") == event
                for row in selected
            )
            == 1
            for name in expected
            for event in ("start", "stop")
        )
        and not any(
            row.get("event") in ("error", "failure", "skip") for row in selected
        ),
        "Normal execution or completion population incomplete, failed or deferred",
    )
    return sorted(expected)


def verify_acquisition_recovery(path, plan):
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("focused-exact/result.json"))
        require(
            result["commit"] == plan["candidate"]
            and result["tree"] == plan["tree"]
            and result["dirty"] == []
            and result["passed"] is True
            and result["tests"] == 123
            and result["failures"] == result["errors"] == result["skipped"] == 0
            and result["memory_limit"] == 2147483648
            and not any(int(result["events"].get(k, 0)) for k in ("oom", "oom_kill")),
            "Acquisition focused source/resource/completion proof missing",
        )
        for width in (320, 375, 390, 1280):
            row = json.loads(
                archive.read(f"focused-exact/acquisition/phone-{width}.json")
            )
            require(
                row["width"] == width
                and row["physical_safari"] is False
                and row["no_overflow"] is True,
                "Acquisition responsive fixture coverage missing",
            )
            data = archive.read(f"focused-exact/acquisition/phone-{width}.png")
            require(
                data.startswith(b"\x89PNG\r\n\x1a\n")
                and int.from_bytes(data[16:20], "big") == width,
                "Acquisition screenshot width/source missing",
            )
            offers = row["rows"]
            require(
                len(offers) == 3
                and [x["proposal"]["assets_sent"] for x in offers]
                == [["player:a"], ["player:d"], ["player:b"]],
                "Acquisition prepared packages changed",
            )
            best, cheap = [x["acquisition_comparison"] for x in offers[:2]]
            require(
                best["roles"] == ["best_fit"]
                and cheap["roles"] == ["lowest_cost"]
                and best["cost"]["outgoing"] == 400
                and cheap["cost"]["outgoing"] == 100
                and best["cost"]["extra_received_asset_ids"] == ["player:y"]
                and best["cost"]["extra_received_value"] == 100
                and best["cost"]["net_received_minus_sent"] == 300
                and cheap["cost"]["extra_received_asset_ids"] == []
                and offers[1]["evaluation"]["recommendation"] == "FAIR / OPTIONAL"
                and offers[1]["evaluation"]["generated_trade_eligible"] is False,
                "Cost vs fit/extras/optional distinction lost",
            )
            require(
                len(row["operations"]) == 1
                and row["operations"][0]["path"] == "generate",
                "Inspection/comparison/Back initiated incidental work",
            )
    return {
        "passed": True,
        "candidate": plan["candidate"],
        "tree": plan["tree"],
        "focused_tests": 123,
        "widths": [320, 375, 390, 1280],
        "source": "Disposable prepared controls; no live or physical Safari claim",
    }


def verify_prior_evidence(path, plan):
    """Prior attempts are integrity evidence, never substitutes for final gates."""
    require(
        digest(path) == plan["prior_evidence_sha256"], "Prior evidence archive changed"
    )
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        meta = json.loads(archive.read("prior-manifest.json"))
        require(
            meta["candidate"] == plan["candidate"]
            and meta["tree"] == plan["tree"]
            and meta["scope"] == "prior-attempts-only",
            "Prior evidence association mismatch",
        )
        names = set()
        for entry in meta["files"]:
            require(entry["name"] not in names, "Duplicate prior manifest row")
            names.add(entry["name"])
            data = archive.read(entry["name"])
            require(
                len(data) == entry["bytes"]
                and hashlib.sha256(data).hexdigest() == entry["sha256"],
                "Prior evidence payload mismatch",
            )
        require(
            set(archive.namelist()) == names | {"prior-manifest.json"},
            "Unmanifested prior evidence",
        )


def verify_preflight(path, plan):
    """Exact-source metadata-only admission under the actual 2 GiB limit."""
    verify_zip(path)
    expected_cases = {
        "healthy": ("would_admit", "sufficient_headroom"),
        "capacity_deferred": ("would_defer", "insufficient_headroom"),
        "pressure_relieved": ("would_admit", "sufficient_headroom"),
        "fois_reserve_protected": ("would_defer", "insufficient_headroom"),
        "fois_released_same_pressure": ("would_admit", "sufficient_headroom"),
    }
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("result.json"))
        require(
            result["head"] == plan["candidate"] and result["tree"] == plan["tree"],
            "Preflight source mismatch",
        )
        require(
            result.get("passed") is True and result.get("complete") is True,
            "Preflight incomplete",
        )
        require(
            result.get("enforced_limit") == 2147483648
            and result.get("swap_limit") == 0,
            "Preflight enforced limit missing",
        )
        require(
            type(result.get("kernel_peak_bytes")) is int
            and 0 < result["kernel_peak_bytes"] <= 2147483648,
            "Preflight exceeded enforced memory",
        )
        require(
            result.get("scratch_removed") is True
            and result.get("children_after") == []
            and result.get("runtime_population_unchanged") is True
            and result.get("no_private_payload_decoded") is True,
            "Preflight cleanup or read-only proof missing",
        )
        require(
            result.get("guarded_operation_calls") == [0, 0, 0, 0, 0],
            "Preflight started prohibited work",
        )
        memory = result.get("final_memory") or {}
        require(
            memory.get("cgroup_limit_bytes") == 2147483648
            and not (memory.get("cgroup_memory_events") or {}).get("oom")
            and not (memory.get("cgroup_memory_events") or {}).get("oom_kill"),
            "Preflight final memory evidence failed",
        )
        rows = result.get("cases") or []
        require(
            len(rows) == len(expected_cases)
            and Counter(r.get("name") for r in rows) == Counter(expected_cases.keys()),
            "Preflight cases missing or duplicated",
        )
        by_name = {row["name"]: row for row in rows}
        for name, expected in expected_cases.items():
            response = by_name[name].get("response") or {}
            require(
                (response.get("verdict"), response.get("reason")) == expected,
                "Preflight verdict evidence mismatch",
            )
            require(
                response.get("advisory_only") is True
                and response.get("non_atomic") is True
                and response.get("recheck_required") is True,
                "Preflight falsely grants admission",
            )
            process = response.get("process") or {}
            require(
                type(process.get("pid")) is int
                and process["pid"] > 0
                and process.get("lifecycle_scope") == "serving_process_only"
                and process.get("other_worker_idleness") == "not_established",
                "Preflight process scope unsupported",
            )
            require(
                response.get("assessment_scope")
                == "saved_cache_resource_and_coordination_admission_only",
                "Preflight scope changed",
            )
            cache = response.get("cache") or {}
            require(
                cache.get("size_bytes") == 23048708
                and cache.get("generation_pinned") is True
                and cache.get("path_matches_pinned_generation_at_end") is True
                and cache.get("payload_readability") == "not_checked"
                and cache.get("content_compatibility") == "not_evaluated",
                "Preflight cache or compatibility claim unsupported",
            )
            life = response.get("lifecycle") or {}
            require(
                life.get("available") is True
                and life.get("cache_lease_conflict") is False,
                "Preflight is not a memory-only admission control",
            )
            reserved = name == "fois_reserve_protected"
            require(
                (life.get("heavy_work") or {}).get("fois_generation") is reserved,
                "Preflight FOIS reservation mismatch",
            )
            memory = response.get("memory") or {}
            require(
                memory.get("scope") == "shared_container"
                and memory.get("cgroup_limit_bytes") == 2147483648
                and type(memory.get("cgroup_current_bytes")) is int
                and 0 <= memory["cgroup_current_bytes"] <= 2147483648,
                "Preflight container scope unsupported",
            )
            events = memory.get("memory_events") or {}
            require(
                not events.get("oom") and not events.get("oom_kill"),
                "Preflight case OOM",
            )
            capacity = response.get("capacity") or {}
            working = 16 * 23048708
            safety, fois = (
                (256 * 1024**2, 512 * 1024**2) if reserved else (128 * 1024**2, 0)
            )
            require(
                capacity.get("telemetry_valid") is True
                and capacity.get("working_bytes") == working
                and capacity.get("safety_bytes") == safety
                and capacity.get("fois_working_bytes") == fois
                and capacity.get("required_bytes") == working + safety + fois
                and capacity.get("effective_limit_bytes") == 2147483648
                and capacity.get("headroom_bytes")
                == 2147483648 - memory["cgroup_current_bytes"],
                "Preflight changed the restoration reservation",
            )
            require(
                capacity.get("would_admit") is (expected[0] == "would_admit")
                and capacity["would_admit"]
                is (capacity["headroom_bytes"] >= capacity["required_bytes"]),
                "Preflight headroom verdict mismatch",
            )
        before = by_name["fois_reserve_protected"]["harness_padding_bytes"]
        require(
            type(before) is int
            and before > 0
            and before
            == by_name["fois_released_same_pressure"]["harness_padding_bytes"],
            "Preflight FOIS recovery changed the harness pressure",
        )
        liveness = result.get("liveness") or []
        require(
            len(liveness) == 5
            and Counter(x.get("case") for x in liveness)
            == Counter(expected_cases.keys())
            and all(
                type(x.get("server_ms")) in (int, float)
                and 0 <= x["server_ms"] < 500
                and type(x.get("client_ms")) in (int, float)
                and x["client_ms"] >= 0
                for x in liveness
            ),
            "Preflight server liveness failed",
        )
        sums = [
            line.split("  ", 1)
            for line in archive.read("SHA256SUMS").decode().splitlines()
        ]
        require(
            len(sums) == 2 and {x[1] for x in sums} == {"result.json", "raw.log"},
            "Preflight checksum population mismatch",
        )
        for expected, name in sums:
            require(
                hashlib.sha256(archive.read(name)).hexdigest() == expected,
                "Preflight payload checksum mismatch",
            )
        return result


def verify_league_entry(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read("result.json"))
        require(
            result["head"] == plan["candidate"] and result["tree"] == plan["tree"],
            "League entry source mismatch",
        )
        require(
            result.get("passed") is True
            and result.get("complete") is True
            and result.get("working_tree_clean") is True,
            "League entry incomplete or dirty",
        )
        require(
            result.get("warm_cold_saved_http") == "passed"
            and result.get("one_qb_k_def_http_evaluation") == "passed",
            "League entry HTTP controls missing",
        )
        require(
            result.get("pressure_deferred") is True
            and result.get("recovery_completed") is True
            and result.get("worker_reaped") is True,
            "League entry deferral/recovery/cleanup missing",
        )
        require(
            result.get("active_fois_commitment_deferred") is True
            and result.get("after_fois_release_same_pressure_completed") is True,
            "Outstanding FOIS reserve or same-pressure recovery not established",
        )
        require(
            result["cgroup_lifetime_peak"] <= 2147483648,
            "League entry exceeded enforced memory",
        )
        samples = result["samples"]
        require(
            samples
            and all(
                x["cgroup_limit_bytes"] == 2147483648
                and not x["cgroup_memory_events"].get("oom")
                and not x["cgroup_memory_events"].get("oom_kill")
                and x["cgroup_current_bytes"] <= 2147483648
                for x in samples
            ),
            "League entry memory evidence failed",
        )
        labels = {x["label"] for x in samples}
        require(
            {
                "active_fois_worker",
                "before_large_restore_with_fois",
                "after_large_restore_with_fois",
                "unsafe_pressure",
                "active_fois_outstanding_reserve",
                "same_pressure_after_fois_release",
                "pressure_relieved",
                "recovered_restore",
                "cleanup",
            }
            <= labels,
            "League entry lifecycle evidence incomplete",
        )
        require(
            result["liveness"]
            and len(result["liveness"]) == 5
            and all(
                type(x.get("server_ms")) in (int, float)
                and 0 <= x["server_ms"] < 500
                and type(x.get("client_ms")) in (int, float)
                and x["client_ms"] >= 0
                for x in result["liveness"]
            ),
            "League entry server liveness failed",
        )
        checks = [
            line.split("  ", 1)
            for line in archive.read("SHA256SUMS").decode().splitlines()
        ]
        require(
            {x[1] for x in checks} == {"result.json", "raw.log", "preparation.log"}
            and len(checks) == 3,
            "League entry attachment manifest incomplete",
        )
        for expected, name in checks:
            require(
                hashlib.sha256(archive.read(name)).hexdigest() == expected,
                "League entry checksum mismatch",
            )
        return result


def prior_attempt_record(repo, reference):
    """Keep a failed historical attempt distinct from a later successful rerun."""
    require(
        isinstance(reference, dict) and set(reference) == {"id", "attempt"},
        "Invalid prior attempt reference",
    )
    run_id, attempt = reference["id"], reference["attempt"]
    require(
        type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0,
        "Invalid prior attempt identity",
    )
    run = api(repo + "/actions/runs/" + str(run_id) + "/attempts/" + str(attempt))
    require(
        run["id"] == run_id and run["run_attempt"] == attempt,
        "Prior attempt API identity mismatch",
    )
    return {
        key: run[key]
        for key in (
            "id",
            "name",
            "head_sha",
            "status",
            "conclusion",
            "html_url",
            "run_attempt",
        )
    }


def verify_handoff(data, plan):
    require(
        len(data) <= 128 * 1024 and not TOKEN.search(data), "Unsafe handoff attachment"
    )
    require(
        plan["candidate"].encode() in data and plan["tree"].encode() in data,
        "Handoff describes another source",
    )
    return data


def verify_context(plan, operation):
    require(
        os.environ.get("GITHUB_ACTIONS") == "true", "Publisher requires GitHub Actions"
    )
    require(
        os.environ.get("GITHUB_REPOSITORY") == plan["repository"], "Wrong repository"
    )
    require(
        os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch",
        "Only explicit dispatch is authorized",
    )
    require(
        os.environ.get("GITHUB_ACTOR") == plan["actor"], "Unapproved dispatch actor"
    )
    require(
        os.environ.get("GITHUB_REF") == plan["publisher_ref"],
        "Unapproved publisher ref",
    )
    sha = os.environ["GITHUB_SHA"]
    require(command("git", "rev-parse", "HEAD") == sha, "Publisher checkout mismatch")
    repo = "repos/" + plan["repository"]
    ref = api(
        repo + "/git/ref/heads/" + plan["publisher_ref"].removeprefix("refs/heads/")
    )
    require(ref["object"]["sha"] == sha, "Publisher ref advanced")
    changed = set(
        command("git", "diff", "--name-only", plan["baseline"], sha).splitlines()
    )
    require(changed <= ALLOWED_PATHS, "Publisher contains application changes")
    run = api(repo + "/actions/runs/" + os.environ["GITHUB_RUN_ID"])
    require(
        run["head_sha"] == sha
        and run["event"] == "workflow_dispatch"
        and run["path"] == ".github/workflows/canonical-release-recovery.yml",
        "Untrusted publisher run",
    )
    pr = api(repo + "/pulls/" + str(plan["pr"]))
    require(
        pr["base"]["ref"] == "main"
        and pr["base"]["repo"]["full_name"] == plan["repository"],
        "Wrong PR base",
    )
    require(
        pr["head"]["repo"]["full_name"] == plan["repository"]
        and pr["head"]["sha"] == plan["candidate"]
        and pr["head"]["ref"] == plan["source_branch"],
        "Candidate PR changed",
    )
    main = api(repo + "/git/ref/heads/main")["object"]["sha"]
    if operation == "publish":
        require(
            pr["merged"] and pr["merged_at"] and pr["merge_commit_sha"] == main,
            "Publication requires the approved PR merged at current main",
        )
    else:
        require(
            not pr["merged"] and pr["state"] == "open" and main == plan["baseline"],
            "Preparation requires unchanged baseline and open candidate",
        )
    subprocess.run(
        ["git", "fetch", "origin", "refs/pull/" + str(plan["pr"]) + "/head", "main"],
        check=True,
    )
    require(
        command("git", "rev-parse", plan["candidate"] + "^{tree}") == plan["tree"],
        "Candidate tree mismatch",
    )
    if operation == "publish":
        require(
            command("git", "rev-parse", main + "^{tree}") == plan["tree"],
            "Merged application differs from validated source",
        )
    source = ast.parse(command("git", "show", plan["candidate"] + ":app_metadata.py"))
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in source.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"VERSION", "BUILD_NUMBER"}
    }
    require(
        constants == {"VERSION": plan["version"], "BUILD_NUMBER": plan["build"]},
        "Version/build mismatch",
    )
    previous = api(repo + "/releases/tags/" + plan["prior_immutable_tag"])
    require(
        previous["immutable"] is True and previous["draft"] is False,
        "Established immutable policy not verified",
    )
    return pr, main


def verify_runs(plan):
    repo = "repos/" + plan["repository"]
    checks = api(
        repo
        + "/commits/"
        + plan["candidate"]
        + "/check-runs?filter=latest&per_page=100"
    )["check_runs"]
    for name in [n for run in plan["runs"] for n in run["jobs"]]:
        matching = [x for x in checks if x["name"] == name]
        require(
            matching
            and all(
                x["head_sha"] == plan["candidate"]
                and x["status"] == "completed"
                and x["conclusion"] == "success"
                and x["app"]["slug"] == "github-actions"
                for x in matching
            ),
            "Latest required check not successful: " + name,
        )
    records = []
    product_job = None
    for expected in plan["runs"]:
        run = api(repo + "/actions/runs/" + str(expected["id"]))
        require(
            run["head_sha"] == plan["candidate"]
            and run["head_repository"]["full_name"] == plan["repository"],
            "Validation run source mismatch",
        )
        require(
            run["event"] == "pull_request"
            and run["path"] == expected["path"]
            and run["name"] == expected["name"],
            "Wrong validation workflow",
        )
        require(
            run["status"] == "completed" and run["conclusion"] == "success",
            "Validation workflow not successful",
        )
        jobs = api(
            repo + "/actions/runs/" + str(expected["id"]) + "/jobs?per_page=100"
        )["jobs"]
        for name in expected["jobs"]:
            found = [x for x in jobs if x["name"] == name]
            require(
                len(found) == 1
                and found[0]["status"] == "completed"
                and found[0]["conclusion"] == "success",
                "Required job not successful: " + name,
            )
            records.append(
                {
                    "id": found[0]["id"],
                    "name": name,
                    "run": expected["id"],
                    "conclusion": "success",
                }
            )
            if name == "product-browser":
                product_job = found[0]["id"]
    require(len(records) == 13 and product_job, "Required gate population mismatch")
    return records, product_job


def make_zip(path, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    verify_zip(path)


def verify_market_roster(path, plan, prefix="browser/market-needs/"):
    """Read exact-source real route/browser artifacts, never owner live claims."""
    verify_zip(path)
    expected = {
        (shape, width, height)
        for shape in ("oneqb-kdef", "superflex")
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900))
    }

    def record(archive, name):
        row = json.loads(archive.read(prefix + name + ".json"))
        require(
            row.get("commit") == plan["candidate"] and row.get("tree") == plan["tree"],
            "Market handoff source mismatch",
        )
        require(
            "not owner live" in row.get("scope", ""), "Market fixture scope missing"
        )
        return row["observations"]

    with zipfile.ZipFile(path) as archive:
        rows = record(archive, "roundtrip")
        require(
            len(rows) == 8 and {(r["shape"], *r["viewport"]) for r in rows} == expected,
            "Market round-trip coverage incomplete",
        )
        for row in rows:
            require(
                all(
                    row.get(k) is True
                    for k in (
                        "roundtrip",
                        "exact_asset",
                        "draft_preserved",
                        "protections_preserved",
                        "comparison_preserved",
                        "retained_result",
                        "no_extra_posts",
                        "no_solver_on_navigation",
                    )
                )
                and row.get("errors") == [],
                "Market state or no-work control failed",
            )
            shape, width, height = row["shape"], *row["viewport"]
            captured = record(archive, shape + "-" + str(width))
            require(
                len(captured) == 1
                and captured[0].get("viewport") == [width, height]
                and captured[0].get("exact_target") == "player:2-RB-0"
                and captured[0].get("neutral_movement") == 150
                and captured[0].get("keyboard_disclosure") is True
                and captured[0].get("touch_emulation") is (width < 1000)
                and captured[0].get("overflow") is False,
                "Market target or accessibility proof missing",
            )
            market = record(archive, "market-" + shape + "-" + str(width))
            require(
                len(market) == 1 and market[0].get("no_search") is True,
                "Market disclosure proof missing",
            )
            for stem in (
                shape + "-" + str(width),
                "market-" + shape + "-" + str(width),
            ):
                image = archive.read(prefix + stem + ".png")
                require(
                    image.startswith(b"\x89PNG\r\n\x1a\n")
                    and len(image) >= 24
                    and int.from_bytes(image[16:20], "big") == width,
                    "Market phone capture missing or wrong width",
                )
        stale = record(archive, "stale-and-league")
        require(
            len(stale) == 1
            and all(
                stale[0].get(k) is True
                for k in (
                    "stale_link_withheld",
                    "new_target_not_applied",
                    "existing_draft_preserved",
                    "league_switch_cleared_scope",
                    "no_posts",
                )
            )
            and stale[0].get("errors") == [],
            "Stale Market handoff protection missing",
        )
    return {
        "candidate": plan["candidate"],
        "tree": plan["tree"],
        "cases": 8,
        "scope": "Disposable authenticated prepared evidence and Chromium phone/touch emulation; owner live and physical Safari unverified",
    }


def verify_market_roster_tests(path, plan):
    with zipfile.ZipFile(path) as archive:
        rows = [json.loads(line) for line in archive.read("tests.jsonl").splitlines()]
    starts = [
        r["test"]
        for r in rows
        if r.get("event") == "start"
        and "test_market_roster_relevance" in r.get("test", "")
    ]
    stops = [
        r["test"]
        for r in rows
        if r.get("event") == "stop"
        and "test_market_roster_relevance" in r.get("test", "")
    ]
    require(
        len(starts) == len(set(starts)) == plan["market_roster_tests"] == 21
        and Counter(starts) == Counter(stops),
        "Market roster regression population incomplete",
    )
    return starts


def verify_roster_source_scope_tests(path, plan):
    with zipfile.ZipFile(path) as archive:
        rows = [json.loads(line) for line in archive.read("tests.jsonl").splitlines()]

    def selected(row):
        return "test_roster_source_scope." in row.get(
            "test", ""
        ) or "test_roster_source_scope_browser." in row.get("test", "")

    starts = [r["test"] for r in rows if r.get("event") == "start" and selected(r)]
    stops = [r["test"] for r in rows if r.get("event") == "stop" and selected(r)]
    require(
        len(starts) == len(set(starts)) == plan["roster_source_scope_tests"] == 20
        and Counter(starts) == Counter(stops),
        "Roster source-scope regression population incomplete",
    )
    return starts


def verify_roster_source_scope(path, plan, prefix="browser/roster-source-scope/"):
    """Source-bound prepared-source/browser proof, never owner live acceptance."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        for shape in ("oneqb-kdef", "sf"):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                stem = prefix + shape + "-" + str(width)
                row = json.loads(archive.read(stem + ".json"))
                require(
                    row.get("commit") == plan["candidate"]
                    and row.get("tree") == plan["tree"]
                    and row.get("working_tree_clean") is True,
                    "Roster source-scope capture source mismatch",
                )
                require(
                    row.get("viewport") == [width, height]
                    and row.get("exact_target") == "player:2-RB-0"
                    and all(
                        row.get(key) is True
                        for key in (
                            "unrostered_missing_projection",
                            "my_team_supported",
                            "explicit_generate_required",
                            "keyboard",
                            "no_navigation_solver",
                        )
                    )
                    and row.get("touch_emulation") is (width < 1000),
                    "Roster source-scope supported journey incomplete",
                )
                require(
                    "not owner live" in row.get("scope", ""),
                    "Roster fixture/live distinction missing",
                )
                require(
                    archive.read(stem + ".png").startswith(b"\x89PNG\r\n\x1a\n"),
                    "Roster journey image missing",
                )
        for reason in (
            "unknown-k",
            "unknown-def",
            "eligible-missing",
            "aging",
            "failed-refresh",
        ):
            stem = prefix + reason
            row = json.loads(archive.read(stem + ".json"))
            require(
                row.get("commit") == plan["candidate"]
                and row.get("tree") == plan["tree"]
                and row.get("working_tree_clean") is True,
                "Roster withholding capture source mismatch",
            )
            require(
                row.get("reason") == reason
                and all(
                    row.get(key) is True
                    for key in (
                        "neutral_preserved",
                        "personalized_action_withheld",
                        "no_posts",
                    )
                ),
                "Genuine roster limitations were not preserved",
            )
            require(
                archive.read(stem + ".png").startswith(b"\x89PNG\r\n\x1a\n"),
                "Roster withholding image missing",
            )
    return {
        "candidate": plan["candidate"],
        "tree": plan["tree"],
        "passed": True,
        "supported_roundtrips": 8,
        "withheld_cases": 5,
        "scope": "Native disposable source/route/browser controls; owner live and physical Safari unverified",
    }


def verify_draft_capital(path, plan, prefix="browser/offer-comparison/"):
    """Pinned real evaluator/browser captures; never owner live acceptance."""
    verify_zip(path)
    rows = []
    with zipfile.ZipFile(path) as archive:
        for superflex in ("False", "True"):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                stem = prefix + "draft-capital-" + superflex + "-" + str(width)
                record = json.loads(archive.read(stem + ".json"))
                require(
                    record.get("commit") == plan["candidate"]
                    and record.get("tree") == plan["tree"]
                    and record.get("working_tree_clean") is True,
                    "Draft-capital source mismatch",
                )
                require(
                    record.get("physical_safari_tested") is False,
                    "Draft-capital fixture scope missing",
                )
                observed = record.get("observations", {})
                require(
                    observed.get("complete_recorded_inventories") == 3
                    and observed.get("four_viewports") is True
                    and observed.get("no_comparison_http") is True
                    and observed.get("exact_originals") == [1, 3],
                    "Draft-capital comparison or exact identity control failed",
                )
                captures = observed.get("capital_records", [])
                require(
                    len(captures) == 2, "Both draft-capital alternatives are required"
                )
                baselines = []
                for index, envelope in enumerate(captures):
                    parts = envelope.get("parts", [])
                    require(
                        isinstance(parts, list)
                        and 0 < len(parts) <= 8
                        and all(isinstance(x, str) and len(x) <= 1400 for x in parts),
                        "Invalid bounded capital record",
                    )
                    text = "".join(parts)
                    require(
                        len(text) == envelope.get("characters") and len(text) <= 10000,
                        "Truncated capital record",
                    )
                    row = json.loads(text)
                    require(
                        row.get("schema") == 1
                        and row.get("league") == "league-1"
                        and row.get("roster") == 1
                        and row.get("complete") is True
                        and row.get("rounds") == 4
                        and row.get("seasons") == [2028],
                        "Capital ownership scope or completeness missing",
                    )
                    before = row.get("before", [])
                    require(
                        [2028, 1, 1] in before
                        and [2028, 1, 3] in before
                        and len({tuple(x) for x in before}) == len(before),
                        "Own/acquired firsts not distinct",
                    )
                    require(
                        row.get("sent") == ([[2028, 1, 3]] if index == 0 else [])
                        and row.get("received") == [],
                        "Recorded exchange movement changed",
                    )
                    require(
                        re.fullmatch("[0-9a-f]{64}", row.get("generation", ""))
                        is not None,
                        "Capital ownership generation missing",
                    )
                    baselines.append((row["generation"], before))
                require(
                    baselines[0] == baselines[1], "Keep-roster capital baseline differs"
                )
                image = archive.read(stem + ".png")
                require(
                    image.startswith(b"\x89PNG\r\n\x1a\n")
                    and len(image) >= 24
                    and int.from_bytes(image[16:20], "big") == width,
                    "Capital phone capture missing or wrong width",
                )
                rows.append(
                    {
                        "superflex": superflex == "True",
                        "width": width,
                        "height": height,
                        "recorded_alternatives": 2,
                    }
                )
    return {
        "candidate": plan["candidate"],
        "tree": plan["tree"],
        "cases": rows,
        "scope": "Disposable authenticated evaluations; not owner live acceptance",
    }


def verify_capital_test_execution(path, plan):
    with zipfile.ZipFile(path) as archive:
        rows = [json.loads(line) for line in archive.read("tests.jsonl").splitlines()]
    starts = [
        r["test"]
        for r in rows
        if r.get("event") == "start" and "test_trade_capital_" in r.get("test", "")
    ]
    stops = [
        r["test"]
        for r in rows
        if r.get("event") == "stop" and "test_trade_capital_" in r.get("test", "")
    ]
    require(
        len(starts) == len(set(starts)) == plan["capital_tests"] == 14
        and Counter(starts) == Counter(stops),
        "Draft-capital regression population incomplete",
    )
    require(
        any(
            x.endswith(
                "test_bounded_record_keeps_supported_exchange_when_inventory_is_too_large"
            )
            for x in starts
        ),
        "Bounded capital movement preservation test missing",
    )
    return starts


def validate_recovery_parts(plan, family="recovery"):
    require(family in ("recovery", "prior"), "Unknown bounded evidence family")
    file_key = "recovery_file" if family == "recovery" else "prior_evidence_file"
    parts_key = "recovery_parts" if family == "recovery" else "prior_evidence_parts"
    require(
        plan.get(file_key) == ".github/release-plans/2251-" + family + ".zip",
        "Unexpected recovery archive identity",
    )
    parts = plan.get(parts_key)
    require(
        isinstance(parts, list) and 1 <= len(parts) <= 4,
        "Missing bounded recovery parts",
    )
    total = 0
    for index, item in enumerate(parts, 1):
        require(
            isinstance(item, dict) and set(item) == {"path", "bytes", "sha256"},
            "Invalid recovery part metadata",
        )
        require(
            item["path"]
            == ".github/release-plans/2251-"
            + family
            + "-"
            + str(index).zfill(3)
            + ".part",
            "Unexpected or unordered recovery part",
        )
        require(
            type(item["bytes"]) is int and 0 < item["bytes"] <= 64 * 1024**2,
            "Recovery part size outside bound",
        )
        require(
            isinstance(item["sha256"], str)
            and re.fullmatch("[0-9a-f]{64}", item["sha256"]),
            "Invalid recovery part checksum",
        )
        total += item["bytes"]
    require(total <= 256 * 1024**2, "Recovery transport exceeds bound")
    return parts


def materialize_recovery(plan, root, repository=None, family="recovery"):
    """No missing bytes are replaced: verify every part, then the full archive."""
    parts = validate_recovery_parts(plan, family)
    checksum_key = (
        "recovery_sha256" if family == "recovery" else "prior_evidence_sha256"
    )
    repository = Path.cwd() if repository is None else Path(repository)
    for relative in (".github", ".github/release-plans"):
        require(not (repository / relative).is_symlink(), "Recovery parent symlink")
    root.mkdir(parents=True, exist_ok=True)
    target = root / (family + "-assembled.zip")
    require(not target.exists(), "Recovery output already exists; preserve and inspect")
    temporary = root / (family + "-assembled.partial")
    with temporary.open("xb") as stream:
        for item in parts:
            path = repository / item["path"]
            require(
                path.is_file() and not path.is_symlink(),
                "Missing or nonregular recovery part",
            )
            require(
                path.stat().st_size == item["bytes"] and digest(path) == item["sha256"],
                "Recovery part checksum mismatch",
            )
            with path.open("rb") as source:
                shutil.copyfileobj(source, stream, 1024 * 1024)
    require(
        temporary.stat().st_size == sum(x["bytes"] for x in parts)
        and digest(temporary) == plan[checksum_key],
        "Assembled recovery checksum mismatch",
    )
    verify_zip(temporary)
    temporary.rename(target)
    return target


def materialize_prior_evidence(plan, root, repository=None):
    require(
        plan.get("prior_evidence_file") == ".github/release-plans/2251-prior.zip",
        "Unexpected prior archive identity",
    )
    if "prior_evidence_parts" in plan:
        return materialize_recovery(plan, root, repository, family="prior")
    repository = Path.cwd() if repository is None else Path(repository)
    return repository / plan["prior_evidence_file"]


def collect(plan, root):
    repo = "repos/" + plan["repository"]
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    records, product_job = verify_runs(plan)
    canonical = None
    offer_comparison = None
    draft_capital = None
    market_roster = None
    roster_source_scope = None
    for expected in plan["artifacts"]:
        metadata = api(repo + "/actions/artifacts/" + str(expected["id"]))
        require(
            not metadata["expired"] and metadata["name"] == expected["name"],
            "Artifact unavailable or renamed",
        )
        require(
            metadata["workflow_run"]["id"] == expected["run"]
            and metadata["workflow_run"]["head_sha"] == plan["candidate"],
            "Artifact run mismatch",
        )
        require(
            metadata["digest"] == "sha256:" + expected["sha256"],
            "Artifact API digest mismatch",
        )
        path = assets / expected["file"]
        download(repo + "/actions/artifacts/" + str(expected["id"]) + "/zip", path)
        require(
            digest(path) == expected["sha256"]
            and path.stat().st_size == metadata["size_in_bytes"],
            "Original artifact checksum mismatch",
        )
        verify_zip(path)
        if expected["file"] == "canonical-original.zip":
            canonical = verify_canonical(path, plan)
            verify_capital_test_execution(path, plan)
            verify_market_roster_tests(path, plan)
            verify_roster_source_scope_tests(path, plan)
            acquisition_test_ids = verify_acquisition_tests(path, plan)
            normal_execution_test_ids = verify_normal_execution_tests(path, plan)
            franchise_progress_test_ids = verify_franchise_progress_tests(path, plan)
        if expected["file"] == "actuals-restoration-original.zip":
            verify_actuals_restoration(path, plan)
        if expected["file"] == "restoration-unused-original.zip":
            verify_restoration_unused(path, plan)
        if expected["file"] == "resident-refresh-original.zip":
            verify_resident_refresh(path, plan)
        if expected["file"] == "trade-resource-original.zip":
            verify_trade_resource(path, plan)
            verify_team_need_handoff(path, plan)
            offer_comparison = verify_offer_comparison(path, plan)
            verify_recommended_protections(path, plan)
            verify_activation_deferral(path, plan)
            verify_front_office_workflow(path, plan)
            draft_capital = verify_draft_capital(path, plan)
            market_roster = verify_market_roster(path, plan)
            roster_source_scope = verify_roster_source_scope(path, plan)
        if expected["file"] == "league-entry-original.zip":
            verify_league_entry(path, plan)
        if expected["file"] == "preflight-original.zip":
            verify_preflight(path, plan)
        if expected["file"] == "current-history-original.zip":
            verify_current_history(path, plan)
        if expected["file"] == "current-production-coverage-original.zip":
            verify_current_production(path, plan)
        if expected["file"] == "market-history-coverage-original.zip":
            verify_market_history(path, plan)
        if expected["file"] == "history-followthrough-original.zip":
            verify_history_followthrough(path, plan)
            verify_completed_trade_browser(path, plan)
            verify_franchise_progress_browser(path, plan)
        if expected["file"] == "public-welcome-security.zip":
            verify_partner_history_links(path, plan)
        if expected["file"].startswith("lifecycle-"):
            with zipfile.ZipFile(path) as archive:
                result = json.loads(archive.read("summary.json"))
            require(
                result["passed"] is True
                and result["completed"] is True
                and result["exit_code"] == 0
                and result["memory_max"] == 2147483648,
                "Lifecycle acceptance missing",
            )
    require(canonical is not None, "Canonical artifact absent")
    require(offer_comparison is not None, "Hosted offer comparison proof absent")
    require(draft_capital is not None, "Hosted draft-capital proof absent")
    require(market_roster is not None, "Hosted Market roster proof absent")
    require(roster_source_scope is not None, "Hosted roster source-scope proof absent")
    recovery = materialize_recovery(plan, root)
    require(digest(recovery) == plan["recovery_sha256"], "Recovery evidence changed")
    local_canonical = verify_local_recovery(recovery, plan)
    local_acquisition_tests = verify_acquisition_tests(
        recovery, plan, prefix="local-canonical/"
    )
    acquisition = verify_acquisition_recovery(recovery, plan)
    local_normal_execution_tests = verify_normal_execution_tests(
        recovery, plan, prefix="local-canonical/"
    )
    local_progress_tests = verify_franchise_progress_tests(
        recovery, plan, prefix="local-canonical/"
    )
    local_progress_browser = verify_franchise_progress_browser(
        recovery, plan, prefix="feature/"
    )
    franchise_progress_cases = verify_franchise_progress_cases(recovery, plan)
    local_draft_capital = verify_draft_capital(
        recovery, plan, prefix="local-capital-capture/"
    )
    local_draft_capital["evidence_origin"] = (
        "Supplemental two-method local browser capture on the final source under enforced 2 GiB; "
        "the original full canonical manifest is unchanged."
    )
    local_market_roster = verify_market_roster(
        recovery, plan, prefix="local-canonical/market-needs/"
    )
    local_roster_source_scope = verify_roster_source_scope(
        recovery, plan, prefix="local-canonical/roster-source-scope/"
    )
    partner_history_links = verify_partner_history_links(
        recovery, plan, prefix="partner-history/"
    )
    team_need_handoff = verify_team_need_handoff(recovery, plan, prefix="team-need/")
    recommended_protections = verify_recommended_protections(
        recovery, plan, prefix="protections/"
    )
    activation_deferral = verify_activation_deferral(
        recovery, plan, prefix="local-canonical/activation/"
    )
    front_office_workflow = verify_front_office_workflow(
        recovery, plan, prefix="local-canonical/front-office-workflow/"
    )
    completed_trade_observations = verify_completed_trade_browser(
        recovery, plan, prefix="feature/"
    )
    completed_trade_observations["matched_cases"] = verify_completed_trade_cases(
        recovery, plan
    )
    with zipfile.ZipFile(recovery) as archive:
        local_preflight = root / "local-preflight.zip"
        make_zip(
            local_preflight,
            {
                name: archive.read("local-preflight/" + name)
                for name in ("result.json", "raw.log", "SHA256SUMS")
            },
        )
        (assets / "SCOUT_HANDOFF.md").write_bytes(
            verify_handoff(archive.read("SCOUT_HANDOFF.md"), plan)
        )
        local_unused = root / "local-restoration-unused.zip"
        make_zip(
            local_unused,
            {
                name: archive.read("local-restoration-unused/" + name)
                for name in (
                    "evidence/result.json",
                    "raw.log",
                    "prior-study.zip",
                    "SHA256SUMS",
                )
            },
        )
    local_preflight_result = verify_preflight(local_preflight, plan)
    local_unused_result = verify_actuals_restoration(local_unused, plan)
    with zipfile.ZipFile(recovery) as archive:
        local_resident = root / "local-resident-refresh.zip"
        make_zip(
            local_resident,
            {
                name: archive.read("local-resident-refresh/" + name)
                for name in ("evidence/result.json", "raw.log", "SHA256SUMS")
            },
        )
    local_resident_result = verify_resident_refresh(local_resident, plan)
    require(
        any(x["file"] == "preflight-original.zip" for x in plan["artifacts"]),
        "Hosted preflight proof absent",
    )
    require(
        any(x["file"] == "trade-resource-original.zip" for x in plan["artifacts"])
        and any(x["file"] == "league-entry-original.zip" for x in plan["artifacts"]),
        "Existing hosted Trade or league-entry acceptance absent",
    )
    require(
        any(x["file"] == "actuals-restoration-original.zip" for x in plan["artifacts"]),
        "Native restoration acceptance absent",
    )
    require(
        any(x["file"] == "restoration-unused-original.zip" for x in plan["artifacts"]),
        "Hosted restoration recovery proof absent",
    )
    require(
        any(x["file"] == "resident-refresh-original.zip" for x in plan["artifacts"]),
        "Hosted resident ownership proof absent",
    )
    shutil.copyfile(recovery, assets / "Trade-For-Cost-Fit.zip")
    prior_evidence = materialize_prior_evidence(plan, root)
    require(
        plan["prior_evidence_file"] == ".github/release-plans/2251-prior.zip",
        "Unexpected prior archive path",
    )
    verify_prior_evidence(prior_evidence, plan)
    shutil.copyfile(prior_evidence, assets / "Prior-attempts.zip")
    logs = {}
    for job in [product_job, *plan["prior_jobs"]]:
        path = root / (str(job) + ".log")
        download(repo + "/actions/jobs/" + str(job) + "/logs", path)
        data = path.read_bytes()
        require(not TOKEN.search(data), "Credential-shaped material in job log")
        logs[str(job) + ".log"] = data
    counts = [
        int(n)
        for n in re.findall(rb"Ran (\d+) tests? in", logs[str(product_job) + ".log"])
    ]
    require(
        sum(counts) == plan["product_tests"]
        and b"FAILED (" not in logs[str(product_job) + ".log"],
        "Product test evidence mismatch",
    )
    make_zip(assets / "product-and-prior-job-logs.zip", logs)
    prior = []
    for run_id in plan["prior_runs"]:
        run = api(repo + "/actions/runs/" + str(run_id))
        prior.append(
            {
                key: run[key]
                for key in (
                    "id",
                    "name",
                    "head_sha",
                    "status",
                    "conclusion",
                    "html_url",
                )
            }
        )
    prior.extend(
        prior_attempt_record(repo, reference)
        for reference in plan.get("prior_attempts", [])
    )
    write_json(assets / "prior-attempts.json", prior)
    write_json(
        assets / "VALIDATION.json",
        {
            "candidate": plan["candidate"],
            "tree": plan["tree"],
            "version": plan["version"],
            "build": plan["build"],
            "canonical": canonical,
            "local_canonical": local_canonical,
            "acquisition": dict(
                **acquisition,
                canonical_test_ids=acquisition_test_ids,
                local_test_ids=local_acquisition_tests,
            ),
            "normal_execution_recovery": {
                "canonical_test_ids": normal_execution_test_ids,
                "local_test_ids": local_normal_execution_tests,
                "scope": "Ten real browser controls completed under unchanged admission; deferral is not successful execution.",
            },
            "market_roster": market_roster,
            "local_market_roster": local_market_roster,
            "roster_source_scope": roster_source_scope,
            "local_roster_source_scope": local_roster_source_scope,
            "franchise_progress": {
                "passed": True,
                "candidate": plan["candidate"],
                "tree": plan["tree"],
                "canonical_test_ids": franchise_progress_test_ids,
                "local_test_ids": local_progress_tests,
                "local_browser": local_progress_browser,
                "matched_cases": franchise_progress_cases,
            },
            "draft_capital": draft_capital,
            "local_draft_capital": local_draft_capital,
            "activation_deferral": activation_deferral,
            "front_office_workflow": front_office_workflow,
            "partner_history_links": partner_history_links,
            "team_need_handoff": team_need_handoff,
            "offer_comparison": offer_comparison,
            "recommended_protections": recommended_protections,
            "completed_trade_observations": completed_trade_observations,
            "local_preflight": local_preflight_result,
            "local_restoration_unused": local_unused_result,
            "local_resident_refresh": local_resident_result,
            "required_jobs": records,
            "product_test_executions": sum(counts),
            "original_artifacts": plan["artifacts"],
            "recovery_sha256": plan["recovery_sha256"],
            "prior_evidence_sha256": plan["prior_evidence_sha256"],
            "limitations": "Cost and fit roles summarize the existing bounded eligible assessments, not a global minimum, actual asking price or guaranteed manager acceptance. Gross outgoing Neutral Market cost is distinct from additional incoming assets and net exchange; packages with different extras are not equivalent purchases. FAIR / OPTIONAL remains optional and unsupported costs cannot win. Custom methods and revisions remain separate. Prepared selection controls, actual shared-evaluator fixture searches and retained source replay are distinct from live owner observations. Keyboard/touch Chromium emulation is not physical iPhone/Safari acceptance. No supported authenticated owner-browser or Render Shell capability is exposed in this session; public identity/auth-boundary smokes do not establish authenticated Trade acceptance. Earlier failed, cancelled and incomplete outcomes remain separate. All inherited history, projection/result provenance, exact-pick, Trade/FOIS, valuation, account and resource-admission safeguards remain intact.",
        },
    )
    files = [
        {"name": p.name, "bytes": p.stat().st_size, "sha256": digest(p)}
        for p in sorted(assets.iterdir())
        if p.is_file()
    ]
    require(
        sum(x["bytes"] for x in files) < 512 * 1024**2,
        "Unexpected attachment population size",
    )
    write_json(
        assets / "evidence-manifest.json",
        {"candidate": plan["candidate"], "tree": plan["tree"], "files": files},
    )
    files.append(
        {
            "name": "evidence-manifest.json",
            "bytes": (assets / "evidence-manifest.json").stat().st_size,
            "sha256": digest(assets / "evidence-manifest.json"),
        }
    )
    (assets / "SHA256SUMS").write_text(
        "".join(x["sha256"] + "  " + x["name"] + "\n" for x in files)
    )
    return assets


def expected_assets(assets):
    manifest = json.loads((assets / "evidence-manifest.json").read_text())
    for item in manifest["files"]:
        p = assets / item["name"]
        require(
            p.parent == assets
            and p.is_file()
            and not p.is_symlink()
            and p.stat().st_size == item["bytes"]
            and digest(p) == item["sha256"],
            "Attachment manifest mismatch",
        )
    expected = {x["name"] for x in manifest["files"]} | {
        "evidence-manifest.json",
        "SHA256SUMS",
    }
    require(
        {p.name for p in assets.iterdir()} == expected, "Unmanifested local attachment"
    )
    sums = "".join(
        digest(assets / name) + "  " + name + "\n"
        for name in sorted(expected - {"SHA256SUMS"})
    )
    # Manifest rows are name-sorted, with the manifest's own digest appended.
    listed = dict(
        line.split("  ", 1)[::-1]
        for line in (assets / "SHA256SUMS").read_text().splitlines()
    )
    require(
        listed == dict(line.split("  ", 1)[::-1] for line in sums.splitlines()),
        "Attachment checksum list mismatch",
    )
    return {p.name: (p.stat().st_size, digest(p)) for p in assets.iterdir()}


def verify_remote_assets(release, expected, complete):
    remote = {x["name"]: x for x in release["assets"]}
    require(
        len(remote) == len(release["assets"]) and set(remote) <= set(expected),
        "Unexpected/duplicate draft asset",
    )
    if complete:
        require(set(remote) == set(expected), "Missing release attachment")
    for name, item in remote.items():
        require(
            item["state"] == "uploaded"
            and item["size"] == expected[name][0]
            and item["digest"] == "sha256:" + expected[name][1],
            "Remote attachment mismatch: " + name,
        )
    return remote


def verify_remote_bytes(plan, root, expected):
    with tempfile.TemporaryDirectory(dir=root) as directory:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                "v" + plan["version"],
                "--repo",
                plan["repository"],
                "--dir",
                directory,
            ],
            check=True,
        )
        paths = {p.name: p for p in Path(directory).iterdir()}
        require(
            set(paths) == set(expected),
            "Release attachment readback population mismatch",
        )
        for name, (size, sha) in expected.items():
            require(
                paths[name].stat().st_size == size and digest(paths[name]) == sha,
                "Release attachment readback mismatch: " + name,
            )


def verify_preparation(plan, root, expected, run_id):
    require(run_id, "Publish requires an explicit successful preparation run")
    repo = "repos/" + plan["repository"]
    run = api(repo + "/actions/runs/" + str(run_id))
    require(
        run["head_sha"] == os.environ["GITHUB_SHA"]
        and run["event"] == "workflow_dispatch"
        and run["path"] == ".github/workflows/canonical-release-recovery.yml"
        and run["conclusion"] == "success"
        and run["status"] == "completed",
        "Preparation was not successful on this publisher source",
    )
    artifacts = api(repo + "/actions/runs/" + str(run_id) + "/artifacts?per_page=100")[
        "artifacts"
    ]
    found = [
        x
        for x in artifacts
        if x["name"] == "guarded-release-2251-prepare-" + str(run_id)
        and not x["expired"]
    ]
    require(len(found) == 1, "Preparation certificate missing")
    path = root / "preparation-certificate.zip"
    download(repo + "/actions/artifacts/" + str(found[0]["id"]) + "/zip", path)
    require(
        "sha256:" + digest(path) == found[0]["digest"],
        "Preparation certificate checksum mismatch",
    )
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        certificate = json.loads(archive.read("publication.json"))
    require(
        certificate["operation"] == "prepare"
        and certificate["publisher"] == os.environ["GITHUB_SHA"]
        and certificate["candidate"] == plan["candidate"]
        and certificate["tree"] == plan["tree"]
        and certificate["main"] == plan["baseline"]
        and certificate["release_id"] == plan["draft_id"]
        and certificate["draft"] is True,
        "Wrong preparation admission certificate",
    )
    actual = {x["name"]: (x["bytes"], x["sha256"]) for x in certificate["attachments"]}
    require(
        actual == expected, "Prepared evidence differs from current release evidence"
    )


def prepare_or_publish(plan, root, operation, prepared_run=None):
    pr, main = verify_context(plan, operation)
    assets = collect(plan, root)
    expected = expected_assets(assets)
    repo = "repos/" + plan["repository"]
    release_path = repo + "/releases/" + str(plan["draft_id"])
    release = api(release_path)
    require(release["tag_name"] == "v" + plan["version"], "Wrong existing release tag")
    require(
        release["target_commitish"] in {plan["candidate"], main},
        "Wrong existing release target",
    )
    existing = verify_remote_assets(release, expected, complete=operation == "publish")
    if operation == "audit":
        require(
            release["draft"] and not release["immutable"],
            "Audit requires existing draft",
        )
    elif operation == "prepare":
        require(
            release["draft"] and not release["immutable"],
            "Preparation requires existing draft",
        )
        for name in sorted(set(expected) - set(existing)):
            # The Actions GITHUB_TOKEN is used by the standard GitHub CLI only.
            subprocess.run(
                [
                    "gh",
                    "release",
                    "upload",
                    "v" + plan["version"],
                    str(assets / name),
                    "--repo",
                    plan["repository"],
                ],
                check=True,
            )
        release = api(release_path)
        verify_remote_assets(release, expected, complete=True)
        verify_remote_bytes(plan, root, expected)
    elif operation == "publish":
        verify_preparation(plan, root, expected, prepared_run)
        # Recheck main/PR after downloads, before touching any tag/release metadata.
        _, latest = verify_context(plan, operation)
        require(
            latest == main and pr["merge_commit_sha"] == main,
            "Main moved during publication",
        )
        if release["draft"]:
            notes = command(
                "git", "show", plan["candidate"] + ":RELEASE_NOTES.md"
            ).split("\n# ", 1)[0]
            notes += (
                "\n\nReleased merge: "
                + main
                + "\nValidated source: "
                + plan["candidate"]
                + "\nSource tree: "
                + plan["tree"]
                + "\nAll 13 required hosted jobs and all ten canonical gates passed; "
                + str(plan["canonical_tests"])
                + " canonical tests and "
                + str(plan["product_tests"])
                + " Product tests. Prior failures and resource qualifications remain in attached evidence.\n"
            )
            api(
                release_path,
                {
                    "tag_name": "v" + plan["version"],
                    "target_commitish": main,
                    "name": "DTOS v"
                    + plan["version"]
                    + " / build "
                    + str(plan["build"]),
                    "body": notes,
                },
            )
            release = api(release_path)
            require(
                release["draft"] and release["target_commitish"] == main,
                "Draft target was not updated to approved merge",
            )
        tag_ref_path = repo + "/git/ref/tags/v" + plan["version"]
        lookup = subprocess.run(
            ["gh", "api", tag_ref_path], capture_output=True, text=True, check=False
        )
        if lookup.returncode:
            require(
                "HTTP 404" in lookup.stderr, "Tag lookup failed; not confirmed absent"
            )
            require(
                release["draft"] and not release["immutable"],
                "Missing tag on published release",
            )
            tag = api(
                repo + "/git/tags",
                {
                    "tag": "v" + plan["version"],
                    "message": "DTOS v"
                    + plan["version"]
                    + " / build "
                    + str(plan["build"]),
                    "object": main,
                    "type": "commit",
                },
            )
            api(
                repo + "/git/refs",
                {"ref": "refs/tags/v" + plan["version"], "sha": tag["sha"]},
            )
        tag = api(tag_ref_path)["object"]
        if tag["type"] == "tag":
            tag = api(repo + "/git/tags/" + tag["sha"])["object"]
        require(
            tag["type"] == "commit" and tag["sha"] == main,
            "Version tag does not resolve to approved merge",
        )
        if release["draft"]:
            _, latest = verify_context(plan, operation)
            require(latest == main, "Main changed before immutable publication")
            verify_remote_assets(api(release_path), expected, complete=True)
            api(release_path, {"draft": False})
        release = api(release_path)
        require(
            not release["draft"]
            and release.get("immutable") is True
            and release["target_commitish"] == main,
            "Published release is not immutable or targets wrong merge",
        )
        verify_remote_assets(release, expected, complete=True)
        verify_remote_bytes(plan, root, expected)
        verify_production(plan, main, root)
    write_json(
        root / "publication.json",
        {
            "operation": operation,
            "publisher": os.environ["GITHUB_SHA"],
            "candidate": plan["candidate"],
            "tree": plan["tree"],
            "main": main,
            "release_id": release["id"],
            "draft": release["draft"],
            "immutable": release.get("immutable"),
            "url": release["html_url"],
            "attachments": [
                {"name": n, "bytes": s, "sha256": h}
                for n, (s, h) in sorted(expected.items())
            ],
        },
    )


def verify_production(plan, sha, root):
    import time

    attempts = []
    ready = None
    for _ in range(60):
        try:
            request = urllib.request.Request(
                "https://dtos.onrender.com/health/ready",
                headers={"Cache-Control": "no-cache"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.load(response)
            attempts.append(data)
            if (
                data.get("status") == "ready"
                and data.get("version") == plan["version"]
                and data.get("build") == plan["build"]
                and data.get("deployment", {}).get("commit") == sha
            ):
                ready = data
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            attempts.append({"error_type": type(exc).__name__})
        finally:
            write_json(root / "readiness.json", attempts)
        time.sleep(10)
    require(
        ready is not None,
        "Approved production identity not ready in bounded observation",
    )
    results = []
    for path, expected in [
        ("/health/live", 200),
        ("/welcome", 200),
        ("/account/sign-in", 200),
        ("/api/my-dtos", 401),
        ("/api/inspect/live/teams", 401),
    ]:
        try:
            with urllib.request.urlopen(
                "https://dtos.onrender.com" + path, timeout=15
            ) as response:
                code = response.status
                response.read()
        except urllib.error.HTTPError as exc:
            code = exc.code
        require(code == expected, "Production read-only smoke failed: " + path)
        results.append({"path": path, "status": code})
    write_json(
        root / "production-smoke.json",
        {
            "readiness": ready,
            "reads": results,
            "scope": "Bounded public read-only requests; no private-account mutations or heavy production workloads.",
        },
    )


def verify_plan(plan):
    require(plan.get("finalized") is True, "Release plan is not finalized")
    require(
        plan.get("roster_source_scope_tests") == 20,
        "Roster source-scope population missing",
    )
    require(
        plan.get("market_roster_tests") == 21,
        "Market roster regression population missing",
    )
    require(
        plan.get("capital_tests") == 14, "Draft-capital regression population missing"
    )
    require(
        plan.get("franchise_progress_tests") == 16,
        "Franchise movement test population missing",
    )
    require(
        plan.get("acquisition_tests") == 20, "Acquisition regression population missing"
    )
    require(
        plan.get("fixture_isolation_tests") == 10, "Normal execution population missing"
    )
    validate_recovery_parts(plan)
    if "prior_evidence_parts" in plan:
        validate_recovery_parts(plan, family="prior")
    for field in (
        "draft_id",
        "canonical_tests",
        "canonical_entries",
        "local_canonical_entries",
        "product_tests",
    ):
        require(
            type(plan.get(field)) is int and plan[field] > 0,
            "Missing final release evidence: " + field,
        )
    for field in ("candidate", "tree", "baseline"):
        require(
            isinstance(plan.get(field), str)
            and re.fullmatch("[0-9a-f]{40}", plan[field]),
            "Invalid source identity: " + field,
        )
    for field in ("recovery_sha256", "prior_evidence_sha256"):
        require(
            isinstance(plan.get(field), str)
            and re.fullmatch("[0-9a-f]{64}", plan[field]),
            "Missing evidence checksum: " + field,
        )
    required = {
        "current-production-coverage-original.zip",
        "market-history-coverage-original.zip",
        "canonical-original.zip",
        "current-history-original.zip",
        "history-followthrough-original.zip",
        "preflight-original.zip",
        "trade-resource-original.zip",
        "league-entry-original.zip",
        "actuals-restoration-original.zip",
        "restoration-unused-original.zip",
        "resident-refresh-original.zip",
        "lifecycle-ordinary.zip",
        "lifecycle-archive-warmed.zip",
        "lifecycle-combined-read.zip",
        "public-welcome-security.zip",
    }
    files = [x.get("file") for x in plan.get("artifacts", [])]
    require(required <= set(files), "Missing mandatory release artifacts")
    require(
        len(files) == len(set(files)) == len(required),
        "Unexpected or duplicate release artifact population",
    )
    require(
        sum(len(x.get("jobs", [])) for x in plan.get("runs", [])) == 13,
        "Required thirteen-job population missing",
    )
    require(
        all(type(run.get("id")) is int and run["id"] > 0 for run in plan["runs"]),
        "Final validation run identities missing",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--operation", choices=["audit", "prepare", "publish"], required=True
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(".validation/guarded-release")
    )
    parser.add_argument("--prepared-run", type=int)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    outcome = {
        "operation": args.operation,
        "publisher": os.environ.get("GITHUB_SHA"),
        "candidate": plan["candidate"],
        "passed": False,
    }
    try:
        verify_plan(plan)
        prepare_or_publish(plan, args.output, args.operation, args.prepared_run)
        outcome["passed"] = True
    except Exception as exc:
        outcome["error_type"] = type(exc).__name__
        if isinstance(exc, RuntimeError):
            outcome["reason"] = str(exc)
        raise
    finally:
        write_json(args.output / "outcome.json", outcome)
    print("Verified guarded release " + args.operation + " completed.")


if __name__ == "__main__":
    main()
