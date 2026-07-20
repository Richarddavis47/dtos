"""Transaction normalization, filtering, sorting, and pagination."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from math import ceil
from typing import Any


SORT_FIELDS = {"date", "type", "teams", "assets", "id"}
PAGE_SIZES = {10, 25, 50}


def _player_name(player_id: str, players: dict[str, Any]) -> str:
    player = players.get(player_id) or {}
    return (
        player.get("full_name")
        or " ".join(
            part for part in (player.get("first_name"), player.get("last_name")) if part
        )
        or player_id
    )


def _team_label(roster_id: str | int | None, teams: dict[str, dict[str, Any]]) -> str:
    key = str(roster_id or "")
    return str((teams.get(key) or {}).get("team_name") or f"Team {key or '?'}")


def _team_owner(roster_id: str | int | None, teams: dict[str, dict[str, Any]]) -> str:
    return str((teams.get(str(roster_id or "")) or {}).get("owner") or "Unassigned")


def _player_asset(
    player_id: str,
    source_id: str | None,
    destination_id: str | None,
    players: dict[str, Any],
    teams: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    player = players.get(player_id) or {}
    if source_id and destination_id and source_id != destination_id:
        action = "Moved"
    elif destination_id:
        action = "Added"
    else:
        action = "Dropped"
    return {
        "kind": "player",
        "action": action,
        "player_id": player_id,
        "label": _player_name(player_id, players),
        "position": str(player.get("position") or "—"),
        "nfl_team": str(player.get("team") or "FA"),
        "source_id": source_id,
        "source": _team_label(source_id, teams) if source_id else None,
        "destination_id": destination_id,
        "destination": _team_label(destination_id, teams) if destination_id else None,
    }


def _pick_asset(
    pick: dict[str, Any], teams: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    source_id = str(pick.get("previous_owner_id") or "") or None
    destination_id = str(pick.get("owner_id") or "") or None
    original_id = str(pick.get("roster_id") or "") or None
    season = str(pick.get("season") or "Future")
    round_number = str(pick.get("round") or "?")
    return {
        "kind": "pick",
        "action": "Draft pick",
        "label": f"{season} Round {round_number}",
        "position": "PICK",
        "player_id": None,
        "source_id": source_id,
        "source": _team_label(source_id, teams) if source_id else None,
        "destination_id": destination_id,
        "destination": _team_label(destination_id, teams) if destination_id else None,
        "original": _team_label(original_id, teams) if original_id else None,
    }


def normalize_transactions(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Sleeper transaction payloads into presentation-ready records."""
    players = data.get("players") or {}
    teams = {
        str(team.get("roster_id")): team for team in (data.get("teams") or [])
    }
    normalized: list[dict[str, Any]] = []

    for raw in data.get("transactions") or []:
        adds = {str(key): str(value) for key, value in (raw.get("adds") or {}).items()}
        drops = {
            str(key): str(value) for key, value in (raw.get("drops") or {}).items()
        }
        assets = [
            _player_asset(
                player_id,
                drops.get(player_id),
                adds.get(player_id),
                players,
                teams,
            )
            for player_id in sorted(set(adds) | set(drops))
        ]
        assets.extend(
            _pick_asset(pick, teams) for pick in (raw.get("draft_picks") or [])
        )

        roster_ids = {
            str(roster_id)
            for roster_id in (
                list(raw.get("roster_ids") or [])
                + list(adds.values())
                + list(drops.values())
            )
        }
        for pick in raw.get("draft_picks") or []:
            roster_ids.update(
                str(roster_id)
                for roster_id in (
                    pick.get("owner_id"),
                    pick.get("previous_owner_id"),
                )
                if roster_id is not None
            )
        roster_ids.discard("")
        involved_teams = [
            {
                "roster_id": roster_id,
                "team_name": _team_label(roster_id, teams),
                "owner": _team_owner(roster_id, teams),
            }
            for roster_id in sorted(roster_ids, key=lambda value: int(value))
        ]

        created_ms = int(raw.get("created") or 0)
        created_at = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            if created_ms
            else None
        )
        transaction_type = str(raw.get("type") or "transaction")
        type_label = transaction_type.replace("_", " ").title()
        transaction_id = str(raw.get("transaction_id") or "")
        player_ids = sorted(set(adds) | set(drops))
        player_names = [_player_name(player_id, players) for player_id in player_ids]
        pick_labels = [asset["label"] for asset in assets if asset["kind"] == "pick"]
        search_values = [
            transaction_id,
            transaction_type,
            type_label,
            str(raw.get("status") or ""),
            *(team["team_name"] for team in involved_teams),
            *(team["owner"] for team in involved_teams),
            *player_ids,
            *player_names,
            *pick_labels,
        ]
        normalized.append(
            {
                "id": transaction_id,
                "type": transaction_type,
                "type_label": type_label,
                "status": str(raw.get("status") or ""),
                "created_ms": created_ms,
                "created_date": created_at.date().isoformat() if created_at else "",
                "timestamp": created_at.strftime("%Y-%m-%d %H:%M UTC")
                if created_at
                else "—",
                "teams": involved_teams,
                "roster_ids": roster_ids,
                "owners": {team["owner"].casefold() for team in involved_teams},
                "assets": assets,
                "player_ids": player_ids,
                "player_names": player_names,
                "has_draft_pick": any(asset["kind"] == "pick" for asset in assets),
                "add_count": len(adds),
                "drop_count": len(drops),
                "search_text": " ".join(search_values).casefold(),
                "raw": raw,
            }
        )
    return normalized


