"""Disposable league-relative roster facts from canonical legal lineups.

Current-week evidence, not a player value/projection or acceptance model.
Every add/remove is a complete legal assignment; effects must never be summed.
"""

from copy import deepcopy
from hashlib import sha256
import json
from math import isfinite
from statistics import median

from src.core.trade_intelligence.lineup import BENCH_SLOTS, _eligible
from src.core.trade_intelligence.lineup_memo import LineupStore, SearchLineupMemo
from src.core.trade_intelligence.capital_assessment import resolve_strategy

POSITIONS = ("QB", "RB", "WR", "TE")
METHOD = "legal-roster-diagnostics-v1"
diagnostic_store = LineupStore(max_entries=12, max_bytes=2_097_152, ttl=180)


def _number(value):
    return (
        float(value)
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        else None
    )


def projection_snapshot(data):
    from src.platform.league_context import current_league_context
    from src.core.projection_intelligence import projection_service

    runtime = current_league_context()
    league_id = str((data.get("league") or {}).get("league_id") or "")
    service = (
        runtime.projection
        if runtime and runtime.league_id == league_id
        else projection_service
    )
    return service.snapshot()


def diagnostic_inputs(data, snapshot):
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or "")
    week = data.get("week") or 1
    slots = tuple(data.get("roster_positions") or league.get("roster_positions") or ())
    scoring = data.get("scoring_settings") or league.get("scoring_settings")
    admitted = bool(
        snapshot
        and snapshot.get("projection_snapshot_id")
        and str(snapshot.get("league_id")) == league_id
        and snapshot.get("week") == week
        and (
            league.get("season") is None
            or str(snapshot.get("season")) == str(league["season"])
        )
        and (scoring is None or snapshot.get("scoring_settings") == scoring)
    )
    rows = (snapshot or {}).get("players") or {}
    pools, excluded, uncertain = {}, {}, {}
    owned = set()
    for team in data.get("teams") or []:
        rid = str(team.get("roster_id"))
        if rid in pools:
            raise ValueError("Duplicate diagnostic franchise identity")
        pools[rid], excluded[rid], uncertain[rid] = [], [], []
        for player in team.get("players") or []:
            pid = str(player.get("id") or player.get("player_id") or "")
            if not pid or pid in owned:
                raise ValueError("Diagnostic player ownership must be unique")
            owned.add(pid)
            details = (data.get("players") or {}).get(pid) or {}
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
            status = str(
                player.get("injury_status")
                or details.get("injury_status")
                or player.get("status")
                or details.get("status")
                or ""
            ).upper()
            unavailable = (
                slot in {"IR", "TAXI", "RESERVE"}
                or source.get("lineup_eligible") is False
                or source.get("bye_week") == week
                or status in {"OUT", "O", "IR", "PUP", "SUSPENDED", "SUS"}
            )
            if unavailable:
                excluded[rid].append(pid)
                continue
            if status in {"QUESTIONABLE", "Q", "DOUBTFUL", "D"}:
                uncertain[rid].append(pid)
            pools[rid].append(
                {
                    "id": pid,
                    "name": source.get("name") or source.get("full_name") or pid,
                    "position": source.get("position") or row.get("position"),
                    "projected_points": points,
                }
            )
    return league_id, week, slots, admitted, pools, excluded, uncertain


def diagnostic_identity(data, snapshot):
    inputs = diagnostic_inputs(data, snapshot)
    return _identity(inputs, snapshot)


def _identity(inputs, snapshot):
    return sha256(
        json.dumps(
            (
                METHOD,
                inputs,
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
    lid, week, slots, admitted, pools, excluded, uncertain = inputs
    if (
        not admitted
        or sum(map(len, pools.values())) > 2048
        or sum(slot not in BENCH_SLOTS for slot in slots) > 14
    ):
        reason = (
            "Compatible league/week/scoring projection publication unavailable."
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
            members = [p for p in pool if p["position"] == pos]
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
            backup = [p for p in reserves[rid] if p["position"] == pos]
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
            positions[pos] = {
                "classification": classification,
                "starter_need": bool(need),
                "resilience_need": bool(resilience),
                "quality_depth_need": quality_depth,
                "replacement_reference_points": replacement_reference,
                "observed_replacement_points": actual_replacements,
                "strength": bool(strength),
                "surplus_assets": tradable,
                "reason": reason,
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
            "limitations": [
                "Current-week diagnostic; future projections, byes and long-term quality are not inferred.",
                "Removal/addition effects are separate scenarios and must not be summed.",
                "Reserve support is a disjoint legal assignment, not an injury probability or guaranteed replacement.",
            ],
        }
    result["computation"] = {"lineup_hits": solver.hits, "lineup_misses": solver.misses}
    return result


def diagnose_league(data, snapshot=None):
    snapshot = projection_snapshot(data) if snapshot is None else snapshot
    inputs = diagnostic_inputs(data, snapshot)
    key = _identity(inputs, snapshot)
    saved = diagnostic_store.get(key)
    if saved is None:
        result = _compute(inputs, snapshot, key)
        diagnostic_store.put(key, json.dumps(result, separators=(",", ":")).encode())
        return result
    return json.loads(saved)


def team_diagnostics(data, roster_id, snapshot=None, *, strategy=None):
    league = diagnose_league(data, snapshot)
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


def package_diagnostics(data, proposal, snapshot, impact, strategies):
    """All players move together; existing capacity/horizon gates stay authoritative."""
    baseline = diagnose_league(data, snapshot)
    lid, week, slots, admitted, pools, _, _ = diagnostic_inputs(data, snapshot)
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
    }
    for label, rid, outgoing, incoming in (
        ("active", active, sent, received),
        ("partner", partner, received, sent),
    ):
        before = team_diagnostics(
            data,
            rid,
            snapshot,
            strategy=strategies.get(rid) or teams[rid].get("strategy"),
        )
        pool = [p for p in pools[rid] if p["id"] not in outgoing] + [
            by_id[pid] for pid in sorted(incoming) if pid in by_id
        ]
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
        result["sides"][label] = {
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
            "summary": f"Package optimal lineup: {canonical_pre if canonical_pre is not None else 'unavailable'} → {canonical_post if canonical_post is not None else 'unavailable'} Sleeper-projected points. Replacement support is recalculated after all player movements."
            + (
                " Availability-qualified depth differs or canonical comparison is unavailable; no complete diagnostic conclusion is claimed."
                if not availability_matches
                else ""
            ),
        }
    return result
