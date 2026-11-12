from pathlib import Path
P=Path('/workspace/dtos-publisher-2250/tools/release/publish.py')
s=P.read_text()
addition='''def verify_franchise_progress_tests(path, plan, prefix=""):
    with zipfile.ZipFile(path) as archive:
        rows = [json.loads(line) for line in archive.read(prefix + "tests.jsonl").splitlines()]
    selected = [r for r in rows if "test_franchise_trade_progress." in r.get("test", "")]
    starts = [r["test"] for r in selected if r.get("event") == "start"]
    stops = [r["test"] for r in selected if r.get("event") == "stop"]
    require(plan.get("franchise_progress_tests") == 16 and len(starts) == len(set(starts)) == 16
            and Counter(starts) == Counter(stops)
            and not any(r.get("event") in {"error", "failure", "skip"} for r in selected),
            "Franchise movement regression population incomplete or failed")
    return starts


def verify_franchise_progress_browser(path, plan, prefix="completed-trade-observations/"):
    result = verify_completed_trade_browser(path, plan, prefix=prefix)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read(prefix + "browser.json"))
    for row in report["records"]:
        known = row["control"].startswith("Day retained")
        require(row.get("season_filter") == (2026 if known else None)
                and row.get("filtered_pagination_conversion_return") is known
                and row.get("gross_player_transfers") == ([1, 3] if known else None)
                and row.get("gross_pick_transfers") == ([5, 2] if known else None),
                "Franchise movement season/transfer/conversion journey missing")
    return result


def verify_franchise_progress_cases(path, plan):
    verify_completed_trade_cases(path, plan)
    with zipfile.ZipFile(path) as archive:
        feature = json.loads(archive.read("feature/feature.json"))
    rows = {r["case"]: r["summary"] for r in feature["cases"]}
    for kind, expected in (("player", (1, 3, -2)), ("pick", (5, 2, 3))):
        counts = rows["retained_day"].get("movements", {}).get(kind, {})
        require(tuple(counts.get(k) for k in ("acquired", "sent", "net")) == expected
                and counts.get("complete_in_sample") is True,
                "Retained gross/net movement mismatch")
    unknown = rows["unknown"]
    require(unknown.get("assets") == [] and all(
        unknown.get("movements", {}).get(kind, {}).get(k) is None
        for kind in ("player", "pick") for k in ("acquired", "sent", "net")),
        "Unknown period turned into movement zero")
    partial = rows["partial_pick"].get("movements", {})
    require(partial.get("pick", {}).get("net") is None
            and partial.get("pick", {}).get("complete_in_sample") is False
            and partial.get("player", {}).get("complete_in_sample") is True,
            "Incomplete picks contaminated supported player movement")
    assets = rows["retained_day"].get("assets", [])
    converted = [a for a in assets if a.get("kind") == "player" and a.get("id") == "13346"]
    require(len(converted) == 1 and converted[0].get("acquired") == 0
            and converted[0].get("sent") == 1,
            "Pick conversion recounted as trade acquisition")
    for row in rows.values():
        require(len(row.get("assets", [])) <= 256
                and all(len(a.get("references", [])) <= 4 for a in row.get("assets", [])),
                "Unbounded franchise movement detail")
    return {"passed": True, "scope": "Retained source replay and disposable controls, not owner live acceptance"}


'''
s=s.replace('def verify_prior_evidence(path, plan):',addition+'def verify_prior_evidence(path, plan):')
s=s.replace('            verify_roster_source_scope_tests(path, plan)\n','            verify_roster_source_scope_tests(path, plan)\n            verify_franchise_progress_tests(path, plan)\n')
s=s.replace('            verify_completed_trade_browser(path, plan)\n','            verify_completed_trade_browser(path, plan)\n            verify_franchise_progress_browser(path, plan)\n')
s=s.replace('    local_canonical = verify_local_recovery(recovery, plan)\n','    local_canonical = verify_local_recovery(recovery, plan)\n    verify_franchise_progress_tests(recovery, plan, prefix="local-canonical/")\n    verify_franchise_progress_browser(recovery, plan, prefix="feature/")\n    verify_franchise_progress_cases(recovery, plan)\n')
s=s.replace('def verify_plan(plan):\n','def verify_plan(plan):\n    require(plan.get("franchise_progress_tests") == 16, "Franchise movement test population missing")\n')
P.write_text(s)
