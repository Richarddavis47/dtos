from pathlib import Path
P=Path('/workspace/dtos-publisher-2249');p=P/'tools/release/publish.py';s=p.read_text()
block='''def verify_roster_source_scope_tests(path, plan):
    with zipfile.ZipFile(path) as archive:
        rows = [json.loads(line) for line in archive.read("tests.jsonl").splitlines()]
    def selected(row):
        return "test_roster_source_scope." in row.get("test", "") or "test_roster_source_scope_browser." in row.get("test", "")
    starts = [r["test"] for r in rows if r.get("event") == "start" and selected(r)]
    stops = [r["test"] for r in rows if r.get("event") == "stop" and selected(r)]
    require(len(starts) == len(set(starts)) == plan["roster_source_scope_tests"] == 20
            and Counter(starts) == Counter(stops),
            "Roster source-scope regression population incomplete")
    return starts


def verify_roster_source_scope(path, plan, prefix="browser/roster-source-scope/"):
    """Source-bound prepared-source/browser proof, never owner live acceptance."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        for shape in ("oneqb-kdef", "sf"):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                stem = prefix + shape + "-" + str(width)
                row = json.loads(archive.read(stem + ".json"))
                require(row.get("commit") == plan["candidate"] and row.get("tree") == plan["tree"],
                        "Roster source-scope capture source mismatch")
                require(row.get("viewport") == [width, height] and row.get("exact_target") == "player:2-RB-0"
                        and all(row.get(key) is True for key in ("unrostered_missing_projection", "my_team_supported", "explicit_generate_required", "keyboard", "no_navigation_solver"))
                        and row.get("touch_emulation") is (width < 1000),
                        "Roster source-scope supported journey incomplete")
                require("not owner live" in row.get("scope", ""), "Roster fixture/live distinction missing")
                require(archive.read(stem + ".png").startswith(b"\\x89PNG\\r\\n\\x1a\\n"), "Roster journey image missing")
        for reason in ("unknown-k", "unknown-def", "eligible-missing", "aging", "failed-refresh"):
            stem = prefix + reason
            row = json.loads(archive.read(stem + ".json"))
            require(row.get("commit") == plan["candidate"] and row.get("tree") == plan["tree"],
                    "Roster withholding capture source mismatch")
            require(row.get("reason") == reason and all(row.get(key) is True for key in ("neutral_preserved", "personalized_action_withheld", "no_posts")),
                    "Genuine roster limitations were not preserved")
            require(archive.read(stem + ".png").startswith(b"\\x89PNG\\r\\n\\x1a\\n"), "Roster withholding image missing")
    return dict(candidate=plan["candidate"], tree=plan["tree"], passed=True,
                supported_roundtrips=8, withheld_cases=5,
                scope="Native disposable source/route/browser controls; owner live and physical Safari unverified")


'''
assert 'def verify_roster_source_scope(' not in s
s=s.replace('def verify_draft_capital(',block+'def verify_draft_capital(',1)
s=s.replace('    market_roster = None\n', '    market_roster = None\n    roster_source_scope = None\n',1)
s=s.replace('            verify_market_roster_tests(path, plan)\n','            verify_market_roster_tests(path, plan)\n            verify_roster_source_scope_tests(path, plan)\n',1)
s=s.replace('            market_roster = verify_market_roster(path, plan)\n','            market_roster = verify_market_roster(path, plan)\n            roster_source_scope = verify_roster_source_scope(path, plan)\n',1)
s=s.replace('    require(market_roster is not None, "Hosted Market roster proof absent")\n','    require(market_roster is not None, "Hosted Market roster proof absent")\n    require(roster_source_scope is not None, "Hosted roster source-scope proof absent")\n',1)
s=s.replace('    local_market_roster = verify_market_roster(\n        recovery, plan, prefix="local-canonical/market-needs/"\n    )\n','    local_market_roster = verify_market_roster(\n        recovery, plan, prefix="local-canonical/market-needs/"\n    )\n    local_roster_source_scope = verify_roster_source_scope(\n        recovery, plan, prefix="local-canonical/roster-source-scope/"\n    )\n',1)
s=s.replace('            local_market_roster=local_market_roster,\n','            local_market_roster=local_market_roster,\n            roster_source_scope=roster_source_scope,\n            local_roster_source_scope=local_roster_source_scope,\n',1)
s=s.replace('    require(plan.get("finalized") is True, "Release plan is not finalized")\n','    require(plan.get("finalized") is True, "Release plan is not finalized")\n    require(plan.get("roster_source_scope_tests") == 20, "Roster source-scope population missing")\n',1)
p.write_text(s)
p=P/'tests/test_release_publisher.py';s=p.read_text().replace('                "verify_market_roster_tests",\n','                "verify_market_roster_tests",\n                "verify_roster_source_scope_tests",\n                "verify_roster_source_scope",\n',1);p.write_text(s)
