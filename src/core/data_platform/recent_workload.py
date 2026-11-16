"""Bounded observed-game workload comparisons; never fantasy scoring or prediction."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict

from .global_evidence import utc
from .global_schedule import schedule_from_facts

METHOD = "observed-workload-3-vs-3-v1"


def recent_workload(
    facts: list[dict],
    *,
    season: int,
    as_of: str,
    through_week: int | None,
    schedule: list[dict] | None = None,
) -> dict:
    """Caller supplies the admitted NFL completed-week boundary, not a wall-clock guess.

    Require the latest six REG observations, never the latest six non-null/positive
    statistics. Missing periods within that span or after it block comparison,
    unless a complete retained schedule establishes a bye. Older missing periods
    are outside the selected sample, not represented as complete season coverage.
    """
    boundary = utc(as_of)
    groups = defaultdict(list)
    reasons = []
    result = dict(
        method=METHOD,
        season=season,
        game_type="REG",
        as_of=boundary,
        completed_week_boundary=through_week,
        sample_basis="observed games, not complete season coverage",
        source="nflverse player statistics",
        status="unavailable",
        reasons=reasons,
        metrics={},
        previous=[],
        recent=[],
        qualifications=[],
        provider_calls=0,
    )
    for fact in facts:
        if fact.get("season") != season or fact.get("provider") != "nflverse":
            continue
        if (
            utc(fact["effective_at"]) > boundary
            or utc(fact["knowledge_boundary"]) > boundary
        ):
            continue
        values = fact["values"]
        week = fact.get("week")
        if type(week) is not int or week < 1:
            reasons.append("game_week_unknown")
            continue
        if through_week is not None and week > through_week:
            continue
        if values.get("season_type") != "REG":
            if values.get("season_type") is None:
                reasons.append("game_type_unknown")
            continue
        game = values.get("game_id")
        if not game or not values.get("team"):
            reasons.append("game_identity_unknown")
            continue
        groups[str(game)].append(fact)

    games = []
    for game_id, rows in groups.items():
        identities = {
            (
                r["week"],
                utc(r["effective_at"]),
                r["values"].get("team"),
                r["values"].get("opponent"),
            )
            for r in rows
        }
        conflict = len(identities) != 1 or any(r.get("revision_conflict") for r in rows)
        row = rows[0]
        game = dict(
            game_id=game_id,
            week=row["week"],
            date=utc(row["effective_at"]),
            team=row["values"].get("team"),
            opponent=row["values"].get("opponent"),
            knowledge_boundaries=sorted({utc(r["knowledge_boundary"]) for r in rows}),
            fingerprints=sorted({r["fingerprint"] for r in rows}),
            conflicts=[],
        )
        for label, field in (("targets", "rec_tgt"), ("carries", "rush_att")):
            values = [r["values"].get(field) for r in rows]
            valid = all(
                type(v) in (int, float) and math.isfinite(v) and v >= 0 and v == int(v)
                for v in values
            )
            if conflict or (valid and len(set(values)) != 1):
                game[label] = None
                game["conflicts"].append(label)
            else:
                game[label] = values[0] if valid else None
        games.append(game)
    games.sort(key=lambda r: (r["date"], r["game_id"]))
    result["eligible_observations"] = len(games)
    if type(through_week) is not int or through_week < 0:
        reasons.append("completed_week_boundary_unknown")
    if len(games) < 6:
        reasons.append("six_observations_not_available")
    selected = games[-6:]
    if selected:
        weeks = [r["week"] for r in selected]
        if len(set(weeks)) != len(weeks) or weeks != sorted(weeks):
            reasons.append("game_order_or_identity_conflict")
        if through_week is not None:
            missing = set(range(min(weeks), through_week + 1)) - set(weeks)
            byes = {}
            for week in missing:
                # At a transfer boundary, both adjacent observed teams must have
                # a proven bye; do not invent which team employed an absent player.
                before = next((g for g in reversed(selected) if g["week"] < week), None)
                after = next((g for g in selected if g["week"] > week), None)
                teams = {g["team"] for g in (before, after) if g}
                for team in teams:
                    if team not in byes:
                        byes[team] = schedule_from_facts(
                            schedule or [], team, season=season, as_of=boundary
                        )["bye_week"]
                if not teams or any(byes[team] != week for team in teams):
                    result.setdefault("unobserved_weeks", []).append(week)
            if result.get("unobserved_weeks"):
                reasons.append("game_observations_missing")
        if len({g["team"] for g in selected}) > 1:
            result["qualifications"].append("teams_changed")
    if not reasons:
        previous, recent = selected[:3], selected[3:]
        result.update(previous=previous, recent=recent)
        for metric in ("targets", "carries"):
            metric_reasons = []
            if any(metric in g["conflicts"] for g in selected):
                metric_reasons.append("conflicting_stat_records")
            elif any(g[metric] is None for g in selected):
                metric_reasons.append("stat_fields_missing")
            if metric_reasons:
                result["metrics"][metric] = dict(
                    status="unavailable", reasons=metric_reasons
                )
            else:
                earlier = sum(int(g[metric]) for g in previous) / 3
                latest = sum(int(g[metric]) for g in recent) / 3
                result["metrics"][metric] = dict(
                    status="supported",
                    previous_average=earlier,
                    recent_average=latest,
                    difference=latest - earlier,
                    previous_count=3,
                    recent_count=3,
                )
        supported = sum(m["status"] == "supported" for m in result["metrics"].values())
        result["status"] = (
            "supported" if supported == 2 else "partial" if supported else "unavailable"
        )
    result["reasons"] = sorted(set(reasons))
    result["generation"] = hashlib.sha256(
        json.dumps(
            [
                METHOD,
                season,
                through_week,
                games,
                result["reasons"],
                sorted(r["fingerprint"] for r in schedule or []),
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return result
