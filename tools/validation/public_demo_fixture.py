"""Offline generator for the public, fictional football demonstration.

Never imported by a request handler. All analytical work uses disposable stores.
Only the deliberately allowlisted export is read by the public presentation.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

FIXTURE_ID = "public-football-demo-v1"
SCORING = {
    "pass_yd": 0.04,
    "pass_td": 4,
    "pass_int": -2,
    "rush_yd": 0.1,
    "rush_td": 6,
    "rec": 1,
    "rec_yd": 0.1,
    "rec_td": 6,
    "fum_lost": -2,
}
STARTERS = ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX"]


def fixture_input():
    """One fictional league, football statistics, players and exact owned picks."""
    rows = [
        (
            1,
            "harbor-q1",
            "Josh Allen",
            "QB",
            700,
            {"pass_yd": 350, "pass_td": 4, "rush_yd": 40},
        ),
        (
            1,
            "harbor-q2",
            "Lamar Jackson",
            "QB",
            400,
            {"pass_yd": 300, "pass_td": 3, "rush_yd": 60},
        ),
        (
            1,
            "harbor-q3",
            "Jalen Hurts",
            "QB",
            300,
            {"pass_yd": 250, "pass_td": 2, "rush_yd": 60},
        ),
        (
            1,
            "harbor-r1",
            "Bijan Robinson",
            "RB",
            450,
            {"rush_yd": 80, "rush_td": 1, "rec": 2},
        ),
        (
            1,
            "harbor-r2",
            "Christian McCaffrey",
            "RB",
            100,
            {"rush_yd": 40, "rec": 2, "rec_yd": 20},
        ),
        (1, "harbor-w1", "DeVonta Smith", "WR", 400, {"rec": 3, "rec_yd": 40}),
        (1, "harbor-w2", "Ja'Marr Chase", "WR", 100, {"rec": 3, "rec_yd": 50}),
        (1, "harbor-w3", "CeeDee Lamb", "WR", 350, {"rec": 4, "rec_yd": 60}),
        (1, "harbor-t1", "Brock Bowers", "TE", 250, {"rec": 4, "rec_yd": 60}),
        (1, "harbor-t2", "George Kittle", "TE", 50, {"rec": 2, "rec_yd": 20}),
        (
            2,
            "summit-q1",
            "Summit QB One",
            "QB",
            650,
            {"pass_yd": 250, "pass_td": 2, "rush_yd": 50},
        ),
        (
            2,
            "summit-q2",
            "Summit QB Two",
            "QB",
            200,
            {"pass_yd": 250, "pass_td": 1, "pass_int": 1},
        ),
        (
            2,
            "summit-q3",
            "Summit QB Three",
            "QB",
            80,
            {"pass_yd": 200, "pass_td": 1, "pass_int": 1},
        ),
        (
            2,
            "summit-r1",
            "Summit RB One",
            "RB",
            500,
            {"rush_yd": 90, "rush_td": 1, "rec": 2},
        ),
        (
            2,
            "summit-r2",
            "Summit RB Two",
            "RB",
            150,
            {"rush_yd": 50, "rec": 2, "rec_yd": 20},
        ),
        (
            2,
            "summit-w1",
            "Justin Jefferson",
            "WR",
            400,
            {"rec": 8, "rec_yd": 120, "rec_td": 1},
        ),
        (2, "summit-w2", "Summit WR Two", "WR", 380, {"rec": 6, "rec_yd": 120}),
        (2, "summit-w3", "Summit WR Three", "WR", 300, {"rec": 7, "rec_yd": 100}),
        (2, "summit-t1", "Summit TE One", "TE", 280, {"rec": 5, "rec_yd": 60}),
        (2, "summit-t2", "Summit TE Two", "TE", 60, {"rec": 2, "rec_yd": 30}),
    ]
    data = {
        "league": {
            "league_id": FIXTURE_ID,
            "name": "Demo Dynasty League",
            "season": 2026,
            "sport": "nfl",
            "total_rosters": 4,
            "roster_positions": STARTERS + ["BN"] * 6,
            "scoring_settings": deepcopy(SCORING),
            "settings": {
                "leg": 5,
                "last_scored_leg": 4,
                "start_week": 1,
                "playoff_week_start": 17,
                "playoff_teams": 4,
                "playoff_round_type": 0,
                "playoff_type": 0,
            },
        },
        "week": 5,
        "players": {},
        "teams": [],
        "transactions": [],
        "traded_picks": [],
        "market_data": {"generation": FIXTURE_ID, "providers": {"FantasyCalc": {}}},
    }
    for rid, name in [(1, "Harbor Front Office"), (2, "Summit Front Office")]:
        data["teams"].append(
            {
                "roster_id": rid,
                "owner": name,
                "team_name": name,
                "strategy": "RETOOL",
                "wins": 2,
                "losses": 2,
                "ties": 0,
                "points_for": 400,
                "points_against": 400,
                "players": [],
                "picks_owned": [
                    {
                        "year": 2028,
                        "round": 1,
                        "original_roster_id": 3 - rid,
                        "current_owner_id": rid,
                        "original_team": "Summit Front Office"
                        if rid == 1
                        else "Harbor Front Office",
                    }
                ],
            }
        )
    stats = {}
    for rid, pid, name, pos, value, production in rows:
        player = {
            "id": pid,
            "name": name,
            "position": pos,
            "status": "Active",
            "roster_slot": "Bench",
            "team": "DEMO",
        }
        data["teams"][rid - 1]["players"].append(player)
        data["players"][pid] = {
            "full_name": name,
            "position": pos,
            "status": "Active",
            "team": "DEMO",
        }
        data["market_data"]["providers"]["FantasyCalc"][pid] = {
            "value": value * 12,
            "confidence": 90,
        }
        stats[pid] = production
    # Two additional fully projected fictional rosters make the four-team
    # winner bracket and comparison population internally consistent.
    for rid, name in [(3, "Valley Front Office"), (4, "Meadow Front Office")]:
        team = {
            "roster_id": rid,
            "owner": name,
            "team_name": name,
            "strategy": "RETOOL",
            "wins": 2,
            "losses": 2,
            "ties": 0,
            "points_for": 400,
            "points_against": 400,
            "players": [],
            "picks_owned": [],
        }
        for suffix, pos, production in [
            ("q1", "QB", {"pass_yd": 250, "pass_td": 2, "rush_yd": 40}),
            ("q2", "QB", {"pass_yd": 200, "pass_td": 2}),
            ("r1", "RB", {"rush_yd": 90, "rush_td": 1}),
            ("w1", "WR", {"rec": 5, "rec_yd": 80}),
            ("w2", "WR", {"rec": 4, "rec_yd": 60}),
            ("t1", "TE", {"rec": 4, "rec_yd": 50}),
        ]:
            pid = f"demo-{rid}-{suffix}"
            label = f"{name.split()[0]} {pos} {suffix[-1]}"
            player = {
                "id": pid,
                "name": label,
                "position": pos,
                "status": "Active",
                "roster_slot": "Bench",
                "team": "DEMO",
            }
            team["players"].append(player)
            data["players"][pid] = {
                "full_name": label,
                "position": pos,
                "status": "Active",
                "team": "DEMO",
            }
            stats[pid] = production
            data["market_data"]["providers"]["FantasyCalc"][pid] = {
                "value": 1800,
                "confidence": 90,
            }
        data["teams"].append(team)
    return data, stats


def generate():
    """Derive the frozen artifact through unchanged canonical services offline."""
    from services.personal_rankings import (
        METHOD,
        build_universe,
        personal_values,
        to_trade_id,
    )
    from services.trade_intelligence import (
        build_trade_workspace,
        evaluate_trade_request,
    )
    from src.core.intelligence.team_strength import prepare_for_data
    from src.core.projection_intelligence.scoring import fantasy_points
    from src.core.projection_intelligence.service import ProjectionService
    from src.core.trade_intelligence.lineup import optimal_legal_lineup

    data, stats = fixture_input()
    input_hash = sha256(
        json.dumps([data, stats], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with tempfile.TemporaryDirectory(prefix="dtos-public-demo-") as root:
        reader = ProjectionService(Path(root) / "projections.sqlite3")
        payloads = {
            week: [
                {
                    "player_id": pid,
                    "season": 2026,
                    "week": week,
                    "stats": production,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "player": {"position": data["players"][pid]["position"]},
                }
                for pid, production in stats.items()
            ]
            for week in range(5, 19)
        }
        reader.publish_horizon(
            payloads, data=data, league_id=FIXTURE_ID, season=2026, current_week=5
        )
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(reader, data)
        with patch(
            "services.trade_intelligence._trade_projection_service", return_value=reader
        ):
            workspace = build_trade_workspace(data, 1)
            evaluation = evaluate_trade_request(
                data,
                {
                    "active_roster_id": 1,
                    "partner_roster_id": 2,
                    "assets_sent": ["harbor-q2"],
                    "assets_received": ["summit-w1"],
                    "strategy": "RETOOL",
                },
                workspace=workspace,
                projection_reader=reader,
            )["evaluation"]
        snapshot = reader.snapshot()
        projections = {
            pid: row["canonical_projection"] for pid, row in snapshot["players"].items()
        }
        for pid, production in stats.items():
            assert projections[pid] == fantasy_points(
                production, SCORING, data["players"][pid]["position"]
            )

        def lineup(team):
            return optimal_legal_lineup(
                [
                    {**p, "projected_points": projections[p["id"]]}
                    for p in team["players"]
                ],
                STARTERS,
                week=5,
            )

        before = [lineup(t) for t in data["teams"]]
        after_data = deepcopy(data)
        sent = next(p for p in data["teams"][0]["players"] if p["id"] == "harbor-q2")
        received = next(
            p for p in data["teams"][1]["players"] if p["id"] == "summit-w1"
        )
        after_data["teams"][0]["players"] = [
            p for p in after_data["teams"][0]["players"] if p["id"] != "harbor-q2"
        ] + [received]
        after_data["teams"][1]["players"] = [
            p for p in after_data["teams"][1]["players"] if p["id"] != "summit-w1"
        ] + [sent]
        after = [lineup(t) for t in after_data["teams"]]
        for side, pre, post in zip(["active", "partner"], before, after):
            assert pre.available and post.available
            assert (
                evaluation["lineup_impact"][side]["pre"]["projected_points"]
                == pre.projected_points
            )
            assert (
                evaluation["lineup_impact"][side]["post"]["projected_points"]
                == post.projected_points
            )
        selected = {e.asset_id for e in before[0].entries}
        reserves = [
            {
                "asset_id": p["id"],
                "name": p["name"],
                "position": p["position"],
                "points": projections[p["id"]],
            }
            for p in data["teams"][0]["players"]
            if p["id"] not in selected
        ]
        values = {
            asset.asset_id: asset.trade_value
            for pool in workspace["pools"].values()
            for asset in pool
            if asset.kind == "player" and asset.trade_value is not None
        }

        # Reuse the existing complete-universe identity/admission boundary. This
        # offline immutable reader exposes only the canonical workspace prices;
        # it does not price absent picks or act as another valuation engine.
        class DemoMarket:
            generation = FIXTURE_ID
            semantic_generation = FIXTURE_ID

            def __init__(self):
                self.data = data
                self.rows = []
                for pool in workspace["pools"].values():
                    for asset in pool:
                        key = (
                            "player:" + asset.asset_id
                            if asset.kind == "player"
                            else f"pick:{asset.season}:{asset.round}:{asset.original_roster_id}"
                        )
                        self.rows.append(
                            {
                                "asset_id": key,
                                "asset_type": asset.kind,
                                "position": asset.position
                                if asset.kind == "player"
                                else "PICK",
                                "display_name": asset.label,
                                "status": "Active",
                                "values": {"market_value": asset.trade_value},
                            }
                        )

            def identity(self):
                return {"league_id": FIXTURE_ID, "market_generation": FIXTURE_ID}

            def directory(
                self,
                *,
                offset=0,
                limit=250,
                sort="market",
                direction="desc",
                minimum=None,
                availability_asset_ids=None,
            ):
                rows = [
                    r
                    for r in self.rows
                    if (
                        availability_asset_ids is None
                        or r["asset_id"] in availability_asset_ids
                    )
                    and (
                        minimum is None
                        or r["values"]["market_value"] is not None
                        and r["values"]["market_value"] >= minimum
                    )
                ]
                rows = sorted(
                    rows,
                    key=lambda r: (
                        r["values"]["market_value"]
                        if r["values"]["market_value"] is not None
                        else -1,
                        r["asset_id"],
                    ),
                    reverse=True,
                )
                return {
                    **self.identity(),
                    "total": len(rows),
                    "assets": rows[offset : offset + limit],
                }

        market = DemoMarket()
        universe = build_universe(data, market)
        canonical_baseline = [r["asset_id"] for r in universe["rows"]]
        personal_order = ["player:summit-w1"] + [
            pid for pid in canonical_baseline if pid != "player:summit-w1"
        ]
        zero = personal_values(
            {"order": canonical_baseline, "baseline": {"ids": canonical_baseline}},
            universe,
        )
        personal = personal_values(
            {"order": personal_order, "baseline": {"ids": canonical_baseline}}, universe
        )
        assert (
            zero["available"]
            and {to_trade_id(k): v for k, v in zero["values"].items()} == values
            and personal["available"]
        )
        context = {
            "mode": "custom",
            "revision": 1,
            "baseline_generation": FIXTURE_ID,
            "market_generation": FIXTURE_ID,
            "method": METHOD,
            "scope": [FIXTURE_ID, 1],
            "values": {to_trade_id(k): v for k, v in personal["values"].items()},
            "neutral_values": values,
        }
        custom = evaluate_trade_request(
            data,
            {
                "active_roster_id": 1,
                "partner_roster_id": 2,
                "assets_sent": ["harbor-q2"],
                "assets_received": ["summit-w1"],
                "strategy": "RETOOL",
                "_personal_context": context,
            },
            workspace=workspace,
            projection_reader=reader,
        )["evaluation"]
        for key in ["market_evidence", "lineup_impact", "multi_horizon_impact"]:
            assert custom[key] == evaluation[key], key
        assert (
            custom["dimensions"]["counterparty_plausibility"]
            == evaluation["dimensions"]["counterparty_plausibility"]
        )
        assert (
            custom["dimensions"]["strategic_fit"]["partner"]
            == evaluation["dimensions"]["strategic_fit"]["partner"]
        )
        assert (
            custom["personal_value_evidence"]["sent"]["total"]
            == personal["values"]["player:harbor-q2"]
        )
        assert (
            custom["personal_value_evidence"]["received"]["total"]
            == personal["values"]["player:summit-w1"]
        )

        def order_rows(ids, prices):
            return [
                {
                    "asset_id": "player:" + pid,
                    "trade_asset_id": pid,
                    "label": data["players"][pid]["full_name"],
                    "rank": ids.index("player:" + pid) + 1,
                    "value": prices["player:" + pid],
                }
                for pid in ["summit-w1", "harbor-q2"]
            ]

        package = evaluation["dimensions"]["package_quality"]

        def side(which, index):
            quality = package[which]["reserve_quality"]
            return {
                "name": data["teams"][index]["team_name"],
                "before": before[index].projected_points,
                "after": after[index].projected_points,
                "delta": after[index].projected_points - before[index].projected_points,
                "reserve_before": quality.get("pre_mean_weekly_points"),
                "reserve_after": (
                    quality.get("pre_mean_weekly_points")
                    + quality.get("mean_weekly_delta")
                )
                if quality.get("pre_mean_weekly_points") is not None
                and quality.get("mean_weekly_delta") is not None
                else None,
                "reserve_delta": quality.get("mean_weekly_delta"),
            }

        active, partner = side("active", 0), side("partner", 1)
        active.update(
            benefit="The incoming receiver improves the best legal starting lineup.",
            cost="Sending a starting quarterback uses the third quarterback as the Superflex starter; there is no further quarterback replacement in this example.",
        )
        partner.update(
            benefit="The incoming quarterback improves the best legal starting lineup.",
            cost="Summit gives up its highest-projected receiver and relies on its other receivers to cover WR and FLEX.",
        )
        export = {
            "version": 1,
            "fixture_id": FIXTURE_ID,
            "input_sha256": input_hash,
            "label": "Demonstration data · fictional league · not current player advice",
            "season": 2026,
            "week": 5,
            "league": {
                "name": data["league"]["name"],
                "scoring_label": "Full PPR · 4-point passing touchdowns · Superflex",
                "starter_slots": STARTERS,
                "scoring": SCORING,
            },
            "limitations": [
                "Real player names identify illustrative roster slots only. All prices, projected statistics, rosters and transactions are hypothetical; they are not actual player assessments.",
                "Frozen Week 5 example; supported changes are not promised results.",
                "No injury probabilities, playoff odds or multi-season forecast are inferred.",
                "Reserve points summarize useful disjoint legal replacements, not a second complete starting lineup.",
            ],
            "team": {
                "name": data["teams"][0]["team_name"],
                "strategy": "RETOOL",
                "lineup_points": before[0].projected_points,
                "comparison_population": len(data["teams"]),
                "comparison_rank": 1
                + sum(
                    lineup(t).projected_points > before[0].projected_points
                    for t in data["teams"]
                ),
                "lineup": [
                    {
                        "asset_id": e.asset_id,
                        "name": e.label,
                        "position": e.position,
                        "slot": e.slot,
                        "points": e.projected_points,
                    }
                    for e in before[0].entries
                ],
                "reserve": reserves,
                "strength": "Three projected quarterbacks provide meaningful Superflex replacement cover.",
                "limitation": "Using a reserve quarterback to improve receivers can remove that quarterback cover. Current points do not establish future availability.",
                "next_step": "Compare a receiver upgrade with its quarterback-depth cost before pursuing it.",
                "capital": [
                    {
                        "asset_id": "pick:2028:1:2",
                        "label": "2028 first · originally Summit Front Office",
                        "year": 2028,
                        "round": 1,
                        "original_franchise": "Summit Front Office",
                        "original_franchise_id": 2,
                        "current_owner": "Harbor Front Office",
                        "current_owner_id": 1,
                    }
                ],
            },
            "trade": {
                "send": [
                    {
                        "asset_id": sent["id"],
                        "name": sent["name"],
                        "position": sent["position"],
                    }
                ],
                "receive": [
                    {
                        "asset_id": received["id"],
                        "name": received["name"],
                        "position": received["position"],
                    }
                ],
                "market_sent": evaluation["values"]["sent"],
                "market_received": evaluation["values"]["received"],
                "active": active,
                "partner": partner,
                "recommendation": evaluation["recommendation"],
                "eligible": evaluation["generated_trade_eligible"],
                "qualification": "An evaluated hypothetical offer, not a prediction that another manager accepts. Both rosters are evaluated using the same neutral evidence.",
            },
            "personal": {
                "neutral_sent": values["harbor-q2"],
                "neutral_received": values["summit-w1"],
                "personal_sent": custom["personal_value_evidence"]["sent"]["total"],
                "personal_received": custom["personal_value_evidence"]["received"][
                    "total"
                ],
                "universe_asset_count": len(canonical_baseline),
                "cohort_label": "All compatible priced player assets in this fictional fixture. The owned future picks have no supplied Market quote and receive no personal price.",
                "unpriced_exact_picks": [
                    r["asset_id"]
                    for r in market.rows
                    if r["asset_type"] == "pick" and r["values"]["market_value"] is None
                ],
                "before_order": order_rows(canonical_baseline, zero["values"]),
                "after_order": order_rows(personal_order, personal["values"]),
                "explanation": "Move Justin Jefferson to first in the full example ranking. The saved-cohort Market value curve assigns that rank its existing highest value.",
                "unchanged": [
                    "Neutral Market prices",
                    "Both legal-lineup calculations",
                    "Opponent neutral valuation",
                ],
                "limitation": "This is a two-asset excerpt from the complete example order. Personal preference is not evidence of an opponent valuation or trade acceptance.",
            },
        }
        assert (
            evaluation["values"]["sent"] == values["harbor-q2"]
            and evaluation["values"]["received"] == values["summit-w1"]
        ), (evaluation["values"], values, evaluation["reason_codes"])
        assert evaluation["legal"] and evaluation["generated_trade_eligible"]
        assert evaluation["recommendation"] == "WORTH PURSUING"
        return export


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("src/ui/public_demo_data.json")
    )
    args = parser.parse_args()
    result = generate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
                "trade": result["trade"],
                "personal": result["personal"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
