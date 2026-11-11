"""Verify immutable release, final deployment identity and bounded guest/static reads only."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from common import BASE, SOURCE_REPOSITORY, command, load_source, now, write_json

CONTROLLER = Path("/workspace/dtos-publisher-2246")


def main():
    source = load_source()
    plan = json.loads((CONTROLLER / ".github/release-plans/2246.json").read_text())
    merge = json.loads((BASE / "merged-source.json").read_text())
    frozen = json.loads((BASE / "publisher-source.json").read_text())
    verified = json.loads((BASE / "published-attachment-verification.json").read_text())
    expected = merge["merge_commit"]
    assert merge["candidate"] == source["candidate"] and merge["tree"] == source["tree"] and merge["validated_tree_unchanged"]
    assert merge["publisher"] == frozen["publisher"] == verified["publisher"]
    assert verified["candidate"] == source["candidate"] and verified["tree"] == source["tree"]
    assert verified["native_all_attachment_bytes_read_back"] and verified["cloud_api_digests_match_certificate"] and verified["front_office_workflow_verified"]
    repo = "repos/" + plan["repository"]

    def api(tail):
        return json.loads(subprocess.check_output(["gh", "api", repo + "/" + tail], text=True))

    run = api("actions/runs/" + str(json.loads((BASE / "publication-run.json").read_text())["id"]))
    assert run["status"] == "completed" and run["conclusion"] == "success" and run["head_sha"] == frozen["publisher"]
    assert run["event"] == "workflow_dispatch" and run["path"] == ".github/workflows/canonical-release-recovery.yml"
    release = api("releases/" + str(plan["draft_id"]))
    assert not release["draft"] and release["immutable"] and release["tag_name"] == "v" + source["version"]
    assert release["target_commitish"] == expected and len(release["assets"]) == len(verified["attachments"]) == 23
    attachments = {row["name"]: row for row in verified["attachments"]}
    assert {row["name"] for row in release["assets"]} == set(attachments)
    for row in release["assets"]:
        admitted = attachments[row["name"]]
        assert row["state"] == "uploaded" and row["size"] == admitted["bytes"] and row["digest"] == "sha256:" + admitted["sha256"]
    ref = api("git/ref/tags/v" + source["version"])["object"]
    if ref["type"] == "tag":
        ref = api("git/tags/" + ref["sha"])["object"]
    assert ref["type"] == "commit" and ref["sha"] == expected
    assert api("git/ref/heads/main")["object"]["sha"] == expected
    assert api("git/commits/" + expected)["tree"]["sha"] == source["tree"]
    base_url = "https://dtos.onrender.com"
    with urlopen(Request(base_url + "/health/ready", headers={"Cache-Control": "no-cache"}), timeout=20) as response:
        ready = json.load(response)
    assert ready["status"] == "ready" and ready["version"] == source["version"] and ready["build"] == source["build"]
    assert ready["deployment"]["commit"] == expected

    class VisibleText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.hidden = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self.hidden += 1

        def handle_endtag(self, tag):
            if tag in ("script", "style"):
                self.hidden = max(0, self.hidden - 1)

        def handle_data(self, data):
            if not self.hidden:
                self.parts.append(data)

    static = {"/static/js/contextual_navigation.js", "/static/js/trade_workspace.js",
              "/static/js/trade_comparison.js", "/static/css/trade_workspace.css"}
    changed = command("git", "diff", "--name-only", source["baseline"], source["candidate"], cwd=SOURCE_REPOSITORY).splitlines()
    static.update("/" + path for path in changed if path.startswith("static/") and path.endswith((".js", ".css")))
    checks = [("/health/live", 200), ("/welcome", 200), ("/account/sign-in", 200), ("/api/my-dtos", 401), ("/api/inspect/live/teams", 401)]
    checks += [(path, 200) for path in sorted(static)]
    reads = []
    for path, code in checks:
        try:
            with urlopen(Request(base_url + path, headers={"Cache-Control": "no-cache"}), timeout=20) as response:
                status = response.status
                raw = response.read(2 * 1024 * 1024 + 1)
                assert len(raw) <= 2 * 1024 * 1024, "Unexpected public asset size"
        except HTTPError as exc:
            status = exc.code
            raw = b""
        assert status == code, (path, status)
        item = dict(path=path, status=status, guest_read_only=True)
        if path == "/welcome":
            text = VisibleText()
            text.feed(raw.decode())
            assert not re.search(r"\b(?:beta|prerelease|pre-release)\b", " ".join(text.parts), re.I)
        if path in static:
            original = subprocess.check_output(["git", "-C", str(SOURCE_REPOSITORY), "show", source["candidate"] + ":" + path.lstrip("/")])
            assert raw == original, "Deployed static asset differs from final validated source: " + path
            item.update(sha256=hashlib.sha256(original).hexdigest(), bytes=len(original))
        reads.append(item)

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = build_opener(NoRedirect)
    for path in ("/front-offices", "/market", "/players/1", "/trades/recommended", "/trades/calculator", "/history",
                 "/history/team/source-scope:franchise:4", "/trades/history/retained-source-control"):
        try:
            with opener.open(Request(base_url + path, headers={"Cache-Control": "no-cache"}), timeout=20) as response:
                status = response.status
                location = response.headers.get("Location", "")
        except HTTPError as exc:
            status = exc.code
            location = exc.headers.get("Location", "")
        assert status == 303 and location.startswith("/account/sign-in"), (path, status, location)
        reads.append(dict(path=path, status=status, guest_read_only=True,
                          scope="Authentication/public entry boundary only; no private content or league hydration"))
    write_json(BASE / "production-readonly-smoke.json", dict(observed_at=now(), production_ready=ready, reads=reads,
        scope="Bounded public guest/static reads only. No owner entry/search, login, sync, FOIS rebuild or saved preference mutation."))
    write_json(BASE / "publication-verified.json", dict(run=run, release=release, tag_target=ref["sha"], tree=source["tree"],
        candidate=source["candidate"], merge_commit=expected,
        verification="Native frozen publisher verified all attachment bytes. This independent reader confirms certificate/API digests, immutable release/tag, deployed merge and source-identical public static assets."))
    print("Production identity,23immutable assets and bounded guest/static reads verified.")


if __name__ == "__main__":
    main()

