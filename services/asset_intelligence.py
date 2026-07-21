"""Application-facing Asset Intelligence context assembly."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.core.intelligence import intelligence_orchestrator


def player_asset_index(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the canonical, stable index of cached rostered player dossiers."""
    database = data.get("players") or {}
    ownership: dict[str, list[int]] = {}
    roster_rows: dict[str, dict[str, Any]] = {}
    for team in data.get("teams") or []:
        roster_id = int(team.get("roster_id") or 0)
        for player in team.get("players") or []:
            player_id = str(player.get("id") or "").strip()
            if not player_id:
                continue
            ownership.setdefault(player_id, []).append(roster_id)
            roster_rows.setdefault(player_id, player)
    index = []
    for player_id in sorted(ownership):
        details = database.get(player_id) or {}
        roster = roster_rows[player_id]
        name = details.get("full_name") or roster.get("name") or player_id
        index.append({
            "player_id": player_id,
            "name": str(name),
            "position": str(details.get("position") or roster.get("position") or "Unknown"),
            "nfl_team": str(details.get("team") or roster.get("team") or "Free Agent"),
            "roster_ids": sorted(set(ownership[player_id])),
            "dossier_url": f"/players/{quote(player_id, safe='')}",
        })
    return index


def _team(data: dict[str, Any], roster_id: int | None, player_id: str | None = None) -> dict[str, Any]:
    teams = data.get("teams") or []
    if roster_id is not None:
        selected = next((team for team in teams if int(team.get("roster_id") or 0) == roster_id), None)
        if selected is not None:
            return selected
    if player_id:
        owner = next((team for team in teams if any(str(player.get("id")) == player_id for player in team.get("players") or [])), None)
        if owner is not None:
            return owner
    if not teams:
        raise ValueError("No Front Office is available for contextual asset evaluation.")
    return teams[0]


def build_player_dossier(data: dict[str, Any], player_id: str, roster_id: int | None = None) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
    player = (data.get("players") or {}).get(player_id)
    if not player:
        raise ValueError("Player not found")
    team = _team(data, roster_id, player_id)
    report = intelligence_orchestrator.player_report(data, {**player, "id": player_id}, int(team.get("roster_id") or 0))
    return report, team, list(data.get("teams") or [])


def build_pick_intelligence(data: dict[str, Any], pick: dict[str, Any], roster_id: int | None = None) -> Any:
    owner_id = roster_id or pick.get("current_owner_id") or pick.get("owner_id")
    team = _team(data, int(owner_id) if owner_id is not None else None)
    enriched = {
        **pick,
        "original_team": pick.get("original_team") or next(
            (item.get("team_name") for item in data.get("teams") or [] if int(item.get("roster_id") or 0) == int(pick.get("roster_id") or 0)),
            "Unknown",
        ),
    }
    return intelligence_orchestrator.pick_report(data, enriched, int(team.get("roster_id") or 0))


def build_pick_reports(data: dict[str, Any], picks: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Any]]:
    """Evaluate a ledger through cached orchestrator contexts per current owner."""
    reports: list[tuple[dict[str, Any], Any]] = []
    for pick in picks:
        owner_id = int(pick.get("current_owner_id") or pick.get("owner_id") or 0)
        team = _team(data, owner_id or None)
        enriched = {
            **pick,
            "original_team": next(
                (item.get("team_name") for item in data.get("teams") or [] if int(item.get("roster_id") or 0) == int(pick.get("roster_id") or 0)),
                "Unknown",
            ),
        }
        reports.append((pick, intelligence_orchestrator.pick_report(data, enriched, int(team.get("roster_id") or 0))))
    return reports
