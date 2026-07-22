"""League-relative, valuation-backed team grading and classification."""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from src.core.team_intelligence.models import CompetitiveWindow, LeagueTeamSummary, RelativeGrade, TeamIntelligenceCard
from src.core.valuation import normalize_pick

POSITIONS = ("QB", "RB", "WR", "TE")
OVERALL_WEIGHTS = {
    "Current Contending": .22, "Dynasty": .14, "Starting Lineup": .14, "Depth": .09,
    "QB": .07, "RB": .06, "WR": .07, "TE": .05, "Draft Capital": .06,
    "Youth": .04, "Future Outlook": .03, "Roster Flexibility": .02, "Asset Liquidity": .01,
}


def _percentile(value: float, population: tuple[float, ...]) -> int:
    if not population or max(population) == min(population):
        return 50
    below = sum(item < value for item in population)
    equal = sum(item == value for item in population)
    return round((below + equal * .5) / len(population) * 100)


def _letter(percentile: int) -> str:
    for threshold, label in ((90, "A+"), (80, "A"), (65, "A-"), (50, "B+"), (40, "B"), (30, "C"), (20, "D")):
        if percentile >= threshold:
            return label
    return "F"


def _rank(value: float, population: tuple[float, ...]) -> int:
    return 1 + sum(item > value for item in population)


def _relative(category: str, roster_id: int, raw: dict[int, dict[str, float]], reasons: tuple[str, ...]) -> RelativeGrade:
    value = raw[roster_id][category]
    population = tuple(row[category] for row in raw.values())
    percentile = _percentile(value, population)
    return RelativeGrade(category, percentile, _letter(percentile), percentile, _rank(value, population), len(population), reasons)


def _window(current: int, overall: int, future: int) -> CompetitiveWindow:
    if current >= 85 and overall >= 80:
        return CompetitiveWindow.ELITE_CONTENDER
    if current >= 70 and overall >= 65:
        return CompetitiveWindow.CONTENDER
    if current >= 52:
        return CompetitiveWindow.PLAYOFF_TEAM
    if current < 25 and future < 35:
        return CompetitiveWindow.FULL_REBUILD
    if current < 40:
        return CompetitiveWindow.REBUILDING
    return CompetitiveWindow.RETOOLING


def _pick_value(picks: tuple[dict[str, Any], ...]) -> float:
    return sum(normalize_pick({1: 82, 2: 64, 3: 48, 4: 36}.get(int(pick.get("round") or 4), 25), int(pick.get("round") or 4)) for pick in picks)


