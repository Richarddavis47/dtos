"""Disposable league-relative roster facts from canonical legal lineups.

Current-week evidence, not a player value/projection or acceptance model.
Every add/remove is a complete legal assignment; effects must never be summed.
"""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from statistics import median

from src.core.trade_intelligence.lineup import BENCH_SLOTS, FLEX_ELIGIBILITY, _eligible, eligible_positions
from src.core.trade_intelligence.lineup_memo import LineupStore, SearchLineupMemo
from src.core.trade_intelligence.capital_assessment import resolve_strategy

POSITIONS = ("QB", "RB", "WR", "TE")
METHOD = "legal-roster-diagnostics-v3-source-eligibility"
diagnostic_store = LineupStore(max_entries=12, max_bytes=2_097_152, ttl=180)


def _now():
    return datetime.now(timezone.utc)


def _projection_service(data):
    from src.platform.league_context import current_league_context
    from src.core.projection_intelligence import projection_service

    runtime = current_league_context()
    lid = str((data.get("league") or {}).get("league_id") or "")
    return (
        runtime.projection
        if runtime and runtime.league_id == lid
        else projection_service
    )


def diagnostic_qualification(diagnostic):
    """Concise shared wording for consumers of admitted numerical scenarios."""
    evidence = (diagnostic or {}).get("evidence") or {}
    state = evidence.get("conclusion_state")
    if state == "current" or not state:
        return ""
    freshness = ", ".join(evidence.get("projection_freshness") or [])
    return (
        (
            "Provisional roster diagnostics"
            if state == "provisional"
            else "Roster diagnostics unavailable"
        )
        + (" · projection evidence " + freshness if freshness else "")
        + ". Review source, scoring and availability limitations."
    )


def _number(value):
    return (
        float(value)
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        else None
    )


def _bounded(slots, pools):
    """Shared admission before any main or package solver expansion."""
    return (
        sum(map(len, pools.values())) <= 2048
        and sum(slot not in BENCH_SLOTS for slot in slots) <= 14
    )


def _qualification(data, snapshot, slots, *, projection_reader=None):
    from src.core.projection_intelligence.scoring import STAT_KEYS
    from src.core.projection_intelligence.sleeper_provider import freshness_state

    league = data.get("league") or {}
    scoring = data.get("scoring_settings")
    if scoring is None:
        scoring = league.get("scoring_settings")
    valid = bool(
        isinstance(scoring, dict)
        and scoring
        and any(k in STAT_KEYS for k in scoring)
        and all(_number(v) is not None for v in scoring.values())
    )
    supported_slots = bool(slots) and all(
        slot in BENCH_SLOTS or slot in POSITIONS or slot in FLEX_ELIGIBILITY
        for slot in slots
    )
    rows = (snapshot or {}).get("players") or {}
    now = _now()
    states = sorted(
        {freshness_state(row.get("source_timestamp"), now=now) for row in rows.values()}
    )
    # Explicit retained/fallback qualifications remain material independently of
    # age. A stored Fresh label cannot establish an absent source observation.
    publication_states = sorted(
        {
            str(
                row.get("source_freshness")
                or row.get("sleeper_freshness")
                or "Unavailable"
            )
            for row in rows.values()
        }
    )
    states = sorted(
        set(states) | (set(publication_states) - {"Fresh", "Aging", "Unavailable"})
    )
    reader = projection_reader or _projection_service(data)
    reader = getattr(reader, "service", reader)
    refresh = (
        reader.refresh_evidence(snapshot) if hasattr(reader, "refresh_evidence") else {}
    )
    if not isinstance(refresh, dict):
        refresh = {}
    from src.core.projection_intelligence.service import projection_row_compatible
    mixed = any(not projection_row_compatible(snapshot, pid, row)
                for pid, row in rows.items()) if snapshot else False
    limitations = []
    if not valid:
        limitations.append(
            "Unavailable — insufficient supported scoring evidence; missing scoring is not zero."
        )
    if not supported_slots:
        limitations.append(
            "Unsupported or missing starting-lineup slots; no numeric diagnostic conclusion."
        )
    if mixed:
        limitations.append(
            "Mixed projection generations; no compatible diagnostic conclusion."
        )
    retained = any(state != "Fresh" for state in states) or not states
    if retained:
        limitations.append(
            "Projection evidence is "
            + ", ".join(states or ["Unavailable"])
            + "; retained numerical evidence is provisional, not freshly verified."
        )
    if refresh.get("retained_publication"):
        limitations.append(
            "Using retained projection evidence; latest refresh did not complete."
        )
    return {
        "scoring": "supported" if valid else "unavailable / incomplete",
        "calculation_supported": valid and supported_slots and not mixed,
        "projection_freshness": states,
        "retained": retained,
        "refresh": refresh,
        "source_observations": sorted(
            {str(row.get("source_timestamp") or "Unavailable") for row in rows.values()}
        ),
        "conclusion_state": "unavailable"
        if not valid or not supported_slots or mixed
        else "provisional"
        if retained or refresh.get("retained_publication")
        else "current",
        "limitations": limitations,
    }


