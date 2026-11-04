"""Sanitized 10-team/32-player/12-exact-pick production-scale test publication."""

import copy
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch
from tests import test_capital_strategy_reconciliation as fixtures
from src.core.intelligence.team_strength import prepare_for_data


def prepare_fixture(root, *, distinct_weeks=True):
    f = fixtures.CapitalStrategyTests()
    f.setUp()
    try:
        d = f.data
        template = copy.deepcopy(d["teams"][0])
        d["teams"] = []
        d["players"] = {}
        f.points = {}
        d["week"] = 5
        d["league"]["roster_positions"] = [
            "QB",
            "RB",
            "RB",
            "WR",
            "WR",
            "WR",
            "TE",
            "FLEX",
            "FLEX",
            "FLEX",
            "SUPER_FLEX",
        ] + ["BN"] * 15
        d["league"]["settings"].update(
            leg=5, last_scored_leg=4, playoff_week_start=15, playoff_teams=6
        )
        for rid in range(1, 11):
            team = dict(
                copy.deepcopy(template),
                roster_id=rid,
                team_name=f"Sanitized franchise {rid}",
                strategy="RETOOL",
            )
            team["players"] = []
            for index, pos in enumerate(
                ["QB"] * 4 + ["RB"] * 8 + ["WR"] * 14 + ["TE"] * 6
            ):
                pid = f"{rid}-{pos}-{index}"
                points = (
                    {
                        "QB": 24 if rid == 1 else 13,
                        "RB": 14,
                        "WR": 8 if rid == 1 else 17,
                        "TE": 12,
                    }[pos]
                    - index % 4 * 1.2
                    + rid % 3 * 0.2
                )
                team["players"].append(
                    {"id": pid, "position": pos, "name": pid, "roster_slot": "Taxi" if index in {3, 10, 11, 24, 25, 31} else "Bench"}
                )
                d["players"][pid] = {
                    "position": pos,
                    "full_name": pid,
                    "age": 23 + index % 10,
                }
                f.points[pid] = points
            team["picks_owned"] = [
                {
                    "year": year,
                    "round": r,
                    "original_roster_id": rid % 10 + 1,
                    "current_owner_id": rid,
                }
                for year in (2027, 2028, 2029)
                for r in (1, 2, 3, 4)
            ]
            d["teams"].append(team)
        f.prices(
            **{
                pid: 250 if int(pid.split("-")[-1]) % 4 == 0 else 100
                for pid in f.points
            }
        )
        quotes = d["market_data"]["pick_quotes"]["FantasyCalc"]
        d["market_data"]["pick_quotes"]["FantasyCalc"] = [dict(row, year=year)
            for year in (2027, 2028, 2029) for row in quotes]
        f.payloads = {
            week: [
                {
                    "player_id": pid,
                    "season": 2026,
                    "week": week,
                    "stats": {"pass_yd": points + (week if distinct_weeks else week % 3) * 0.1},
                    "player": {"position": d["players"][pid]["position"]},
                }
                for pid, points in f.points.items()
            ]
            for week in range(5, 18)
        }
        f.reader.publish_horizon(
            f.payloads, data=d, league_id="league-1", season=2026, current_week=5
        )
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(f.reader, d)
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        (root / "data.json").write_text(json.dumps(d, sort_keys=True))
        with (
            sqlite3.connect(f.reader._database_file) as source,
            sqlite3.connect(root / "projections.sqlite3") as target,
        ):
            source.backup(target)
    finally:
        f.doCleanups()