def transaction_summary(
    transactions: list[dict[str, Any]], data: dict[str, Any]
) -> dict[str, Any]:
    """Calculate league-wide transaction activity metrics."""
    activity: Counter[str] = Counter()
    for transaction in transactions:
        activity.update(transaction["roster_ids"])
    team_by_id = {
        str(team.get("roster_id")): team for team in (data.get("teams") or [])
    }
    most_active_id = min(
        activity,
        key=lambda roster_id: (
            -activity[roster_id],
            str((team_by_id.get(roster_id) or {}).get("team_name") or roster_id).casefold(),
        ),
        default="",
    )
    most_active_count = activity.get(most_active_id, 0)
    most_recent = max(
        transactions, key=lambda transaction: transaction["created_ms"], default=None
    )
    return {
        "trades": sum(transaction["type"] == "trade" for transaction in transactions),
        "waivers": sum(transaction["type"] == "waiver" for transaction in transactions),
        "adds": sum(transaction["add_count"] for transaction in transactions),
        "drops": sum(transaction["drop_count"] for transaction in transactions),
        "most_active_team": str(
            (team_by_id.get(most_active_id) or {}).get("team_name") or "—"
        ),
        "most_active_count": most_active_count,
        "most_recent": most_recent["timestamp"] if most_recent else "—",
    }


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def filter_transactions(
    transactions: list[dict[str, Any]], filters: dict[str, Any]
) -> list[dict[str, Any]]:
    """Apply all Transactions Center filters without external API calls."""
    team = str(filters.get("team") or "")
    owner = str(filters.get("owner") or "").casefold()
    transaction_type = str(filters.get("type") or "")
    player = str(filters.get("player") or "").casefold()
    draft_pick = str(filters.get("draft_pick") or "")
    start_date = _parse_date(str(filters.get("date_from") or ""))
    end_date = _parse_date(str(filters.get("date_to") or ""))
    search = str(filters.get("q") or "").casefold().strip()

    filtered = []
    for transaction in transactions:
        created_date = _parse_date(transaction["created_date"])
        if team and team not in transaction["roster_ids"]:
            continue
        if owner and owner not in transaction["owners"]:
            continue
        if transaction_type and transaction_type != transaction["type"]:
            continue
        if player and not any(
            player in value.casefold()
            for value in transaction["player_ids"] + transaction["player_names"]
        ):
            continue
        if draft_pick == "yes" and not transaction["has_draft_pick"]:
            continue
        if draft_pick == "no" and transaction["has_draft_pick"]:
            continue
        if start_date and (not created_date or created_date < start_date):
            continue
        if end_date and (not created_date or created_date > end_date):
            continue
        if search and search not in transaction["search_text"]:
            continue
        filtered.append(transaction)
    return filtered


def sort_transactions(
    transactions: list[dict[str, Any]], sort: str, direction: str
) -> list[dict[str, Any]]:
    """Sort normalized transactions by a supported dashboard column."""
    sort = sort if sort in SORT_FIELDS else "date"
    direction = direction if direction in {"asc", "desc"} else "desc"
    keys = {
        "date": lambda transaction: transaction["created_ms"],
        "type": lambda transaction: transaction["type_label"].casefold(),
        "teams": lambda transaction: " ".join(
            team["team_name"] for team in transaction["teams"]
        ).casefold(),
        "assets": lambda transaction: len(transaction["assets"]),
        "id": lambda transaction: transaction["id"],
    }
    return sorted(transactions, key=keys[sort], reverse=direction == "desc")


def transaction_center(
    data: dict[str, Any], filters: dict[str, Any]
) -> dict[str, Any]:
    """Build the complete cached Transactions Center view model."""
    normalized = normalize_transactions(data)
    filtered = filter_transactions(normalized, filters)
    ordered = sort_transactions(
        filtered, str(filters.get("sort") or "date"), str(filters.get("direction") or "desc")
    )
    page_size = int(filters.get("per_page") or 25)
    page_size = page_size if page_size in PAGE_SIZES else 25
    page_count = max(1, ceil(len(ordered) / page_size))
    page_number = min(max(1, int(filters.get("page") or 1)), page_count)
    start = (page_number - 1) * page_size
    teams = sorted(
        data.get("teams") or [], key=lambda team: str(team.get("team_name") or "").casefold()
    )
    owners = sorted(
        {str(team.get("owner") or "Unassigned") for team in teams}, key=str.casefold
    )
    transaction_types = sorted(
        {transaction["type"] for transaction in normalized}
    )
    return {
        "transactions": ordered[start : start + page_size],
        "total_filtered": len(ordered),
        "total": len(normalized),
        "page": page_number,
        "page_count": page_count,
        "per_page": page_size,
        "summary": transaction_summary(normalized, data),
        "teams": teams,
        "owners": owners,
        "transaction_types": transaction_types,
    }
