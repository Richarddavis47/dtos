"""Evidence-gated league badges. Presentation only; no inferred standings."""

from html import escape

from src.platform.account_context import current_account


def explained_badge(label: str, explanation: str, kind: str) -> str:
    return (
        f'<details class="ds-badge-detail" data-badge="{escape(kind)}">'
        f"<summary>{escape(label)}</summary><p>{escape(explanation)}</p></details>"
    )


def you_badge(data: dict, roster_id: int) -> str:
    account = current_account()
    membership = account.membership if account else None
    league_id = str((data.get("league") or {}).get("league_id") or "")
    if (
        not membership
        or membership.league_id != league_id
        or membership.roster_id != roster_id
    ):
        return ""
    return '<span class="ds-badge ds-you">You</span>'


def position_chip(position: str | None) -> str:
    if position not in {"QB", "RB", "WR", "TE"}:
        return ""
    return f'<span class="ds-position" data-position="{position}">{position}</span>'


def official_ranks(data: dict) -> dict[int, int]:
    """Accept only a complete, unique Sleeper-reported rank set, never sort records."""
    from src.ui.intelligence_presentation import league_is_preseason

    teams = data.get("teams") or []
    if not teams or league_is_preseason(data):
        return {}
    ranks = [team.get("official_standing_rank") for team in teams]
    if any(type(rank) is not int for rank in ranks) or set(ranks) != set(
        range(1, len(teams) + 1)
    ):
        return {}
    return {int(team["roster_id"]): rank for team, rank in zip(teams, ranks)}


def standing_badge(rank: int | None) -> str:
    if rank is None:
        return ""
    medal = {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)
    return explained_badge(
        f"{ {1: '🥇', 2: '🥈', 3: '🥉'}.get(rank, '')} #{rank}",
        f"Official Sleeper league standings: place {rank}. "
        + (f"{medal} marks this official placement." if medal else ""),
        f"standing-{rank}",
    )


def movement_badge(
    current: int | None, previous: int | None, period: str | None
) -> str:
    if (
        not period
        or type(current) is not int
        or type(previous) is not int
        or min(current, previous) < 1
    ):
        return ""
    change = previous - current
    if not change:
        return ""
    return explained_badge(
        ("↑" if change > 0 else "↓") + str(abs(change)),
        f"Official standings movement over {period}: #{previous} to #{current}. Not a win/loss streak.",
        "movement",
    )


def streak_badge(results: list[str], period: str | None) -> str:
    """Only an explicitly completed, ordered result sequence supports a streak."""
    if (
        not period
        or not results
        or results[-1] not in {"W", "L"}
        or any(row not in {"W", "L", "T"} for row in results)
    ):
        return ""
    last, count = results[-1], 0
    for row in reversed(results):
        if row != last:
            break
        count += 1
    return explained_badge(
        f"{last}{count}",
        f"{count} consecutive {'wins' if last == 'W' else 'losses'} in {period}. Not rank movement.",
        "streak",
    )


def defending_champion(data: dict, cache=None) -> tuple[int, int] | None:
    """Use the active league's immediately preceding completed season bracket."""
    from src.core.history_context.playoffs import playoff_facts

    if cache is None:
        from services.history import sleeper_season_cache

        cache = sleeper_season_cache
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or "")
    try:
        season = int(league["season"]) - 1
        if not league_id:
            return None
        historical = cache.section(league_id, season, "league") or {}
        if historical.get("status") != "complete" or str(
            historical.get("season")
        ) != str(season):
            return None
        result = playoff_facts(
            cache.section(league_id, season, "winners_bracket") or []
        )
        champion = int(result.get("champion_roster_id") or 0)
        finalist = int(result.get("runner_up_roster_id") or 0)
        if (
            not champion
            or not finalist
            or champion == finalist
            or {str(champion), str(finalist)} != set(result["championship_roster_ids"])
        ):
            return None
        if champion not in {int(team["roster_id"]) for team in data.get("teams") or []}:
            return None
        return season, champion
    except (OSError, ValueError, KeyError, TypeError):
        # Unavailable/corrupt history never becomes a guessed achievement.
        return None


def champion_badge(champion: tuple[int, int] | None, roster_id: int) -> str:
    if champion is None or champion[1] != roster_id:
        return ""
    return explained_badge(
        "🏆",
        f"{champion[0]} defending champion. Basis: the completed season’s Sleeper winners-bracket championship result for this league.",
        "champion",
    )
