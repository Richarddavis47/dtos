"""Disposable real v2134 publisher -> running reader; no provider calls/backfill."""

from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch


def isolated(root):
    for key in (
        "DTOS_CACHE_FILE",
        "DTOS_DATA_WAREHOUSE_FILE",
        "DTOS_HISTORY_DB_FILE",
        "DTOS_PROJECTION_DB_FILE",
        "DTOS_INTELLIGENCE_CHECKPOINT_FILE",
        "DTOS_METADATA_DB_FILE",
        "DTOS_ACCOUNT_DB_FILE",
        "DTOS_GLOBAL_EVIDENCE_FILE",
        "DTOS_FOIS_DB_FILE",
    ):
        os.environ[key] = str(root / (key + ".sqlite3"))
    os.environ["DTOS_SLEEPER_SEASON_CACHE_ROOT"] = str(root / "season")
    os.environ["DTOS_HISTORY_STORAGE_ROOT"] = str(root / "history")
    os.environ["DTOS_DURABLE_HISTORY_REQUIRED"] = "false"
    os.environ["DTOS_BACKGROUND_START_DELAY"] = "99999"


def worker(code_root, root, publish, browser=False):
    bodies = []
    sys.path.insert(0, str(code_root))
    isolated(root)
    from src.core.projection_intelligence.service import ProjectionService
    from tests.test_trade_intelligence import fixture_data
    from services.player_projection_view import player_projection_view
    from src.core.projection_intelligence.scoring import DISPLAY_METHOD_VERSION

    cases = [
        ("missing", "TE", 0.5, {"rec": 5}),
        ("explicit", "TE", 0.5, {"rec": 5, "bonus_rec_te": 5}),
        ("zero", "TE", 0.5, {"rec": 5, "bonus_rec_te": 0}),
        ("none", "TE", 0, {"rec": 5}),
        ("wr", "WR", 0.5, {"rec": 5}),
        ("other", "TE", 1, {"rec": 5}),
        ("unavailable", "TE", 0.5, {}),
    ]
    results = []
    with patch("services.global_evidence.retained_global_evidence", return_value=None):
        for name, pos, premium, stats in cases:
            data = fixture_data()
            data.update(week=1, roster_positions=["TE", "BN"])
            data["league"].update(
                league_id=name,
                season="2026",
                roster_positions=["TE", "BN"],
                scoring_settings={"rec": 1, "bonus_rec_te": premium},
                settings={"leg": 1, "playoff_week_start": 14},
            )
            data["scoring_settings"] = data["league"]["scoring_settings"]
            data["players"]["1-TE-8"]["position"] = pos
            feeds = {
                week: [
                    {
                        "player_id": pid,
                        "season": 2026,
                        "week": week,
                        "player": {"position": p["position"]},
                        "stats": stats,
                    }
                    for pid, p in data["players"].items()
                ]
                for week in (1, 2)
            }
            path = root / (name + ".sqlite3")
            service = ProjectionService(path, league_id=name)
            if publish:
                snapshot = service.publish_horizon(
                    feeds, data=data, league_id=name, season=2026, current_week=1
                )
                row = snapshot["players"]["1-TE-8"]
                (root / (name + ".json")).write_text(
                    json.dumps(
                        {"generation": snapshot["projection_snapshot_id"], "row": row}
                    )
                )
                results.append(
                    {
                        "case": name,
                        "canonical": row["canonical_projection"],
                        "display": row["sleeper_web_display_projection"],
                        "method": row["display_method_version"],
                    }
                )
                continue
            prior = json.loads((root / (name + ".json")).read_text())
            snapshot = service.snapshot()
            row = snapshot["players"]["1-TE-8"]
            assert row["canonical_projection"] == prior["row"]["canonical_projection"]
            assert snapshot["projection_snapshot_id"] == prior["generation"]
            assert row["sleeper_web_display_projection"] is None
            assert (
                row["retained_display_evidence"]["value"]
                == prior["row"]["sleeper_web_display_projection"]
            )
            size = path.stat().st_size
            service.begin_external_refresh()
            service.fail_external_refresh(RuntimeError("Controlled provider timeout"))
            view = player_projection_view(data, "1-TE-8", service)
            if view["value"] is not None:
                assert "incompatible" in view["display_reason"]
                assert "unverified" in view["display_reason"]
            for _ in range(8):
                assert player_projection_view(data, "1-TE-8", service) == view
            assert size == path.stat().st_size
            restarted = ProjectionService(path, league_id=name)
            assert (
                player_projection_view(data, "1-TE-8", restarted)["value"]
                == view["value"]
            )
            foreign = {**data, "league": {**data["league"], "league_id": "foreign"}}
            assert player_projection_view(foreign, "1-TE-8", service)["value"] is None
            wrong = {**data, "scoring_settings": {"rec": 2}}
            assert player_projection_view(wrong, "1-TE-8", service)["value"] is None
            route_checks(data, service, view, bodies)
            current = service.publish_horizon(
                feeds, data=data, league_id=name, season=2026, current_week=1
            )
            current_row = current["players"]["1-TE-8"]
            assert current_row["canonical_projection"] == view["value"]
            assert current_row["display_method_version"] == DISPLAY_METHOD_VERSION
            size = path.stat().st_size
            identity = current["projection_snapshot_id"]
            for _ in range(3):
                assert (
                    service.publish_horizon(
                        feeds, data=data, league_id=name, season=2026, current_week=1
                    )["projection_snapshot_id"]
                    == identity
                )
            assert size == path.stat().st_size
            results.append(
                {
                    "case": name,
                    "canonical": view["value"],
                    "old_display": prior["row"]["sleeper_web_display_projection"],
                    "qualified_display": view["display"],
                    "failed_refresh_safe": True,
                    "same_source_republish_stable": True,
                    "unchanged_read_growth": 0,
                }
            )
    if browser and not publish:
        browser_checks(bodies)
    print(json.dumps(results), flush=True)


