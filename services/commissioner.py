"""Deterministic Commissioner Desk briefing and intelligence service."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from models.commissioner import (
    ActiveFrontOffice,
    ActiveLeague,
    DailyBriefing,
    LeagueEvent,
    LeagueEventType,
    LeagueHeadline,
)
from src.core.intelligence import intelligence_orchestrator
from services.transactions import normalize_transactions


def _parse_since(value: str | None) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(hours=24)


def _league_contexts(data: dict[str, Any], configured_league_id: str) -> list[ActiveLeague]:
    league = data.get("league") or {}
    return [
        ActiveLeague(
            league_id=str(league.get("league_id") or configured_league_id),
            name=str(league.get("name") or "Sleeper League"),
            season=str(league.get("season") or "Unknown"),
        )
    ]


def _front_offices(data: dict[str, Any]) -> list[ActiveFrontOffice]:
    return [
        ActiveFrontOffice(
            roster_id=int(team.get("roster_id") or 0),
            owner_id=str(team.get("owner_id") or ""),
            owner_name=str(team.get("owner") or "Unassigned"),
            team_name=str(team.get("team_name") or f"Team {team.get('roster_id')}"),
        )
        for team in data.get("teams") or []
    ]


def _event_detail(transaction: dict[str, Any]) -> str:
    assets = [str(asset.get("label")) for asset in transaction.get("assets") or []]
    teams = [str(team.get("team_name")) for team in transaction.get("teams") or []]
    detail = ", ".join(assets[:5]) or "No asset detail is available."
    if len(assets) > 5:
        detail += f" and {len(assets) - 5} more"
    return f"{' / '.join(teams) or 'League transaction'}: {detail}"


def _briefing(data: dict[str, Any], since: datetime) -> DailyBriefing:
    events: list[LeagueEvent] = []
    for transaction in normalize_transactions(data):
        occurred_ms = int(transaction.get("created_ms") or 0)
        if occurred_ms < int(since.timestamp() * 1000):
            continue
        roster_ids = tuple(
            int(team["roster_id"])
            for team in transaction.get("teams") or []
            if str(team.get("roster_id") or "").isdigit()
        )
        tx_type = transaction.get("type")
        event_type = {
            "trade": LeagueEventType.TRADE,
            "waiver": LeagueEventType.WAIVER,
        }.get(tx_type, LeagueEventType.LEAGUE)
        events.append(
            LeagueEvent(
                event_type=event_type,
                occurred_at=str(transaction.get("timestamp") or "Unknown time"),
                occurred_ms=occurred_ms,
                title=str(transaction.get("type_label") or "Transaction"),
                detail=_event_detail(transaction),
                roster_ids=roster_ids,
                source_id=str(transaction.get("id") or "") or None,
            )
        )
        if transaction.get("add_count"):
            events.append(
                LeagueEvent(
                    LeagueEventType.ADD,
                    str(transaction.get("timestamp") or "Unknown time"),
                    occurred_ms,
                    f"{transaction['add_count']} player add{'s' if transaction['add_count'] != 1 else ''}",
                    _event_detail(transaction),
                    roster_ids,
                    str(transaction.get("id") or "") or None,
                )
            )
        if transaction.get("drop_count"):
            events.append(
                LeagueEvent(
                    LeagueEventType.DROP,
                    str(transaction.get("timestamp") or "Unknown time"),
                    occurred_ms,
                    f"{transaction['drop_count']} player drop{'s' if transaction['drop_count'] != 1 else ''}",
                    _event_detail(transaction),
                    roster_ids,
                    str(transaction.get("id") or "") or None,
                )
            )
        if transaction.get("has_draft_pick"):
            events.append(
                LeagueEvent(
                    LeagueEventType.DRAFT_PICK,
                    str(transaction.get("timestamp") or "Unknown time"),
                    occurred_ms,
                    "Draft pick ownership changed",
                    _event_detail(transaction),
                    roster_ids,
                    str(transaction.get("id") or "") or None,
                )
            )
    events.sort(key=lambda event: event.occurred_ms, reverse=True)
    counts = Counter(event.event_type.value for event in events)
    return DailyBriefing(
        since_label=since.strftime("%Y-%m-%d %H:%M UTC"),
        events=tuple(events[:30]),
        counts=dict(counts),
        unavailable=(
            "Standings movement requires a prior standings snapshot.",
            "Injury changes require historical injury snapshots.",
            "Matchup results do not include a reliable completion timestamp in the current cache.",
            "League records and custom events require a future league-history source.",
        ),
    )


def _team_average_age(data: dict[str, Any], team: dict[str, Any]) -> float | None:
    player_database = data.get("players") or {}
    ages = []
    for player in team.get("players") or []:
        details = player_database.get(str(player.get("id")), {}) if isinstance(player_database, dict) else {}
        age = player.get("age") if player.get("age") is not None else details.get("age")
        try:
            if age is not None:
                ages.append(float(age))
        except (TypeError, ValueError):
            continue
    return round(mean(ages), 1) if ages else None


def _headlines(data: dict[str, Any]) -> list[LeagueHeadline]:
    teams = data.get("teams") or []
    headlines: list[LeagueHeadline] = []
    if teams:
        leader = teams[0]
        leading_mark = (
            leader.get("wins", 0),
            leader.get("losses", 0),
            leader.get("ties", 0),
            leader.get("points_for", 0),
        )
        tied_leaders = [
            team
            for team in teams
            if (
                team.get("wins", 0),
                team.get("losses", 0),
                team.get("ties", 0),
                team.get("points_for", 0),
            ) == leading_mark
        ]
        if len(tied_leaders) == 1:
            headlines.append(
                LeagueHeadline(
                    f"{leader.get('team_name')} leads the current standings",
                    f"{leader.get('owner')} is ranked first at {leader.get('wins', 0)}-{leader.get('losses', 0)}-{leader.get('ties', 0)}.",
                    "Current cached Sleeper standings order, record, and points for.",
                    "Standings",
                )
            )
        else:
            headlines.append(
                LeagueHeadline(
                    "The current standings leaders are level",
                    f"{len(tied_leaders)} franchises share the leading record and points-for mark.",
                    "Current cached Sleeper records and points for.",
                    "Standings",
                )
            )
    ages = [(age, team) for team in teams if (age := _team_average_age(data, team)) is not None]
    if ages:
        youngest_age, youngest = min(ages, key=lambda item: (item[0], str(item[1].get("team_name"))))
        youngest_count = sum(age == youngest_age for age, _ in ages)
        headlines.append(
            LeagueHeadline(
                f"{youngest.get('team_name')} {'is tied for' if youngest_count > 1 else 'has'} the youngest measured roster",
                f"Average age is {youngest_age} across players with known ages.",
                "Sleeper player ages for currently rostered players; unknown ages are excluded.",
                "Roster",
            )
        )
    normalized = normalize_transactions(data)
    activity = Counter()
    for transaction in normalized:
        for team in transaction.get("teams") or []:
            activity[str(team.get("team_name"))] += 1
    if activity:
        name, count = sorted(activity.items(), key=lambda item: (-item[1], item[0]))[0]
        active_count = sum(value == count for value in activity.values())
        headlines.append(
            LeagueHeadline(
                f"{name} {'is tied as' if active_count > 1 else 'is'} the most active team in the cached transaction window",
                f"The franchise appears in {count} transactions.",
                "Current cached Sleeper transaction participation.",
                "Activity",
            )
        )
    if teams:
        pick_leader = sorted(
            teams,
            key=lambda team: (-len(team.get("picks_owned") or []), str(team.get("team_name"))),
        )[0]
        pick_count = len(pick_leader.get("picks_owned") or [])
        pick_leader_count = sum(len(team.get("picks_owned") or []) == pick_count for team in teams)
        headlines.append(
            LeagueHeadline(
                f"{pick_leader.get('team_name')} {'is tied for' if pick_leader_count > 1 else 'holds'} the largest future-pick inventory",
                f"The franchise owns {pick_count} future picks.",
                "Current complete future-pick ledger.",
                "Draft Capital",
            )
        )
    return headlines[:5]


def _league_intelligence(data: dict[str, Any], cards: dict[int, Any], league_summary: Any) -> dict[str, Any]:
    teams = data.get("teams") or []
    ages = [age for team in teams if (age := _team_average_age(data, team)) is not None]
    total_picks = sum(len(team.get("picks_owned") or []) for team in teams)
    pick_leader = max((len(team.get("picks_owned") or []) for team in teams), default=0)
    windows = Counter(card.current_window.value for card in cards.values())
    transactions = normalize_transactions(data)
    return {
        "average_roster_age": round(mean(ages), 1) if ages else None,
        "draft_concentration": round(pick_leader / total_picks * 100) if total_picks else None,
        "recent_activity": len(transactions),
        "average_team_grade": league_summary.average_team_grade,
        "league_strength": league_summary.league_strength,
        "league_parity": league_summary.parity_score,
        "contenders": sum(windows[name] for name in ("Elite Contender", "Contender")),
        "rebuilders": sum(windows[name] for name in ("Rebuilding", "Full Rebuild")),
        "strongest_position": league_summary.strongest_position_group,
        "weakest_position": league_summary.weakest_position_group,
        "championship_favorite": league_summary.championship_favorite,
        "most_draft_capital": league_summary.most_draft_capital,
        "least_draft_capital": league_summary.least_draft_capital,
        "most_flexible_roster": league_summary.most_flexible_roster,
        "oldest_team": league_summary.oldest_team,
        "youngest_team": league_summary.youngest_team,
        "trending_up": "Unavailable without historical snapshots",
        "trending_down": "Unavailable without historical snapshots",
    }


def build_commissioner_desk(
    data: dict[str, Any],
    configured_league_id: str,
    active_league_id: str | None = None,
    active_roster_id: int | None = None,
    since: str | None = None,
    last_sync: Any = None,
    last_error: Any = None,
) -> dict[str, Any]:
    """Build a complete presentation-neutral Commissioner Desk view model."""
    leagues = _league_contexts(data, configured_league_id)
    selected_league = next((league for league in leagues if league.league_id == active_league_id), leagues[0])
    front_offices = _front_offices(data)
    if not front_offices:
        raise ValueError("Commissioner Desk requires at least one league franchise.")
    selected_front_office = next(
        (office for office in front_offices if office.roster_id == active_roster_id),
        front_offices[0],
    )
    selected_team = next(
        team
        for team in data.get("teams") or []
        if int(team.get("roster_id") or 0) == selected_front_office.roster_id
    )
    intelligence = intelligence_orchestrator.analyze(data, selected_front_office.roster_id)
    decision = intelligence.decision
    team_card = intelligence.roster.team_intelligence[selected_front_office.roster_id]
    since_time = _parse_since(since)
    summary = {
        "current_outlook": team_card.current_contending,
        "future_outlook": team_card.future_outlook,
        "depth": decision.depth,
        "asset_health": decision.asset_health,
        "competitive_window": team_card.current_window.value,
        "window_explanation": " ".join(team_card.explanation),
        "record": f"{selected_team.get('wins', 0)}-{selected_team.get('losses', 0)}-{selected_team.get('ties', 0)}",
        "power_ranking": team_card.overall.rank,
        "team_intelligence": team_card,
    }
    normalized = normalize_transactions(data)
    return {
        "leagues": leagues,
        "active_league": selected_league,
        "front_offices": front_offices,
        "active_front_office": selected_front_office,
        "briefing": _briefing(data, since_time),
        "headlines": _headlines(data),
        "front_office_summary": summary,
        "recommendations": decision.recommendations,
        "unified_recommendation": intelligence.recommendation,
        "league_opportunity": intelligence.league,
        "league_intelligence": _league_intelligence(data, intelligence.roster.team_intelligence, intelligence.roster.league_summary),
        "snapshot": {
            "standings": sorted(data.get("teams") or [], key=lambda team: intelligence.roster.team_intelligence[int(team.get("roster_id") or 0)].overall.rank),
            "season_label": intelligence.roster.league_summary.season_label,
            "transactions": normalized[:5],
            "matchups": data.get("matchups") or {},
            "leader": (data.get("teams") or [None])[0],
            "health": {
                "status": "Degraded" if last_error else "Healthy",
                "last_sync": str(last_sync or "Never"),
                "error": str(last_error) if last_error else None,
            },
        },
    }