def projection_snapshot(data):
    return _projection_service(data).snapshot()


def diagnostic_inputs(data, snapshot):
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or "")
    week = data.get("week") or 1
    slots = tuple(
        str(slot).upper()
        for slot in (
            data.get("roster_positions") or league.get("roster_positions") or ()
        )
    )
    scoring = data.get("scoring_settings") or league.get("scoring_settings")
    qualification = _qualification(data, snapshot, slots)
    admitted = bool(
        snapshot
        and snapshot.get("projection_snapshot_id")
        and str(snapshot.get("league_id")) == league_id
        and snapshot.get("week") == week
        and (
            league.get("season") is None
            or str(snapshot.get("season")) == str(league["season"])
        )
        and qualification["calculation_supported"]
        and snapshot.get("scoring_settings") == scoring
    )
    rows = (snapshot or {}).get("players") or {}
    pools, excluded, uncertain, eligibility = {}, {}, {}, {}
    from .team_strength import compatible_profile
    profile = compatible_profile(data, snapshot) if admitted else None
    database = data.get("players") or {}
    if not isinstance(database, dict):
        database = {
            str(p.get("id") or p.get("player_id")): p
            for p in database
            if isinstance(p, dict)
        }
    owned = set()
    for team in data.get("teams") or []:
        rid = str(team.get("roster_id"))
        if rid in pools:
            raise ValueError("Duplicate diagnostic franchise identity")
        pools[rid], excluded[rid], uncertain[rid] = [], [], []
        eligibility[rid] = []
        current = ((profile or {}).get('teams', {}).get(rid, {}).get('weekly') or {})
        known_byes = set((current.get(week) or current.get(str(week)) or {}).get('known_bye_player_ids') or [])
        for player in team.get("players") or []:
            pid = str(player.get("id") or player.get("player_id") or "")
            if not pid or pid in owned:
                raise ValueError("Diagnostic player ownership must be unique")
            owned.add(pid)
            details = database.get(pid) or {}
            source = {**details, **player}
            row = rows.get(pid) or {}
            points = (
                _number(
                    row.get("canonical_projection", row.get("weekly_projected_points"))
                )
                if admitted and row.get("week") == week
                else None
            )
            slot = str(source.get("roster_slot") or "").upper()
            from src.core.projection_intelligence.service import (
                player_availability,
                UNAVAILABLE_PLAYER_STATUSES,
            )

            status = player_availability(source, row)
            # Canonical unknown/unsigned evidence may support numerical scenarios,
            # never a verified availability claim. Unfamiliar statuses are withheld.
            unknown_status = status not in UNAVAILABLE_PLAYER_STATUSES | {
                "active",
                "questionable",
                "doubtful",
                "unknown",
                "unsigned",
                "unavailable",
            }
            unavailable = (
                slot in {"IR", "TAXI", "RESERVE"}
                or source.get("lineup_eligible") is False
                or source.get("bye_week") == week or pid in known_byes
                or status in UNAVAILABLE_PLAYER_STATUSES
                or unknown_status
            )
            reason = (
                "Roster reserve/taxi is not active lineup cover"
                if slot in {"IR", "TAXI", "RESERVE"}
                else "Not lineup eligible"
                if source.get("lineup_eligible") is False
                else "Observed bye week"
                if source.get("bye_week") == week or pid in known_byes
                else "Unsupported availability status"
                if unknown_status
                else status.title()
            )
            eligibility[rid].append(
                {
                    "player_id": pid,
                    "name": source.get("name") or source.get("full_name") or pid,
                    "position": source.get("position") or row.get("position"),
                    "fantasy_positions": row.get('fantasy_positions'),
                    "status": status,
                    "excluded": unavailable,
                    "reason": reason,
                }
            )
            if unavailable:
                excluded[rid].append(pid)
                continue
            if status in {"questionable", "doubtful"}:
                uncertain[rid].append(pid)
            pools[rid].append(
                {
                    "id": pid,
                    "name": source.get("name") or source.get("full_name") or pid,
                    "position": source.get("position") or row.get("position"),
                    "fantasy_positions": row.get('fantasy_positions'),
                    "projected_points": points,
                }
            )
    qualification["eligibility"] = eligibility
    return league_id, week, slots, admitted, pools, excluded, uncertain, qualification


