"""Read-only current calibration panel from approved public source data.

Not a production backfill or historical decision-time evaluation. No credentials,
league facts, private data, durable writes, or player-specific model overrides.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from collections import defaultdict
from dataclasses import asdict
from datetime import date
import json
import io
import logging
from statistics import mean, quantiles
from pathlib import Path

import httpx

from services.player_evidence import REFERENCE_SCORING_SETTINGS
from src.core.data_platform.global_production import GlobalProduction
from src.core.data_platform.identity_crosswalk import CROSSWALK_URL, crosswalk_resolver
from src.core.historical_memory.providers import NflverseProvider
from src.core.valuation.player_methodology import ReferenceSeason, assess_intrinsic


async def audit(season: int, as_of: date) -> dict:
    if season != as_of.year - 1:
        raise ValueError("This audit uses the immediately prior completed season for a CURRENT model assessment.")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    async with httpx.AsyncClient(follow_redirects=True, timeout=45) as client:
        response = await client.get("https://api.sleeper.app/v1/players/nfl")
        response.raise_for_status()
        catalog = response.json()
        response = await client.get(CROSSWALK_URL)
        response.raise_for_status()
        resolver, identity_report = crosswalk_resolver(catalog, csv.DictReader(io.StringIO(response.text)))
        grouped = defaultdict(list)
        unresolved = records = 0
        async def batches():
            for source_season in range(as_of.year - 7, season + 1):
                async for batch in NflverseProvider(client).weekly_batches(source_season, 1000):
                    yield batch
        async for batch in batches():
            for row in batch:
                if row["season_type"] != "REG" or row["position"] not in {"QB", "RB", "WR", "TE"}:
                    continue
                records += 1
                match = resolver.resolve(str(row["provider_player_id"]), "GSIS")
                if match is None:
                    unresolved += 1
                    continue
                player_id = match.dtos_id
                grouped[player_id].append(row)
    results = []
    for player_id, rows in grouped.items():
        player = catalog[player_id]
        position = player.get("position")
        if position not in {"QB", "RB", "WR", "TE"}:
            continue
        scored = [GlobalProduction.score_game(row["raw_stats"], REFERENCE_SCORING_SETTINGS)["fantasy_points"] for row in rows]
        ppg = mean(scored) if all(value is not None for value in scored) else None
        usage_values = []
        for row in rows:
            raw = row["raw_stats"]
            if position == "RB":
                usage_values.append(raw["rush_att"] + raw["rec_tgt"] if raw["rush_att"] is not None and raw["rec_tgt"] is not None else None)
            else:
                usage_values.append(raw["rec_tgt"] if position in {"WR", "TE"} else None)
        birth = player.get("birth_date")
        age = (as_of - date.fromisoformat(birth)).days / 365.2425 if birth else None
        summaries = []
        for year in sorted({row['season'] for row in rows}):
            selected = [index for index, row in enumerate(rows) if row['season'] == year]
            points = [scored[index] for index in selected]
            uses = [usage_values[index] for index in selected]
            summaries.append(ReferenceSeason(year, len(selected),
                mean(points) if all(value is not None for value in points) else None,
                mean(uses) if all(value is not None for value in uses) else None))
        result = assess_intrinsic(position=position, age=age, current_season=as_of.year, seasons=tuple(summaries))
        results.append({"player_id": player_id, "name": player.get("full_name"), "position": position,
            "catalog_active": player.get('active'), "catalog_status": player.get('status'),
            "nfl_team": player.get('team'),
            "age": round(age, 2) if age is not None else None, "games": len(rows),
            "model_age": age,
            "reference_ppg": round(ppg, 3) if ppg is not None else None,
            "season_summaries": [asdict(row) for row in summaries], "assessment": asdict(result)})
    scored_results = sorted((row for row in results if row["assessment"]["value"] is not None),
        key=lambda row: (-row["assessment"]["value"], row["player_id"]))
    counts = defaultdict(int)
    for overall, row in enumerate(scored_results, 1):
        counts[row["position"]] += 1
        row.update(overall_rank=overall, positional_rank=counts[row["position"]])
    panel = {"Jayden Daniels", "Jalen Hurts", "Joe Burrow", "Derrick Henry", "Justin Jefferson",
             "Ja'Marr Chase", "Brock Bowers", "Travis Kelce", "Ashton Jeanty", "Omarion Hampton"}
    distributions = {}
    for position in ("QB", "RB", "WR", "TE"):
        values = [row["assessment"]["value"] for row in scored_results if row["position"] == position]
        distributions[position] = {"count": len(values), "minimum": min(values) if values else None,
            "quartiles": quantiles(values, n=4) if len(values) > 1 else [], "maximum": max(values) if values else None,
            "top": [row for row in scored_results if row["position"] == position][:5]}
    return {"status": "candidate_audit_not_production_acceptance", "as_of": as_of.isoformat(),
        "rank_scope": "matched scored historical cohort; not current active dynasty universe",
        "production_seasons": list(range(as_of.year - 7, season + 1)), "sources": ["https://api.sleeper.app/v1/players/nfl", CROSSWALK_URL,
            *[NflverseProvider.url_template.format(season=year) for year in range(as_of.year - 7, season + 1)]],
        "identity_report": identity_report,
        "source_license": NflverseProvider.license, "production_records": records,
        "unresolved_or_ambiguous_records": unresolved,
        "scored_players": len(scored_results), "distributions": distributions,
        "panel": [row for row in results if row["name"] in panel],
        "panel_unmatched": sorted(panel - {row["name"] for row in results}),
        "cohort": results,
        "limitations": ["Current metadata and seven completed regular seasons; not historical knowledge-at-the-time proof.",
            "Candidate intrinsic ranks are not deployed DTOS ranks or Market prices.",
            "Players without matching scored NFL evidence have no intrinsic ranking in this audit."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        root = Path(__file__).resolve().parents[2] / '.validation'
        destination = args.output.resolve()
        if not destination.is_relative_to(root.resolve()) or destination.suffix != '.json':
            parser.error('Diagnostic output must be JSON inside repository .validation.')
    result = asyncio.run(audit(args.season, args.as_of))
    if args.output:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, sort_keys=True), encoding='utf-8')
        print(json.dumps({key: result[key] for key in ('status', 'production_seasons', 'scored_players', 'unresolved_or_ambiguous_records')}))
    else:
        print(json.dumps(result, sort_keys=True))