def route_checks(data, service, view, bodies):
    import asyncio
    from types import SimpleNamespace
    from fastapi import FastAPI
    import dtos_app
    from fastapi.testclient import TestClient
    from routes.teams import create_teams_router
    from routes.transactions import create_transactions_router
    from routes.matchups import create_matchups_router
    from services.matchup_season import prepare_season_matchups
    from src.core.intelligence.orchestrator import IntelligenceOrchestrator
    from src.core.intelligence.cache import IntelligenceCache

    async def fresh():
        pass

    rows = [
        {
            "roster_id": t["roster_id"],
            "matchup_id": 1,
            "starters": [f"{t['roster_id']}-TE-8"],
            "players": [p["id"] for p in t["players"]],
            "points": 11,
            "starters_points": [11],
        }
        for t in data["teams"][:2]
    ]

    async def fetch(_):
        return rows

    data["season_matchups"] = asyncio.run(
        prepare_season_matchups(
            data["league"], 1, rows, fetch, observed_at="controlled"
        )
    )
    engine = IntelligenceOrchestrator(cache=IntelligenceCache())
    history = SimpleNamespace(
        player_dossier=lambda pid: {
            "season_summaries": [],
            "ownership_timeline": [],
            "league_origin": {},
            "identity": {"canonical_id": pid, "resolution_status": "resolved"},
        },
        franchise_history=lambda rid: {
            "standings": [],
            "transactions": [],
            "identities": [],
            "roster_snapshots": [],
            "franchise_id": f"{data['league']['league_id']}:{rid}",
        },
    )
    with ExitStack() as stack:
        for name in ("routes.transactions", "routes.teams", "routes.matchups"):
            stack.enter_context(
                patch(
                    name + ".current_league_context",
                    return_value=SimpleNamespace(
                        league_id=data["league"]["league_id"], projection=service
                    ),
                )
            )
        stack.enter_context(
            patch(
                "src.core.projection_intelligence.projection_service.snapshot",
                side_effect=service.snapshot,
            )
        )
        stack.enter_context(
            patch(
                "src.core.projection_intelligence.projection_service.week_snapshot",
                side_effect=service.week_snapshot,
            )
        )
        for name in ("services.team_headquarters", "services.asset_intelligence"):
            stack.enter_context(patch(name + ".intelligence_orchestrator", engine))
        for name in ("routes.transactions", "routes.teams"):
            stack.enter_context(patch(name + ".historical_graph", return_value=history))
        app = FastAPI()
        common = dict(
            ensure_fresh=fresh,
            require_data=lambda: data,
            page=dtos_app.page,
        )
        app.include_router(create_teams_router(**common, state={}))
        app.include_router(
            create_transactions_router(**common, refresh_transactions=fresh, state={})
        )
        app.include_router(create_matchups_router(**common))
        with TestClient(app) as client:
            for url in (
                "/teams/1",
                "/players/1-TE-8?week=1",
                "/players/1-TE-8/projections?week=1",
                "/matchups/1?week=1",
            ):
                response = client.get(url)
                assert response.status_code == 200, (url, response.status_code)
                bodies.append((url, response.text, view["value"]))
                if view["value"] is not None:
                    assert "Retained display method is incompatible" in response.text, (
                        url
                    )
                    assert "unverified" in response.text, url


