"""Run DTOS HTTP smoke tests against an explicitly started local server."""
from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen


def get(base_url: str, path: str, expected: int = 200) -> bytes:
    try:
        with urlopen(base_url.rstrip("/") + path, timeout=60) as response:
            status = response.status
            body = response.read()
    except HTTPError as exc:
        status = exc.code
        body = exc.read()
    if status != expected:
        raise AssertionError(f"{path}: expected HTTP {expected}, received {status}; body={body[:300]!r}")
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    args = parser.parse_args()

    major = (
        "/", "/teams", "/matchups", "/transactions", "/picks", "/settings",
        "/api/status", "/api/platform/health", "/api/intelligence", "/api/league", "/api/players", "/front-offices",
        "/api/front-offices", "/trades", "/api/trades", "/openapi.json",
    )
    for path in major:
        get(args.base_url, path)

    league = json.loads(get(args.base_url, "/api/league"))
    teams = league.get("teams") or []
    if not teams:
        raise AssertionError("Cached league contract contains no teams.")
    roster_ids = [int(team["roster_id"]) for team in teams]
    for roster_id in roster_ids:
        get(args.base_url, f"/teams/{roster_id}")
        get(args.base_url, f"/front-offices?front_office={roster_id}")
        organization = json.loads(get(args.base_url, f"/api/front-offices?front_office={roster_id}"))
        if organization.get("active_front_office") != roster_id:
            raise AssertionError(f"Front Office context {roster_id} did not persist through the API.")
        get(args.base_url, f"/trades?front_office={roster_id}")
        get(args.base_url, f"/api/trades?front_office={roster_id}")

    player_index = json.loads(get(args.base_url, "/api/players"))
    players = player_index.get("players") or []
    if not players or not players[0].get("player_id"):
        raise AssertionError("Canonical cached player index contains no discoverable player ID.")
    player_id = quote(str(players[0]["player_id"]), safe="")
    for roster_id in roster_ids:
        get(args.base_url, f"/players/{player_id}?front_office={roster_id}")

    get(args.base_url, "/players/", expected=404)
    get(args.base_url, "/players/dtos-validation-missing-player", expected=404)
    print(
        f"HTTP smoke passed: {len(major)} major endpoints, {len(roster_ids)} Team HQ pages, "
        f"{len(roster_ids)} Front Office dossiers/APIs/trade contexts, and one player dossier across all contexts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
