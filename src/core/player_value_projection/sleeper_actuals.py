"""Pure, bounded interpretation of retained Sleeper league matchup results.

No scoring reconstruction, provider IO, current-roster inference or game-count
inference. The owning league publication supplies identity and retrieval clocks.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

METHOD = "sleeper-matchup-actuals-v1"
SOURCE = "Sleeper league matchup results"


def score_number(value: Any) -> float | None:
    # JSON numbers only: booleans, strings, nulls and non-finite values are not scores.
    return (
        float(value) if type(value) in (int, float) and math.isfinite(value) else None
    )


def actual_display(value: Any) -> str:
    """Sleeper web Number.toFixed(2) presentation; never an arithmetic input."""
    score = score_number(value)
    if score is None:
        return "Unavailable"
    if score == 0:
        return "0.00"
    # Preserve the binary64 boundary, as in the existing Sleeper projection
    # display contract; Decimal(str(score)) would change midpoint behavior.
    from decimal import localcontext

    with localcontext() as context:
        context.prec = 340
        return format(
            Decimal.from_float(score).quantize(Decimal(".01"), rounding=ROUND_HALF_UP),
            ".2f",
        )


def scoring_identity(settings: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            settings, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def resolve_score(row: dict, player_id: str) -> dict:
    """Resolve a player map and correctly indexed starter score without precedence.

    An explicit map key proves source coverage even if the player's roster role
    is absent. No score is inferred for another current roster member.
    """
    pid = str(player_id)
    if not pid or pid == "0":
        return {"points": None, "reason": "placeholder_player", "sources": []}
    starters = [str(p) for p in row.get("starters") or []]
    mapped = row.get("players_points") or {}
    ordered = row.get("starters_points") or []
    values, sources, invalid = [], [], []
    if pid in mapped:
        value = score_number(mapped[pid])
        if value is None:
            invalid.append("players_points")
        else:
            values.append(value)
            sources.append("players_points")
    indices = [i for i, item in enumerate(starters) if item == pid]
    if len(indices) > 1:
        return {
            "points": None,
            "reason": "duplicate_starter_identity",
            "sources": sources,
        }
    if indices and indices[0] < len(ordered):
        value = score_number(ordered[indices[0]])
        if value is None:
            invalid.append("starters_points")
        else:
            values.append(value)
            sources.append("starters_points")
    if len({Decimal(str(v)) for v in values}) > 1:
        return {
            "points": None,
            "reason": "conflicting_sleeper_scores",
            "sources": sources,
        }
    return {
        "points": values[0] if values else None,
        "reason": ("invalid_alternate_score" if invalid else None)
        if values
        else "invalid_sleeper_score"
        if invalid
        else "score_not_observed",
        "sources": sources,
    }


def prepare_actual_results(data: dict, *, expected_league_id: str) -> dict:
    """Interpret at most 18 retained weeks, once per publication/restoration.

    Old caches without scoring provenance remain unverified. Calendar completion
    comes from Sleeper's last-scored leg, never from a nonzero score or wall clock.
    """
    league = data.get("league") or {}
    lid, season = str(league.get("league_id") or ""), str(league.get("season") or "")
    if lid != str(expected_league_id) or not lid:
        raise ValueError("Sleeper actual results require the selected league.")
    settings = data.get("scoring_settings") or league.get("scoring_settings") or {}
    fingerprint = scoring_identity(settings)
    prepared = data.get("season_matchups") or {}
    result = {
        "method_version": METHOD,
        "source": SOURCE,
        "league_id": lid,
        "season": season,
        "scoring_fingerprint": fingerprint,
        "source_generation": prepared.get("semantic_generation"),
        "retrieved_at": prepared.get("observed_at"),
        "players": {},
        "periods": {},
        "availability": "unavailable",
        "reason": None,
        "scoring_provenance": "explicit_publication_fingerprint",
    }
    if (
        not season.isdigit()
        or not settings
        or prepared.get("methodology") != "matchup-season-presentation-v1"
        or str(prepared.get("league_id") or "") != lid
        or str(prepared.get("season") or "") != season
    ):
        result["reason"] = "compatible_sleeper_matchup_publication_unavailable"
    elif prepared.get("scoring_fingerprint") != fingerprint:
        # Legacy atomic runtime caches retained native Sleeper matchup rows
        # alongside the exact league settings/calendar. Reinterpret those rows,
        # never old NFLverse calculated totals. Missing context stays unknown.
        from src.core.intelligence.season_calendar import season_calendar

        legacy_atomic = (
            prepared.get("scoring_fingerprint") is None
            and bool(league.get("scoring_settings"))
            and league["scoring_settings"] == settings
            and prepared.get("calendar_reference")
            == season_calendar(league)["reference"]
            and bool(prepared.get("observed_at"))
            and bool(prepared.get("semantic_generation"))
        )
        if legacy_atomic:
            result["scoring_provenance"] = "retained_atomic_league_context"
        else:
            result["reason"] = "sleeper_scoring_provenance_unverified"
    if not result["reason"] and len(prepared.get("weeks") or {}) > 18:
        result["reason"] = "unsupported_week_population"
    if not result["reason"]:
        completed = (league.get("settings") or {}).get("last_scored_leg")
        completed = (
            completed if type(completed) is int and 0 <= completed <= 18 else None
        )
        start = (league.get("settings") or {}).get("start_week")
        playoff_start = (league.get("settings") or {}).get("playoff_week_start")
        result["completed_through_week"] = completed
        for key, week in sorted(
            (prepared.get("weeks") or {}).items(),
            key=lambda item: str(item[0]).zfill(2),
        ):
            if not str(key).isdigit() or not 1 <= int(key) <= 18:
                continue
            w = int(key)
            phase = (
                ("postseason" if w >= playoff_start else "regular")
                if type(playoff_start) is int
                else "unknown"
            )
            state = (
                "completed"
                if completed is not None and w <= completed
                else "provisional"
                if completed is not None
                else "unknown"
            )
            # Future Sleeper rows can be zero-filled placeholders. They cannot
            # enter actual windows before the selected league reaches that week.
            current = data.get("week")
            if type(current) is int and w > current:
                state = "future"
            if type(start) is int and w < start:
                state = "outside_league_season"
            result["periods"][str(w)] = {
                "availability": week.get("availability"),
                "reason": week.get("reason"),
                "state": state,
                "scope": phase,
                "retrieved_at": week.get("observed_at"),
                "last_attempt_at": week.get("last_attempt_at"),
                "freshness": week.get("freshness", "retained"),
            }
            if (
                week.get("availability") != "available"
                and not week.get("retained_rows")
            ) or state in {"future", "outside_league_season"}:
                continue
            observations: dict[str, list[dict]] = {}
            rows = (
                week.get("rows")
                if week.get("availability") == "available"
                else week.get("retained_rows")
            )
            rows = rows or []
            if len(rows) > 64:
                result["periods"][str(w)].update(
                    availability="unavailable", reason="unsupported_roster_population"
                )
                continue
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or type(row.get("roster_id")) is not int
                    or any(
                        row.get(k) is not None and not isinstance(row[k], list)
                        for k in ("players", "starters", "starters_points")
                    )
                    or row.get("players_points") is not None
                    and not isinstance(row["players_points"], dict)
                ):
                    result["periods"][str(w)].update(
                        availability="unavailable",
                        reason="invalid_retained_matchup_row",
                    )
                    observations = {}
                    break
                players = (
                    set(map(str, row.get("players") or []))
                    | set(map(str, row.get("starters") or []))
                    | set(map(str, row.get("players_points") or {}))
                )
                if len(players) > 256:
                    result["periods"][str(w)].update(
                        availability="unavailable",
                        reason="unsupported_player_population",
                    )
                    observations = {}
                    break
                for pid in sorted(players - {"0", ""}):
                    observations.setdefault(pid, []).append(resolve_score(row, pid))
            for pid, candidates in observations.items():
                observed = [v["points"] for v in candidates if v["points"] is not None]
                conflict = (
                    any(
                        v["reason"]
                        in {"conflicting_sleeper_scores", "duplicate_starter_identity"}
                        for v in candidates
                    )
                    or len({Decimal(str(v)) for v in observed}) > 1
                )
                points = None if conflict else observed[0] if observed else None
                reasons = sorted({v["reason"] for v in candidates if v["reason"]})
                if conflict:
                    reasons.append("conflicting_sleeper_scores")
                entry = {
                    "week": w,
                    "season": int(season),
                    "points": points,
                    "state": state,
                    "scope": phase,
                    "reasons": sorted(set(reasons)),
                    "sources": sorted({s for v in candidates for s in v["sources"]}),
                    "retrieved_at": week.get("observed_at"),
                    "freshness": week.get("freshness", "retained"),
                    "corrected": pid in (week.get("corrected_players") or []),
                }
                result["players"].setdefault(pid, []).append(entry)
        result["availability"] = "cached"
    result["generation"] = hashlib.sha256(
        json.dumps(
            result, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return result


def player_context(snapshot: dict, player_id: str):
    from .models import DataStatus, ProductionContext, ProductionWindow

    rows = (snapshot.get("players") or {}).get(str(player_id)) or []
    completed = [row for row in rows if row["state"] == "completed"]
    windows = []
    groups = [
        (label, completed[-size:])
        for label, size in (
            ("Last Observation", 1),
            ("Last 3 Observations", 3),
            ("Last 5 Observations", 5),
        )
    ]
    groups += [("Season Average", completed), ("Previous Season Average", [])]
    for label, sample in groups:
        values = [row["points"] for row in sample]
        exact = bool(values) and all(v is not None for v in values)
        total = (
            float(sum((Decimal(str(v)) for v in values), Decimal(0))) if exact else None
        )
        windows.append(
            ProductionWindow(
                label,
                total / len(values) if exact else None,
                None,
                None,
                None,
                None,
                None,
                season=int(snapshot["season"])
                if label != "Previous Season Average"
                and str(snapshot.get("season")).isdigit()
                else None,
                observation_count=len(sample),
                scored_count=sum(v is not None for v in values),
                weeks=tuple(row["week"] for row in sample),
                missing_components=tuple(
                    sorted({r for row in sample for r in row["reasons"]})
                ),
                observed_total=total,
            )
        )
    notes = [
        "Averages and totals describe retained completed-week score observations, not games played or full-season acquisition.",
        "An explicit zero does not prove participation. Byes, DNPs, absent matchup records and taxi/IR membership do not supply scores.",
        "Live or unconfirmed weeks are separate from completed-week windows. Team custom-point adjustments are never allocated to players.",
        "Previous-season results require their own admitted Sleeper league-season publication; another season is never substituted.",
    ]
    if snapshot.get("reason"):
        notes.append(
            {
                "compatible_sleeper_matchup_publication_unavailable": "A compatible Sleeper league-season matchup publication is not prepared.",
                "sleeper_scoring_provenance_unverified": "The retained matchup rows cannot be tied to the selected league scoring context.",
            }.get(
                snapshot["reason"],
                "The retained Sleeper publication exceeds supported evidence bounds.",
            )
        )
    if snapshot.get("scoring_provenance") == "retained_atomic_league_context":
        notes.append(
            "Sleeper scores were recovered from native matchup rows in the same retained league cache and calendar, not recalculated or newly verified against Sleeper."
        )
    if any(row["freshness"] != "current" for row in rows):
        notes.append(
            "Some scores are retained observations, not newly revalidated results; review each week’s retrieval time."
        )
    if any(row["points"] is None for row in completed):
        notes.append(
            "Missing or contradictory Sleeper scores withhold the dependent window; supported other windows remain available."
        )
    return ProductionContext(
        tuple(windows),
        None,
        None,
        "Unavailable",
        SOURCE,
        DataStatus.CACHED
        if any(w.fantasy_points is not None for w in windows)
        else DataStatus.UNAVAILABLE,
        snapshot.get("retrieved_at"),
        tuple(notes),
        authority=METHOD,
        source_generation=snapshot.get("source_generation"),
        league_id=snapshot.get("league_id"),
        scoring_fingerprint=snapshot.get("scoring_fingerprint"),
        observations=tuple(rows),
        periods=snapshot.get("periods") or {},
    )