def browser_checks(bodies):
    from playwright.sync_api import sync_playwright
    from tools.validation.browser_runtime import launch_chromium

    count = 0
    with sync_playwright() as engine:
        browser = launch_chromium(engine, headless=True)
        try:
            for width, height in (
                (320, 432),
                (320, 844),
                (375, 667),
                (390, 844),
                (1280, 900),
            ):
                page = browser.new_page(viewport={"width": width, "height": height})
                page.route("**/*", lambda route: route.abort())
                for url, body, value in bodies:
                    page.set_content(body)
                    # Open the affected projection qualifications and roster;
                    # unrelated archive/provider tables have their own journey gates.
                    page.get_by_text(
                        "Retained display method is incompatible", exact=False
                    ).locator("xpath=ancestor::details").evaluate_all(
                        "rows=>rows.forEach(e=>e.open=true)"
                    )
                    if (
                        page.evaluate("document.documentElement.scrollWidth")
                        > width + 1
                    ):
                        print(
                            page.evaluate(
                                """() => [...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,60),r:e.getBoundingClientRect().right,w:e.getBoundingClientRect().width})).filter(e=>e.r>innerWidth+1).slice(-12)"""
                            ),
                            flush=True,
                        )
                    assert (
                        page.evaluate("document.documentElement.scrollWidth")
                        <= width + 1
                    ), (url, width)
                    if value is not None:
                        assert page.get_by_text(
                            "Retained display method is incompatible", exact=False
                        ).count(), url
                    count += 1
                page.close()
        finally:
            browser.close()
    print(
        json.dumps(
            {"responsive_legacy_route_renders": count, "physical_safari": False}
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-root", type=Path)
    parser.add_argument("--publication-root", type=Path)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    if args.code_root:
        worker(args.code_root, args.publication_root, args.publish, args.browser)
        return
    current = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="dtos-display-boundary-") as folder:
        root = Path(folder)
        old = root / "2134"
        old.mkdir()
        publications = root / "publications"
        publications.mkdir()
        archive = root / "source.tar"
        with archive.open("wb") as stream:
            subprocess.run(
                ["git", "archive", "v1.21.34"], cwd=current, stdout=stream, check=True
            )
        with tarfile.open(archive) as source:
            source.extractall(old, filter="data")
        for code, publish in ((old, True), (current, False)):
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--code-root",
                str(code),
                "--publication-root",
                str(publications),
            ]
            if publish:
                command.append("--publish")
            elif args.browser:
                command.append("--browser")
            subprocess.run(
                command,
                cwd=code,
                check=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )


if __name__ == "__main__":
    main()