def diagnostic_identity(data, snapshot, *, include_qualification=False):
    inputs = diagnostic_inputs(data, snapshot)
    if not include_qualification:
        return _identity(inputs, snapshot)
    qualification = inputs[-1]
    # Higher-level Team/HQ/League caches contain explanations, not only numbers.
    return sha256(
        json.dumps(
            (
                _identity(inputs, snapshot),
                qualification["projection_freshness"],
                bool(qualification["refresh"].get("retained_publication")),
            ),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _identity(inputs, snapshot):
    # Time and refresh-attempt labels do not alter numerical solver identity.
    stable = list(inputs)
    stable[-1] = {
        key: inputs[-1][key]
        for key in ("scoring", "calculation_supported", "eligibility")
    }
    return sha256(
        json.dumps(
            (
                METHOD,
                stable,
                sorted(
                    (
                        pid,
                        row.get("source_timestamp"),
                        row.get("source_freshness"),
                        row.get("sleeper_freshness"),
                    )
                    for pid, row in ((snapshot or {}).get("players") or {}).items()
                ),
                (snapshot or {}).get("projection_snapshot_id"),
                (snapshot or {}).get("scoring_profile_id"),
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _same(first, second):
    return (
        len(first.entries) == len(second.entries)
        and sorted(e.slot for e in first.entries)
        == sorted(e.slot for e in second.entries)
        and first.known_starters_subtotal == second.known_starters_subtotal
    )


def _delta(before, after):
    return (
        round(after.projected_points - before.projected_points, 4)
        if before.available and after.available
        else None
    )


def _compute(inputs, snapshot, key):
    lid, week, slots, admitted, pools, excluded, uncertain, qualification = inputs
    shared_evidence = {
        key: value for key, value in qualification.items() if key != "eligibility"
    }
    if not admitted or not _bounded(slots, pools):
        reason = (
            "Compatible league/week/scoring projection publication unavailable. "
            + " ".join(qualification["limitations"])
            if not admitted
            else "Roster/lineup configuration exceeds bounded diagnostic expansion; no positional conclusion inferred."
        )
        return {
            "methodology": METHOD,
            "league_id": lid,
            "generation": key,
            "week": week,
            "projection_generation": (snapshot or {}).get("projection_snapshot_id"),
            "teams": {
                rid: {
                    "positions": {
                        pos: {
                            "classification": "Uncertain",
                            "conclusion_state": "unavailable",
                            "evidence": {
                                **shared_evidence,
                                "calculation_supported": False,
                                "conclusion_state": "unavailable",
                            },
                            "eligibility": [
                                e
                                for e in qualification["eligibility"][rid]
                                if e["position"] == pos
                            ],
                            "starter_need": False,
                            "resilience_need": False,
                            "strength": False,
                            "surplus_assets": [],
                            "reason": reason,
                            "coverage": "partial / unavailable",
                            "remove_one": {},
                            "reference": None,
                            "add_one_gain": None,
                            "starting_ids": [],
                            "disjoint_reserve_ids": [],
                            "league_reference_points": None,
                        }
                        for pos in POSITIONS
                    },
                    "optimal_points": None,
                    "coverage": "partial / unavailable",
                    "limitations": [reason],
                    "independent_limitations": [
                        "Roster/lineup configuration exceeds bounded diagnostic expansion; no positional conclusion inferred."
                        if not _bounded(slots, pools)
                        else "Compatible league/week/scoring projection publication unavailable."
                    ],
                    "evidence": {
                        **shared_evidence,
                        "calculation_supported": False,
                        "conclusion_state": "unavailable",
                    },
                    "excluded_player_ids": excluded[rid],
                    "eligibility": qualification["eligibility"][rid],
                }
                for rid in pools
            },
        }
    solver = SearchLineupMemo(("diagnostics", lid, key))

    def solve(pool):
        return solver.solve(pool, slots, week=week)

    optimal = {rid: solve(pool) for rid, pool in pools.items()}
    reserves = {
        rid: [
            p for p in pools[rid] if p["id"] not in {e.asset_id for e in base.entries}
        ]
        for rid, base in optimal.items()
    }
    reserve_lineups = {rid: solve(pool) for rid, pool in reserves.items()}
    references = {
        pos: [
            (rid, next(p for p in pools[rid] if p["id"] == e.asset_id))
            for rid, base in optimal.items()
            for e in base.entries
            if e.position == pos
        ]
        for pos in POSITIONS
    }
    result = {
        "methodology": METHOD,
        "league_id": lid,
        "generation": key,
        "week": week,
        "projection_generation": (snapshot or {}).get("projection_snapshot_id"),
        "teams": {},
    }
    for rid, pool in pools.items():
        base, reserve = optimal[rid], reserve_lineups[rid]
        missing = [p["id"] for p in pool if p["projected_points"] is None]
        complete = bool(admitted and slots and not missing and not uncertain[rid])
        team_evidence = deepcopy(
            {key: value for key, value in qualification.items() if key != "eligibility"}
        )
        team_evidence["projection_coverage"] = {
            "supported": len(pool) - len(missing),
            "eligible": len(pool),
            "missing_player_ids": missing,
        }
        if any(
            not e["excluded"] and e["status"] in {"unknown", "unsigned", "unavailable"}
            for e in qualification["eligibility"][rid]
        ):
            team_evidence["conclusion_state"] = "provisional"
            team_evidence["limitations"].append(
                "Availability is unknown for some rostered players; numerical scenarios are provisional, not verified active cover."
            )
        if not complete:
            team_evidence["conclusion_state"] = "unavailable"
        removals = {}
        primary_ids = {e.asset_id for e in base.entries}
        reserve_ids = {e.asset_id for e in reserve.entries}
        for player in pool:
            remaining = [p for p in pool if p["id"] != player["id"]]
            after = solve(remaining) if player["id"] in primary_ids else base
            after_ids = {e.asset_id for e in after.entries}
            after_reserve = (
                solve([p for p in remaining if p["id"] not in after_ids])
                if player["id"] in primary_ids | reserve_ids
                else reserve
            )
            removals[player["id"]] = {
                "replacement_names": [
                    p["name"] for p in remaining if p["id"] in after_ids - primary_ids
                ],
                "replacement_points": [
                    p["projected_points"]
                    for p in remaining
                    if p["id"] in after_ids - primary_ids
                ],
                "lineup_loss": -_delta(base, after)
                if _delta(base, after) is not None
                else None,
                "supported_slots_after": len(after.entries),
                "preserves_lineup": _same(base, after),
                "preserves_disjoint_reserve": _same(reserve, after_reserve),
            }
        positions = {}
        for pos in POSITIONS:
            members = [p for p in pool if pos in eligible_positions(p)]
            candidates = [(owner, p) for owner, p in references[pos] if owner != rid]
            target = (
                median(p["projected_points"] for _, p in candidates)
                if candidates
                else None
            )
            reference = (
                min(
                    candidates,
                    key=lambda item: (
                        abs(item[1]["projected_points"] - target),
                        item[1]["id"],
                    ),
                )
                if candidates
                else None
            )
            addition = solve(pool + [reference[1]]) if reference else None
            gain = _delta(base, addition) if addition else None
            added_slots = (
                max(0, len(addition.entries) - len(base.entries)) if addition else 0
            )
            relevant = any(
                _eligible(pos, slot) for slot in slots if slot not in BENCH_SLOTS
            )
            starters = [e for e in base.entries if e.position == pos]
            backup = [p for p in reserves[rid] if pos in eligible_positions(p)]
            # Reserve assignment is disjoint across ALL lineup slots, so one
            # replacement cannot be counted at both FLEX and its core position.
            supported_reserve = [
                e.asset_id for e in reserve.entries if e.position == pos
            ]
            tradable = []
            if complete and base.available:
                for player in members:
                    loss = removals[player["id"]]
                    if not (
                        loss["preserves_lineup"] and loss["preserves_disjoint_reserve"]
                    ):
                        continue
                    benefits = []
                    for other, other_pool in pools.items():
                        if (
                            other == rid
                            or not optimal[other].available
                            or any(p["projected_points"] is None for p in other_pool)
                        ):
                            continue
                        delta = _delta(optimal[other], solve(other_pool + [player]))
                        if delta is not None and delta > 0:
                            benefits.append({"roster_id": other, "lineup_gain": delta})
                    if benefits:
                        tradable.append(
                            {
                                "player_id": player["id"],
                                "recipient_opportunities": benefits,
                            }
                        )
            need = (
                complete
                and relevant
                and (added_slots > 0 or (gain is not None and gain > 0))
            )
            resilience = complete and any(
                removals[e.asset_id]["supported_slots_after"] < len(base.entries)
                for e in starters
            )
            peer_reserve_points = [
                e.projected_points
                for owner, lineup in reserve_lineups.items()
                if owner != rid
                for e in lineup.entries
                if e.position == pos
            ]
            replacement_reference = (
                median(peer_reserve_points) if peer_reserve_points else None
            )
            actual_replacements = [
                value
                for e in starters
                for value in removals[e.asset_id]["replacement_points"]
            ]
            quality_depth = bool(
                complete
                and actual_replacements
                and replacement_reference is not None
                and min(actual_replacements) < replacement_reference
            )
            strength = (
                complete
                and bool(starters)
                and target is not None
                and min(e.projected_points for e in starters) >= target
            )
            classification = (
                "Uncertain"
                if not complete
                else "Not required by lineup"
                if not relevant
                else "Starter improvement"
                if need
                else "Resilience need"
                if resilience
                else "Quality/depth need"
                if quality_depth
                else "Conditional expendable depth"
                if tradable
                else "Strategic strength"
                if strength
                else "No established need or surplus"
            )
            reason = f"{pos}: {classification.lower()}. "
            if not complete:
                reason += "Missing compatible projections or uncertain availability prevents a dependable depth conclusion."
            elif need:
                reason += (
                    f"An observed league-reference {pos} can improve the legal lineup"
                    + (
                        f" by {gain:g} projected points."
                        if gain is not None
                        else " by covering an unsupported slot."
                    )
                )
            elif tradable and not resilience and not quality_depth:
                reason += "Identified assets preserve current starters and disjoint reserve support while improving another observed lineup."
            elif resilience:
                reason += "Removing a current starter leaves unsupported legal starting slots; a complete replacement is not established."
            elif quality_depth:
                reason += "Observed legal replacements project below the peer reserve reference; cross-position flex substitutions remain allowed."
            else:
                reason += "Player count alone does not establish expendability; review removal effects and reserve assignments."
            position_evidence = team_evidence
            positions[pos] = {
                "evidence": position_evidence,
                "eligibility": [
                    e for e in qualification["eligibility"][rid] if e["position"] == pos
                ],
                "classification": classification,
                "starter_need": bool(need),
                "resilience_need": bool(resilience),
                "quality_depth_need": quality_depth,
                "replacement_reference_points": replacement_reference,
                "observed_replacement_points": actual_replacements,
                "strength": bool(strength),
                "surplus_assets": tradable,
                "reason": reason
                + (
                    " " + " ".join(position_evidence["limitations"])
                    if position_evidence["limitations"]
                    else ""
                ),
                "base_reason": reason,
                "conclusion_state": position_evidence["conclusion_state"]
                if complete
                else "unavailable",
                "coverage": "supported current week"
                if complete
                else "partial / unavailable",
                "eligible_players": len(members),
                "supported_players": sum(
                    p["projected_points"] is not None for p in members
                ),
                "starting_ids": [e.asset_id for e in starters],
                "reserve_ids": [p["id"] for p in backup],
                "disjoint_reserve_ids": supported_reserve,
                "remove_one": {p["id"]: removals[p["id"]] for p in members},
                "reference": {
                    "player_id": reference[1]["id"],
                    "roster_id": reference[0],
                    "points": reference[1]["projected_points"],
                }
                if reference
                else None,
                "add_one_gain": gain,
                "add_one_supported_slots": added_slots,
                "league_starter_observations": len(references[pos]),
                "league_reference_points": target,
                "availability_context": "Observed roster reference, not an available trade or acceptance prediction.",
            }
        result["teams"][rid] = {
            "evidence": team_evidence,
            "eligibility": qualification["eligibility"][rid],
            "positions": positions,
            "optimal_points": base.projected_points,
            "optimal_ids": [e.asset_id for e in base.entries],
            "reserve_ids": [e.asset_id for e in reserve.entries],
            "missing_projection_ids": missing,
            "excluded_player_ids": excluded[rid],
            "uncertain_player_ids": uncertain[rid],
            "coverage": "supported current week"
            if complete
            else "partial / unavailable",
            "limitations": qualification["limitations"]
            + [
                "Current-week diagnostic; future projections, byes and long-term quality are not inferred.",
                "Removal/addition effects are separate scenarios and must not be summed.",
                "Reserve support is a disjoint legal assignment, not an injury probability or guaranteed replacement.",
            ],
            "independent_limitations": [
                "Current-week diagnostic; future projections, byes and long-term quality are not inferred.",
                "Removal/addition effects are separate scenarios and must not be summed.",
                "Reserve support is a disjoint legal assignment, not an injury probability or guaranteed replacement.",
            ],
        }
    result["computation"] = {"lineup_hits": solver.hits, "lineup_misses": solver.misses}
    return result


def _requalify(result, qualification):
    """Cheap read-time qualification; never rerun legal assignment for clock age."""
    shared = {
        key: value for key, value in qualification.items() if key != "eligibility"
    }
    for team in result["teams"].values():
        original_evidence = team.get("evidence") or {}
        evidence = deepcopy(shared)
        evidence["projection_coverage"] = (team.get("evidence") or {}).get(
            "projection_coverage", {}
        )
        eligibility = team.get("eligibility") or []
        if any(not e["excluded"] and e["status"] != "active" for e in eligibility):
            evidence["conclusion_state"] = "provisional"
            evidence["limitations"].append(
                "Availability is uncertain for named rostered players; numerical scenarios are provisional, not verified active cover."
            )
        # Admission and coverage are separate: a missing reserve projection
        # must not erase independent supported lineup evidence in other readers.
        if not original_evidence.get("calculation_supported"):
            evidence["calculation_supported"] = False
        if (
            not evidence["calculation_supported"]
            or team.get("optimal_points") is None
            or team.get("missing_projection_ids")
        ):
            evidence["conclusion_state"] = "unavailable"
        team["evidence"] = evidence
        for facts in team["positions"].values():
            facts["evidence"] = evidence
            facts["conclusion_state"] = evidence["conclusion_state"]
            base = facts.get("base_reason")
            if base is not None:
                facts["reason"] = base + (
                    " " + " ".join(evidence["limitations"])
                    if evidence["limitations"]
                    else ""
                )
        # Keep independent scope/scenario limits, replace only source qualifiers.
        independent = team.get("independent_limitations", [])
        team["limitations"] = (
            independent + evidence["limitations"]
            if any("bounded" in item for item in independent)
            else evidence["limitations"] + independent
        )
    return result


def prepared_diagnostics(data, snapshot=None, *, projection_reader=None):
    """Read/requalify an existing publication; never compute on a cache miss."""
    snapshot = projection_snapshot(data) if snapshot is None else snapshot
    inputs = diagnostic_inputs(data, snapshot)
    saved = diagnostic_store.get(_identity(inputs, snapshot))
    if saved is None:
        return None
    return _requalify(json.loads(saved), _qualification(
        data, snapshot, inputs[2], projection_reader=projection_reader))


def diagnose_league(data, snapshot=None, *, projection_reader=None):
    snapshot = projection_snapshot(data) if snapshot is None else snapshot
    inputs = diagnostic_inputs(data, snapshot)
    return _diagnose_inputs(data, snapshot, inputs, projection_reader)


def _diagnose_inputs(data, snapshot, inputs, projection_reader):
    """Consume inputs prepared by this call, never a caller-supplied cache key."""
    key = _identity(inputs, snapshot)
    saved = diagnostic_store.get(key)
    if saved is None:
        result = _compute(inputs, snapshot, key)
        diagnostic_store.put(key, json.dumps(result, separators=(",", ":")).encode())
    else:
        result = json.loads(saved)
    qualification = _qualification(
        data, snapshot, inputs[2], projection_reader=projection_reader
    )
    return _requalify(result, qualification)


def team_diagnostics(
    data, roster_id, snapshot=None, *, strategy=None, projection_reader=None
):
    league = diagnose_league(data, snapshot, projection_reader=projection_reader)
    return _team_from_league(data, roster_id, snapshot, strategy, league)


def _team_from_league(data, roster_id, snapshot, strategy, league):
    """Copy one team's view from the same already-qualified league result."""
    row = deepcopy(
        league["teams"].get(
            str(roster_id),
            {
                "positions": {},
                "coverage": "unavailable",
                "limitations": ["Franchise unavailable."],
            },
        )
    )
    row.update(
        {
            key: league[key]
            for key in (
                "methodology",
                "league_id",
                "generation",
                "projection_generation",
                "week",
            )
        }
    )
    team = next(
        (
            t
            for t in data.get("teams") or []
            if str(t.get("roster_id")) == str(roster_id)
        ),
        {},
    )
    chosen = (
        strategy
        if str(strategy or "").upper() not in {"", "UNSPECIFIED"}
        else team.get("strategy")
    )
    from .team_strength import compatible_profile

    profile = compatible_profile(data, snapshot)
    window = (data.get("competitive_windows") or {}).get(str(roster_id))
    if (
        not profile
        or not window
        or window.get("generation") != profile.get("semantic_generation")
    ):
        window = None
    intent = resolve_strategy(chosen, window)
    row["strategy"] = intent
    for pos, facts in row["positions"].items():
        facts["objective_need"] = bool(
            (
                facts["starter_need"]
                or facts["resilience_need"]
                or facts.get("quality_depth_need")
            )
            and intent["strategy"] != "REBUILD"
        )
        facts["interpretation"] = facts["reason"]
        if intent["strategy"] == "REBUILD" and (
            facts["starter_need"]
            or facts["resilience_need"]
            or facts.get("quality_depth_need")
        ):
            facts["classification"] = "Current production gap"
            facts["interpretation"] = (
                f"{pos}: current production/depth gap under REBUILD. Long-term asset quality is unestablished; this is not advice to acquire an aging starter."
            )
        elif intent["strategy"] == "RETOOL":
            facts["interpretation"] += (
                " Under RETOOL, compare sustainable quality and capital costs separately."
            )
        elif intent["strategy"] == "WIN NOW":
            facts["interpretation"] += (
                " Under WIN NOW, preserve supported starter and replacement production before selling strength."
            )
    return row


def package_diagnostics(
    data, proposal, snapshot, impact, strategies, *, projection_reader=None
):
    """All players move together; existing capacity/horizon gates stay authoritative."""
    if snapshot is None:
        # Preserve the public resolver and original admission for an absent input.
        baseline = diagnose_league(data, snapshot, projection_reader=projection_reader)
        inputs = diagnostic_inputs(data, snapshot)
    else:
        inputs = diagnostic_inputs(data, snapshot)
        baseline = _diagnose_inputs(data, snapshot, inputs, projection_reader)
    lid, week, slots, admitted, pools, _, _, qualification = inputs
    teams = {str(t.get("roster_id")): t for t in data.get("teams") or []}
    active, partner = str(proposal.active_roster_id), str(proposal.partner_roster_id)
    sent = {
        a.asset_id.removeprefix("player:")
        for a in proposal.assets_sent
        if a.kind == "player"
    }
    received = {
        a.asset_id.removeprefix("player:")
        for a in proposal.assets_received
        if a.kind == "player"
    }
    # Apply the same admission to complete proposed rosters, including incoming
    # uncertain/excluded players. Never reuse PRE eligibility as POST evidence.
    post_data = {
        **data,
        "teams": [
            {**team, "players": list(team.get("players") or [])}
            for team in data.get("teams") or []
        ],
    }
    player_rows = {
        str(p.get("id") or p.get("player_id")): p
        for team in data.get("teams") or []
        for p in team.get("players") or []
    }
    for team in post_data["teams"]:
        rid = str(team.get("roster_id"))
        if rid not in {active, partner}:
            continue
        outgoing, incoming = (sent, received) if rid == active else (received, sent)
        team["players"] = [
            p
            for p in team["players"]
            if str(p.get("id") or p.get("player_id")) not in outgoing
        ] + [
            {**player_rows[pid], "roster_slot": "Bench"}
            for pid in sorted(incoming)
            if pid in player_rows
        ]
    post_inputs = diagnostic_inputs(post_data, snapshot)
    post_pools, post_qualification = post_inputs[4], post_inputs[-1]
    qualification = _qualification(
        data, snapshot, slots, projection_reader=projection_reader
    )
    # A failed refresh can qualify an unchanged publication during assembly.
    # Keep both pre-views at this latest qualification boundary, without
    # decoding/rebuilding the same league inputs separately for each team.
    baseline = _requalify(
        {**baseline, "teams": {rid: row for rid, row in baseline["teams"].items()
                              if rid in {active, partner}}}, qualification
    )
    by_id = {p["id"]: p for pool in pools.values() for p in pool}
    solver = SearchLineupMemo(("diagnostics", lid, baseline["generation"]))
    result = {
        "methodology": METHOD,
        "league_id": lid,
        "generation": baseline["generation"],
        "projection_generation": baseline["projection_generation"],
        "week": week,
        "sides": {},
        "meaning": "Package-local current-week legal assignments; scenarios are not summed. Existing multi-week and forced-cut gates remain authoritative.",
        "evidence": {
            key: value for key, value in qualification.items() if key != "eligibility"
        },
    }
    if not admitted or not _bounded(slots, pools):
        reason = (
            " ".join(qualification["limitations"])
            if not admitted
            else "Roster/lineup configuration exceeds bounded diagnostic expansion; no positional conclusion inferred."
        )
        result["evidence"].update(
            calculation_supported=False, conclusion_state="unavailable"
        )
        result["sides"] = {
            label: {
                "roster_id": rid,
                "positions": {},
                "pre_optimal_points": None,
                "post_optimal_points": None,
                "available_pre_optimal_points": None,
                "available_post_optimal_points": None,
                "coverage": "partial / unavailable",
                "need_positions_received": [],
                "summary": reason,
                "evidence": result["evidence"],
            }
            for label, rid in (("active", active), ("partner", partner))
        }
        return result
    for label, rid, outgoing, incoming in (
        ("active", active, sent, received),
        ("partner", partner, received, sent),
    ):
        before = _team_from_league(
            data, rid, snapshot, strategies.get(rid) or teams[rid].get("strategy"), baseline
        )
        pool = post_pools[rid]
        post_evidence = deepcopy(
            {key: value for key, value in qualification.items() if key != "eligibility"}
        )
        post_eligibility = post_qualification["eligibility"][rid]
        if any(not e["excluded"] and e["status"] != "active" for e in post_eligibility):
            post_evidence["conclusion_state"] = "provisional"
            post_evidence["limitations"].append(
                "Post-trade availability is uncertain: "
                + ", ".join(
                    e["name"] + " (" + e["status"] + ")"
                    for e in post_eligibility
                    if not e["excluded"] and e["status"] != "active"
                )
                + "; lineup impact is provisional, not dependable cover."
            )
        if any(p["projected_points"] is None for p in pool):
            post_evidence.update(
                calculation_supported=False, conclusion_state="unavailable"
            )
        # Unavailable/IR/taxi source assets remain qualified, not fabricated playable additions.
        unknown_incoming = sorted(incoming - set(by_id))
        post = solver.solve(pool, slots, week=week)
        post_reserve = solver.solve(
            [p for p in pool if p["id"] not in {e.asset_id for e in post.entries}],
            slots,
            week=week,
        )
        positions = {}
        for pos, old in before["positions"].items():
            positions[pos] = {
                "pre": old,
                "post_starters": [
                    e.asset_id for e in post.entries if e.position == pos
                ],
                "post_disjoint_reserves": [
                    e.asset_id for e in post_reserve.entries if e.position == pos
                ],
            }
        side = ((impact or {}).get("sides") or {}).get(label) or {}
        weekly = (
            (side.get("weekly") or {}).get(week)
            or (side.get("weekly") or {}).get(str(week))
            or {}
        )
        canonical_pre = ((weekly.get("pre") or {}).get("optimal") or {}).get(
            "projected_points"
        )
        canonical_post = ((weekly.get("post") or {}).get("optimal") or {}).get(
            "projected_points"
        )
        availability_matches = (
            canonical_pre == before["optimal_points"]
            and canonical_post == post.projected_points
        )
        if (
            not availability_matches
            or unknown_incoming
            or (side.get("roster_capacity") or {}).get("additional_spots_to_resolve")
        ):
            if post_evidence["conclusion_state"] == "current":
                post_evidence["conclusion_state"] = "provisional"
            post_evidence["limitations"].append(
                "Availability-qualified post-trade lineup or capacity differs from the canonical comparison; no dependable complete impact is established."
            )
        excluded_incoming = [
            e for e in post_eligibility if e["player_id"] in incoming and e["excluded"]
        ]
        if excluded_incoming:
            post_evidence["limitations"].append(
                "Incoming players excluded from usable cover: "
                + ", ".join(
                    e["name"] + " (" + e["reason"] + ")" for e in excluded_incoming
                )
                + "."
            )
        result["sides"][label] = {
            "evidence": post_evidence,
            "eligibility": before["eligibility"],
            "pre_evidence": before["evidence"],
            "post_evidence": post_evidence,
            "pre_eligibility": before["eligibility"],
            "post_eligibility": post_eligibility,
            "post_lineup_assignments": [
                {
                    "player_id": entry.asset_id,
                    "name": next(p["name"] for p in pool if p["id"] == entry.asset_id),
                    "slot": entry.slot,
                }
                for entry in post.entries
            ],
            "numeric_impact_state": "unsupported"
            if not post_evidence["calculation_supported"]
            or canonical_pre is None
            or canonical_post is None
            else "supported"
            if post_evidence["conclusion_state"]
            == before["evidence"]["conclusion_state"]
            == "current"
            else "provisional",
            "roster_id": rid,
            "strategy": before["strategy"],
            "positions": positions,
            "pre_optimal_points": canonical_pre,
            "post_optimal_points": canonical_post,
            "available_pre_optimal_points": before["optimal_points"],
            "available_post_optimal_points": post.projected_points,
            "availability_matches_canonical": availability_matches,
            "unknown_incoming_ids": unknown_incoming,
            "coverage": "supported current week"
            if admitted
            and not unknown_incoming
            and not post.missing_player_ids
            and before["coverage"] == "supported current week"
            and availability_matches
            and not (side.get("roster_capacity") or {}).get(
                "additional_spots_to_resolve"
            )
            else "partial / unavailable",
            "capacity": side.get("roster_capacity"),
            "need_positions_received": sorted(
                {
                    by_id[p]["position"]
                    for p in incoming
                    if p in by_id
                    and before["positions"]
                    .get(by_id[p]["position"], {})
                    .get("objective_need")
                }
            ),
            "summary": f"Package optimal lineup: {canonical_pre if canonical_pre is not None else 'unavailable'} → {canonical_post if canonical_post is not None else 'unavailable'} Sleeper-projected points. Replacement support is recalculated after all player movements. "
            + " ".join(post_evidence["limitations"])
            + (
                " Availability-qualified depth differs or canonical comparison is unavailable; no complete diagnostic conclusion is claimed."
                if not availability_matches
                else ""
            ),
        }
    states = {side["evidence"]["conclusion_state"] for side in result["sides"].values()}
    result["evidence"]["conclusion_state"] = (
        "unavailable"
        if "unavailable" in states
        else "provisional"
        if "provisional" in states
        else "current"
    )
    return result
