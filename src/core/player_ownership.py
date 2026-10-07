"""League player ownership and supported actions from one prepared roster map.

Uses the league snapshot already accepted by the context boundary. It neither
fetches evidence nor changes its freshness policy or canonical Market prices.
"""
from __future__ import annotations

from hashlib import sha256
import json


def _roster_id(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class PlayerOwnershipIndex:
    def __init__(self, data: dict):
        self.players = data.get("players") or {}
        self.owners: dict[str, list[dict]] = {}
        teams = data.get("teams") or []
        self.rosters = {_roster_id(team.get("roster_id")) for team in teams}
        expected = (data.get("league") or {}).get("total_rosters")
        self.complete = bool(teams) and 0 not in self.rosters and len(self.rosters) == len(teams)
        if expected is not None:
            self.complete = self.complete and len(teams) == _roster_id(expected)
        snapshot = []
        for team in teams:
            roster_id = _roster_id(team.get("roster_id"))
            rows = team.get("players")
            self.complete = self.complete and isinstance(rows, list)
            members = []
            for player in rows or ():
                player_id = str(player.get("id") or player.get("player_id") or "") if isinstance(player, dict) else str(player)
                if not player_id:
                    self.complete = False
                    continue
                members.append(player_id)
                self.owners.setdefault(player_id, []).append({
                    "roster_id": roster_id, "team_name": team.get("team_name"),
                    "owner": team.get("owner"),
                    "roster_slot": player.get("roster_slot") if isinstance(player, dict) else None,
                })
            snapshot.append((roster_id, team.get("team_name"), team.get("owner"), sorted(members)))
        self.generation = sha256(json.dumps((
            (data.get("league") or {}).get("league_id"), self.complete, sorted(snapshot),
        ), separators=(",", ":")).encode()).hexdigest()

    def resolve(self, player_id: str, active_roster_id: int | None = None) -> dict:
        owners = self.owners.get(str(player_id), [])
        owner = None
        reason = None
        actions = ["VIEW_PLAYER"]
        if not self.complete:
            state, label = "UNKNOWN", "Ownership unavailable"
            reason = "Current league roster evidence is incomplete."
        elif str(player_id) not in self.players:
            state, label = "UNKNOWN", "Ownership unavailable"
            reason = "Player identity is unresolved in the current league context."
        elif len(owners) > 1:
            state, label = "UNKNOWN", "Ownership unavailable"
            reason = "Current league roster evidence has conflicting player ownership."
        elif not owners:
            state, label = "FREE_AGENT", "Free Agent · Unrostered in this league"
            reason = "Free agents have no owning franchise to trade with."
        else:
            owner = owners[0]
            mine = owner["roster_id"] == active_roster_id
            state = "OWNED_BY_ME" if mine else "OWNED_BY_OTHER"
            label = "My Team" if mine else str(owner.get("team_name") or owner.get("owner") or f'Roster {owner["roster_id"]}')
            if active_roster_id in self.rosters:
                actions.append("SHOP_ASSET" if mine else "TRADE_FOR")
        return {"state": state, "label": label, "owner": owner,
                "reason": reason, "actions": actions, "generation": self.generation}


def targeted_player_action(data: dict, player_id: str, active_roster_id: int) -> dict | None:
    """Only players use these capabilities; exact picks keep their own boundary."""
    player_id = str(player_id).removeprefix("player:")
    if player_id not in (data.get("players") or {}):
        return None
    return PlayerOwnershipIndex(data).resolve(player_id, active_roster_id)
