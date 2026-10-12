"""Bounded presentation traversal over the existing asset graph; no writes."""

from __future__ import annotations

from collections import OrderedDict

from src.core.history_context.timestamps import canonical_utc_timestamp

MAX_EVENTS = 100
MAX_ASSETS = 40


def timeline(graph, dossier):
    """Observed asset continuity, plus selection conversion, never value allocation."""
    summary = OrderedDict()
    for event in dossier["asset_events"]:
        summary.setdefault(event["asset_id"], []).append(event)
    root = canonical_utc_timestamp(dossier.get("occurred_at"))
    selections = {str(r["source_record_id"]): r for r in graph._records("draft_pick")}
    identities = graph._records("franchise_identity")

    def franchise(identity, season):
        rows = [
            r
            for r in identities
            if r.get("franchise_id") == identity and r["season"] == season
        ]
        row = rows[0]["payload"] if len(rows) == 1 else {}
        return {
            "id": identity,
            "name": row.get("dtos_display_name") or identity.rsplit(":", 1)[-1]
            if identity
            else "Unavailable franchise",
            "manager": row.get("sleeper_username"),
            "manager_scope": "Season-observed owner; exact trade-time tenure not established",
        }

    def label(asset):
        if asset.startswith("DTOS-P-"):
            return graph.player_identity(asset)["display_label"]
        if asset.startswith("PICK-"):
            parts = graph._pick_parts(asset)
            original = franchise(
                f"{graph.league_id}:franchise:{parts.get('original_roster')}",
                dossier["season"],
            )
            return f"{parts.get('season')} Round {parts.get('round')} · originally {original['name']}"
        return "Exact draft selection"

    def asset_url(asset):
        return (
            "/players/" + asset.removeprefix("DTOS-P-")
            if asset.startswith("DTOS-P-")
            else "/picks/" + asset
        )

    def bounds(event):
        exact = canonical_utc_timestamp(event.get("occurred_at"))
        if exact:
            return exact, exact
        row = (
            selections.get(str(event.get("source_record_id")), {}).get("payload") or {}
        )
        return canonical_utc_timestamp(
            row.get("draft_start_at")
        ), canonical_utc_timestamp(row.get("draft_last_pick_at"))

    def observed_owner(asset):
        # Current source holding, not last scored owner or last deterministic event.
        data = graph.current_data
        if str((data.get("league") or {}).get("league_id")) != graph.league_id:
            return None
        if asset.startswith("DTOS-P-"):
            player = asset.removeprefix("DTOS-P-")
            owners = [
                t.get("roster_id")
                for t in data.get("teams") or ()
                if any(
                    str(p.get("id") or p.get("player_id")) == player
                    for p in t.get("players") or ()
                )
            ]
        else:
            parts = graph._pick_parts(asset)
            owners = [
                p.get("current_owner_id")
                for p in data.get("pick_ledger") or ()
                if str(p.get("season")) == parts.get("season")
                and str(p.get("round")) == parts.get("round")
                and str(p.get("original_roster_id")) == parts.get("original_roster")
            ]
        return (
            f"{graph.league_id}:franchise:{owners[0]}"
            if len(owners) == 1 and owners[0] is not None
            else None
        )

    branches, seen_events, budget = [], set(), MAX_EVENTS
    for asset, original_events in list(summary.items())[:MAX_ASSETS]:
        movements, limits = [], []
        outgoing = sorted(
            {
                e["from_franchise_id"]
                for e in original_events
                if e.get("from_franchise_id")
            }
        )
        incoming = sorted(
            {e["to_franchise_id"] for e in original_events if e.get("to_franchise_id")}
        )
        queue = [(asset, root, 0, incoming[0] if len(incoming) == 1 else None)]
        visited = set()
        while queue and budget:
            current, boundary, depth, expected_owner = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            groups = OrderedDict()
            unresolved_clock = False
            for event in graph.events(asset_id=current):
                if event["event_status"].casefold() not in {
                    "complete",
                    "completed",
                } or event["event_type"] in {"pick_snapshot", "roster_snapshot"}:
                    continue
                if event.get("parent_id") == dossier["trade_id"]:
                    continue
                low, high = bounds(event)
                if not boundary or not low or not high:
                    limits.append(
                        "Missing event clocks or draft bounds prevent confirmed subsequent order."
                    )
                    unresolved_clock = True
                    continue
                if high <= boundary:
                    continue
                if low <= boundary:
                    limits.append(
                        "Overlapping event time bounds leave this branch unresolved."
                    )
                    continue
                key = (
                    event.get("parent_id"),
                    event["source_record_id"],
                    event["event_type"],
                )
                groups.setdefault(key, []).append(event)
            if unresolved_clock:
                limits.append(
                    "Unresolved chronology ends this continuation; open the asset dossier for independent observations."
                )
                continue
            ordered = sorted(
                groups.values(),
                key=lambda rows: (
                    bounds(rows[0])[0] or "",
                    rows[0]["source_record_id"],
                ),
            )
            clocks = {}
            for rows in ordered:
                clocks.setdefault(bounds(rows[0]), set()).add(rows[0].get("parent_id"))
            for rows in ordered:
                event = rows[0]
                low, high = bounds(event)
                if len(clocks[(low, high)]) > 1:
                    limits.append(
                        "Equal event clocks do not establish transaction order; continuation withheld."
                    )
                    break
                from_owners = {
                    e["from_franchise_id"] for e in rows if e.get("from_franchise_id")
                }
                to_owners = {
                    e["to_franchise_id"] for e in rows if e.get("to_franchise_id")
                }
                if (
                    expected_owner is not None
                    and from_owners
                    and from_owners != {expected_owner}
                ):
                    limits.append(
                        "Missing ownership transition ends this branch; no causal continuity is invented."
                    )
                    break
                if to_owners:
                    expected_owner = (
                        next(iter(to_owners)) if len(to_owners) == 1 else None
                    )
                elif from_owners:
                    expected_owner = None
                if not budget:
                    break
                key = (
                    current,
                    event.get("parent_id"),
                    event["source_record_id"],
                    event["event_type"],
                )
                if key in seen_events:
                    continue
                seen_events.add(key)
                budget -= 1
                parents = event.get("parent_id") or ""
                trade_url = (
                    "/trades/history/" + parents.rsplit("-", 1)[-1]
                    if parents.startswith("TRADE-")
                    else None
                )
                move = {
                    "event_id": event["event_id"],
                    "asset_id": current,
                    "asset_label": label(current),
                    "type": event["event_type"],
                    "occurred_at": event.get("occurred_at"),
                    "time_bounds": [low, high],
                    "source_league_id": event["source_league_id"],
                    "source_record_id": event["source_record_id"],
                    "from": sorted(
                        {
                            e["from_franchise_id"]
                            for e in rows
                            if e.get("from_franchise_id")
                        }
                    ),
                    "from_names": [
                        franchise(f, event["season"])["name"]
                        for f in sorted(
                            {
                                e["from_franchise_id"]
                                for e in rows
                                if e.get("from_franchise_id")
                            }
                        )
                    ],
                    "to": sorted(
                        {e["to_franchise_id"] for e in rows if e.get("to_franchise_id")}
                    ),
                    "to_names": [
                        franchise(f, event["season"])["name"]
                        for f in sorted(
                            {
                                e["to_franchise_id"]
                                for e in rows
                                if e.get("to_franchise_id")
                            }
                        )
                    ],
                    "trade_url": trade_url,
                    "evidence": "Observed transaction"
                    if trade_url
                    or "draft" not in event["event_type"]
                    and event["event_type"] != "pick_exercise"
                    else "Observed draft selection with source identity",
                    "package_note": "Package relationship only; no descendant values or speculative shares are assigned."
                    if trade_url
                    else None,
                }
                if event["event_type"] == "pick_exercise":
                    selected = selections.get(str(event["source_record_id"]))
                    if selected and selected.get("player_id") and depth < 2:
                        player = "DTOS-P-" + str(selected["player_id"])
                        move.update(
                            selected_player_id=player,
                            selected_player_label=label(player),
                            selected_player_url=asset_url(player),
                        )
                        queue.append((player, high, depth + 1, expected_owner))
                    else:
                        limits.append(
                            "Draft conversion identity unavailable; continuation withheld."
                        )
                movements.append(move)
        if not root:
            limits.append(
                "Original trade time unavailable; no exact subsequent chronology asserted."
            )
        if not budget or len(summary) > MAX_ASSETS:
            limits.append(
                "Timeline limit reached; open an individual asset or later trade for more evidence."
            )
        converted = any(m.get("selected_player_id") for m in movements)
        current_owner = None if converted else observed_owner(asset)
        current_team = next(
            (t for t in graph.current_data.get("teams") or ()
             if current_owner == f"{graph.league_id}:franchise:{t.get('roster_id')}"),
            {},
        )
        branches.append(
            {
                "asset_id": asset,
                "label": label(asset),
                "url": asset_url(asset),
                "sent_by": [franchise(f, dossier["season"]) for f in outgoing],
                "received_by": [franchise(f, dossier["season"]) for f in incoming],
                "events": movements,
                "current_observed_owner": current_owner,
                "current_observed_owner_name": current_team.get("team_name") or current_team.get("owner"),
                "state": "Converted into confirmed drafted player"
                if converted
                else "Current owner observed"
                if current_owner
                else "Current ownership not confirmed by available source facts",
                "limitations": sorted(set(limits)),
            }
        )
    return {
        "league_id": graph.league_id,
        "league_name": (graph.current_data.get("league") or {}).get("name")
        or "Selected league",
        "season": dossier["season"],
        "trade_id": dossier["trade_id"],
        "occurred_at": dossier.get("occurred_at"),
        "branches": branches,
        "participants": [
            franchise(f, dossier["season"]) for f in dossier["participating_franchises"]
        ],
        "event_limit": MAX_EVENTS,
        "events_rendered": MAX_EVENTS - budget,
        "limitations": [
            "Prepared source coverage is partial; an absent event is not proof of no movement.",
            "Manager identities are season observations, not exact takeover dates.",
            "No trade winner, championship causality or descendant-value allocation is calculated.",
        ],
    }