def build_team_intelligence(
    decisions: dict[int, Any],
    league_rooms: dict[int, dict[str, int]],
    league_players: dict[int, dict[str, Any]],
    league_metrics: dict[int, dict[str, float]],
) -> tuple[dict[int, TeamIntelligenceCard], LeagueTeamSummary]:
    raw: dict[int, dict[str, float]] = {}
    preseason = all(decision.profile.wins + decision.profile.losses + decision.profile.ties == 0 for decision in decisions.values())
    for roster_id, decision in decisions.items():
        players = tuple(league_players.get(roster_id, {}).values())
        metrics = league_metrics[roster_id]
        starters = [player for player in decision.profile.players if player.get("roster_slot") == "Starter"]
        bench_count = max(0, len(players) - len(starters))
        room_average = mean(league_rooms[roster_id].values()) if league_rooms[roster_id] else 0
        bench_quality = mean(sorted((card.dynasty_value for card in players), reverse=True)[len(starters):len(starters) + 5]) if bench_count else 0
        ages = [float(player.get("age")) for player in decision.profile.players if player.get("age") is not None]
        youth_assets = [card.rebuilder_value for card in players if next((float(row.get("age")) for row in decision.profile.players if str(row.get("id") or row.get("player_id")) == card.player_id and row.get("age") is not None), 99) <= 24]
        pick_value = _pick_value(decision.profile.picks)
        current = metrics["Starting-Lineup Dynasty Value"] * .55 + metrics["Contender Value"] * .25 + room_average * 10 * .20
        dynasty = metrics["Total Dynasty Value"] * .60 + metrics["Rebuild Value"] * .40
        depth = bench_quality * .65 + room_average * .35
        youth = mean(youth_assets) if youth_assets else 0
        flexibility = metrics["Market Liquidity"] * .65 + pick_value / max(1, len(decision.profile.picks)) * .035
        raw[roster_id] = {
            "Current Contending": current,
            "Dynasty": dynasty,
            "Starting Lineup": metrics["Starting-Lineup Dynasty Value"],
            "Depth": depth,
            **league_rooms[roster_id],
            "Draft Capital": pick_value,
            "Youth": youth,
            "Future Outlook": dynasty * .75 + pick_value * .25,
            "Roster Flexibility": flexibility,
            "Asset Liquidity": metrics["Market Liquidity"],
            "Average Age": mean(ages) if ages else 0,
        }
    category_percentiles = {roster_id: {category: _percentile(values[category], tuple(row[category] for row in raw.values())) for category in OVERALL_WEIGHTS} for roster_id, values in raw.items()}
    for roster_id in raw:
        raw[roster_id]["Overall"] = sum(category_percentiles[roster_id][category] * weight for category, weight in OVERALL_WEIGHTS.items())
    cards: dict[int, TeamIntelligenceCard] = {}
    for roster_id, decision in decisions.items():
        def grade(category: str, reasons: tuple[str, ...]) -> RelativeGrade:
            return _relative(category, roster_id, raw, reasons)
        positions = {position: grade(position, (f"{position} room uses top-end quality, weekly leverage, longevity, market value, and depth.", f"Raw room strength {league_rooms[roster_id][position]}/100 before league-relative ranking.")) for position in POSITIONS}
        current = grade("Current Contending", ("Starting-lineup value supplies 55% of the raw current-strength input.", "Contender values supply 25%; league-relative position-room strength supplies 20%.", "Record is excluded before completed games exist."))
        dynasty = grade("Dynasty", ("Normalized DTOS dynasty and rebuild values are aggregated with diminishing roster depth already applied by Roster Intelligence.",))
        lineup = grade("Starting Lineup", ("Only designated starters contribute to the starting-lineup value total.",))
        depth = grade("Depth", ("Bench quality is capped to the next five assets; extra replacement-level bodies receive no equal credit.",))
        draft = grade("Draft Capital", (f"{decision.profile.draft_pick_count} owned picks are valued on the canonical DTOS pick scale by round and horizon.",))
        youth = grade("Youth", (f"{decision.profile.young_player_count} players age 24 or younger; young-asset quality matters more than count.",))
        future = grade("Future Outlook", ("Dynasty roster strength and normalized draft capital are evaluated independently from current results.",))
        flexibility = grade("Roster Flexibility", ("Market liquidity and usable draft capital determine optionality.",))
        liquidity = grade("Asset Liquidity", ("Average traceable trade liquidity comes from shared Asset and Market Intelligence.",))
        overall = grade("Overall", ())
        ordered = sorted((current, dynasty, lineup, depth, draft, youth, future, flexibility, liquidity, *positions.values()), key=lambda item: (-item.percentile, item.category))
        explanation = (f"Strongest relative area: {ordered[0].category} ({ordered[0].grade}, #{ordered[0].rank}).", f"Lowest relative area: {ordered[-1].category} ({ordered[-1].grade}, #{ordered[-1].rank}).", "Overall combines category percentiles; no 0–1000 player value is treated as a 0–100 grade.")
        confidence = round(mean((decision.current_outlook.confidence, decision.future_outlook.confidence, decision.depth.confidence, decision.asset_health.confidence)))
        risk = max(0, min(100, round(100 - mean((current.percentile, dynasty.percentile, flexibility.percentile)))))
        window = _window(current.percentile, overall.percentile, future.percentile)
        playoff_odds = max(5, min(95, round(current.percentile * .8 + 10)))
        championship_odds = max(1, min(60, round(current.percentile * .35 + overall.percentile * .25 - 10)))
        projected_wins = round(playoff_odds / 100 * 14, 1)
        cards[roster_id] = TeamIntelligenceCard(
            roster_id, overall, current, dynasty, lineup, depth, positions, draft, youth,
            future, flexibility, liquidity, window, current.percentile, future.percentile,
            risk, confidence, explanation, preseason, overall.rank, projected_wins,
            playoff_odds, championship_odds,
        )
    overall_scores = [card.overall.score for card in cards.values()]
    all_ages = [age for decision in decisions.values() for age in decision.profile.known_ages]
    strongest = max(((grade.score, roster_id, position) for roster_id, card in cards.items() for position, grade in card.positions.items()), default=(0, 0, "Unavailable"))
    weakest = min(((grade.score, roster_id, position) for roster_id, card in cards.items() for position, grade in card.positions.items()), default=(0, 0, "Unavailable"))
    def best(attribute: str) -> int | None:
        return min(cards.values(), key=lambda card: (getattr(card, attribute).rank, card.roster_id)).roster_id if cards else None

    def worst(attribute: str) -> int | None:
        return max(cards.values(), key=lambda card: (getattr(card, attribute).rank, -card.roster_id)).roster_id if cards else None
    age_rows = [(mean(decision.profile.known_ages), roster_id) for roster_id, decision in decisions.items() if decision.profile.known_ages]
    absolute_league_strength = round(mean(score for rooms in league_rooms.values() for score in rooms.values())) if league_rooms else 0
    summary = LeagueTeamSummary(absolute_league_strength, round(mean(all_ages), 1) if all_ages else None, round(mean(overall_scores), 1) if overall_scores else 0, sum(card.current_window in {CompetitiveWindow.ELITE_CONTENDER, CompetitiveWindow.CONTENDER} for card in cards.values()), sum(card.current_window in {CompetitiveWindow.REBUILDING, CompetitiveWindow.FULL_REBUILD} for card in cards.values()), f"Team {strongest[1]} {strongest[2]}", f"Team {weakest[1]} {weakest[2]}", max(0, min(100, round(100 - pstdev(overall_scores) * 2))) if len(overall_scores) > 1 else 100, min(cards.values(), key=lambda card: (card.overall.rank, card.roster_id)).roster_id if cards else None, "Unavailable without prior team-grade snapshots", "Unavailable without prior team-grade snapshots", best("draft_capital"), worst("draft_capital"), best("roster_flexibility"), max(age_rows, default=(0, None))[1], min(age_rows, default=(0, None))[1], "Preseason Projection" if preseason else "Current Season")
    return cards, summary
