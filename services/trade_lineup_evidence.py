"""Pure admission of completed lineup comparisons, never projection or solving.

A failed window does not invalidate independent weeks. Validation compares the
recorded values/identities; it never fills a missing delta or changes a price.
"""

from decimal import Decimal
from math import isclose, isfinite


def number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def same_number(left, right):
    return (
        number(left) and number(right) and isclose(left, right, rel_tol=0, abs_tol=1e-8)
    )


def total(values):
    return float(sum((Decimal(str(v)) for v in values), Decimal(0)))


def completed_lineup_evidence(result, side="active"):
    inputs = (result.get("provenance") or {}).get("inputs") or {}
    projection = inputs.get("projection_evidence") or {}
    impact = result.get("multi_horizon_impact") or {}
    strategies = (result.get("dimensions") or {}).get("strategic_fit") or {}
    strategy = strategies.get(side) or {}
    diagnostic = (
        ((result.get("dimensions") or {}).get("roster_diagnostics") or {}).get("sides")
        or {}
    ).get(side) or {}
    snapshots = projection.get("horizon_snapshot_ids") or {}
    required = ("league_id", "season", "week", "scoring_profile_id", "generation")
    missing = any(projection.get(key) in (None, "") for key in required)
    missing |= (
        not inputs.get("projection_generation")
        or not impact.get("projection_generation")
        or not impact.get("league_id")
    )
    pairs = [
        (inputs.get("league_id"), projection.get("league_id")),
        (inputs.get("league_id"), impact.get("league_id")),
        (inputs.get("projection_generation"), projection.get("generation")),
        (projection.get("generation"), impact.get("projection_generation")),
    ]
    # New producers repeat the pinned context explicitly; old completed views
    # remain bound through their generation and per-week snapshot references.
    pairs += [
        (projection.get(key), impact.get(key))
        for key in ("season", "scoring_profile_id")
        if impact.get(key) is not None
    ]
    if impact.get("current_week") is not None:
        pairs.append((projection.get("week"), impact["current_week"]))
    conflict = any(
        a is not None and b is not None and str(a) != str(b) for a, b in pairs
    )
    identity_state = (
        "incompatible" if conflict else "unavailable" if missing else "compatible"
    )
    common = {
        "season": projection.get("season"),
        "league_id": inputs.get("league_id"),
        "scoring_profile_id": projection.get("scoring_profile_id"),
        "projection_generation": inputs.get("projection_generation"),
    }
    numeric_state = diagnostic.get("numeric_impact_state") or "unavailable"
    weekly = {}
    for key, row in (
        ((impact.get("sides") or {}).get(side) or {}).get("weekly") or {}
    ).items():
        try:
            week = int(key)
        except (TypeError, ValueError):
            continue
        # Current-week rows use the enriched published root snapshot; future
        # weeks use the pinned horizon manifest's individual snapshot handles.
        expected = (
            projection.get("projection_snapshot_id")
            if week == projection.get("week")
            else snapshots.get(str(week))
        )
        phases = {}
        conditional = numeric_state != "supported"
        for phase in ("pre", "post"):
            observed = row.get(phase) or {}
            points = (observed.get("optimal") or {}).get("projected_points")
            reference = observed.get("projection_snapshot_id")
            qualification = (observed.get("reserve_capacity") or {}).get(
                "qualification"
            ) or {}
            phase_conflict = any(
                observed.get(k) is not None and str(observed[k]) != str(v)
                for k, v in (
                    ("week", week),
                    ("season", projection.get("season")),
                    ("scoring_profile_id", projection.get("scoring_profile_id")),
                )
            )
            phase_conflict |= bool(
                qualification.get("scoring_profile_id") is not None
                and qualification["scoring_profile_id"]
                != projection.get("scoring_profile_id")
            )
            valid = (
                identity_state == "compatible"
                and bool(expected)
                and reference == expected
                and observed.get("available") is True
                and number(points)
                and not phase_conflict
            )
            phases[phase] = points if valid else None
            conditional |= qualification.get("conclusion_state") != "current"
        delta = row.get("delta")
        valid_delta = (
            phases["pre"] is not None
            and phases["post"] is not None
            and same_number(delta, total([phases["post"], -phases["pre"]]))
        )
        weekly[week] = {
            **common,
            "week": week,
            **phases,
            "delta": delta if valid_delta else None,
            "state": "incompatible"
            if conflict
            else "unavailable"
            if not valid_delta
            else "provisional"
            if conditional
            else "supported",
        }
    horizons = {}
    for name, row in (strategy.get("horizons") or {}).items():
        requested = row.get("weeks_requested") or []
        valid_weeks = (
            bool(requested)
            and all(type(w) is int for w in requested)
            and len(set(requested)) == len(requested)
        )
        if name == "current_week":
            valid_weeks &= requested == [projection.get("week")]
        complete = (
            valid_weeks
            and row.get("availability") == "complete"
            and set(row.get("pre_supported_weeks") or []) == set(requested)
            and set(row.get("post_supported_weeks") or []) == set(requested)
            and all((weekly.get(w) or {}).get("delta") is not None for w in requested)
        )
        delta = row.get("delta")
        if complete:
            complete = (
                same_number(
                    row.get("pre_total"), total([weekly[w]["pre"] for w in requested])
                )
                and same_number(
                    row.get("post_total"), total([weekly[w]["post"] for w in requested])
                )
                and same_number(delta, total([weekly[w]["delta"] for w in requested]))
            )
        comparable = row.get("comparable_weeks") or []
        supported = (
            [w for w in requested if (weekly.get(w) or {}).get("delta") is not None]
            if valid_weeks
            else []
        )
        subtotal = row.get("supported_week_delta_subtotal")
        subtotal_valid = (
            bool(supported)
            and comparable == supported
            and same_number(subtotal, total([weekly[w]["delta"] for w in supported]))
        )
        horizons[name] = {
            **common,
            "delta": delta if complete else None,
            "state": "incompatible"
            if conflict
            else "unavailable"
            if not complete
            else "provisional"
            if any(weekly[w]["state"] != "supported" for w in requested)
            else "supported",
            "weeks": requested,
            "coverage": row.get("availability"),
            "availability_state": numeric_state,
            "subtotal": subtotal if subtotal_valid else None,
            "comparable_weeks": supported if subtotal_valid else [],
        }
    production = strategy.get("production_evidence") or {}
    counted = production.get("weeks_counted_once") or []
    mean = production.get("mean_weekly_delta")
    valid_mean = (
        bool(counted)
        and len(set(counted)) == len(counted)
        and all((weekly.get(w) or {}).get("delta") is not None for w in counted)
    )
    if valid_mean:
        valid_mean = same_number(
            mean, total([weekly[w]["delta"] for w in counted]) / len(counted)
        )
    invalid = any(
        row.get("delta") is not None and horizons[name]["delta"] is None
        for name, row in (strategy.get("horizons") or {}).items()
    )
    invalid |= any(
        row.get("delta") is not None
        and (weekly.get(int(week)) or {}).get("delta") is None
        for week, row in (
            ((impact.get("sides") or {}).get(side) or {}).get("weekly") or {}
        ).items()
        if str(week).isdigit()
    )
    invalid |= mean is not None and not valid_mean
    return {
        "identity_state": identity_state,
        "invalid_comparison": bool(invalid),
        "weekly": weekly,
        "horizons": horizons,
        "mean_weekly_delta": mean if valid_mean else None,
        "weeks_counted_once": counted if valid_mean else [],
    }
