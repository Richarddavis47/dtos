"""League-wide opportunity synthesis over existing DTOS intelligence outputs."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.league_intelligence.models import (
    AssetAvailability, GMProfile, LeagueIntelligenceReport, LeagueTradeRecommendation, Opportunity,
    PositionEconomy, TeamDirection, TeamNeed, TeamReport, TeamSurplus, TradeCompatibility,
)

POSITIONS = ("QB", "RB", "WR", "TE")


def _direction(decision: Any, card: Any) -> TeamDirection:
    return TeamDirection(decision.profile.roster_id, card.current_window.value, card.confidence, (f"Current league-relative strength {card.current_strength}/100 (#{card.current_contending.rank}).", f"Future league-relative strength {card.future_strength}/100 (#{card.future_outlook.rank}).", *card.explanation))


def _need(roster_id: int, position: str, room_score: int, cards: list[Any], direction: TeamDirection) -> TeamNeed:
    starter_quality = max((card.contender_value for card in cards), default=0)
    future_quality = max((card.rebuilder_value for card in cards), default=0)
    replacement = max((card.weekly_floor for card in cards), default=0)
    urgency = round((100 - room_score) * .45 + (100 - starter_quality) * .30 + (100 - replacement) * .15 + (10 if direction.label in {"Elite Contender", "Contender"} else (100 - future_quality) * .10))
    priority = "Critical" if urgency >= 72 else "High" if urgency >= 58 else "Medium" if urgency >= 43 else "Low"
    return TeamNeed(roster_id, position, priority, max(0, min(100, urgency)), (f"Quality-first {position} room score is {room_score}/100.", f"Best contender value is {starter_quality}/100; best future value is {future_quality}/100.", f"Direction is {direction.label}; player count is considered only inside the separate depth input."))


def _surplus(roster_id: int, position: str, room_score: int, cards: list[Any], need: TeamNeed) -> TeamSurplus | None:
    tradable = [card for card in cards if card.trade_liquidity >= 55 and card.tier not in {"Elite Franchise Player"}]
    score = round(room_score * .55 + mean((card.trade_liquidity for card in tradable)) * .30 + min(len(tradable), 3) * 5) if tradable else 0
    if score < 62 or need.priority in {"Critical", "High"}:
        return None
    return TeamSurplus(roster_id, position, min(100, score), tuple(card.player_id for card in sorted(tradable, key=lambda item: (-item.trade_liquidity, item.player_id))[:4]), (f"{position} room quality is {room_score}/100.", f"{len(tradable)} liquid non-franchise assets are present.", "Multiple players alone do not create a surplus."))


def _availability(player_id: str, roster_id: int, card: Any, direction: TeamDirection, surplus_positions: set[str], position: str) -> AssetAvailability:
    if card.tier == "Elite Franchise Player":
        status = "Untouchable"
    elif card.tier == "Cornerstone" and direction.label not in {"Rebuilding", "Full Rebuild"}:
        status = "Extremely Difficult"
    elif position in surplus_positions and card.trade_liquidity >= 65:
        status = "Available"
    elif direction.label in {"Rebuilding", "Full Rebuild"} and card.age_curve == "Veteran":
        status = "Actively Shopping"
    elif card.trade_liquidity >= 60:
        status = "Available For Premium"
    else:
        status = "Extremely Difficult"
    return AssetAvailability(player_id, roster_id, status, 65, (f"Asset tier: {card.tier}.", f"Team direction: {direction.label}.", f"Trade liquidity: {card.trade_liquidity}/100.", f"Position surplus: {'yes' if position in surplus_positions else 'no'}."))


def evaluate_league(intelligence: Any) -> LeagueIntelligenceReport:
    roster = intelligence.roster
    directions = {roster_id: _direction(decision, roster.team_intelligence[roster_id]) for roster_id, decision in intelligence.decisions.items()}
    needs: dict[int, tuple[TeamNeed, ...]] = {}
    surpluses: dict[int, tuple[TeamSurplus, ...]] = {}
    availability: dict[str, AssetAvailability] = {}
    for roster_id, rooms in roster.league_rooms.items():
        cards_by_position = {position: [card for card in roster.league_players[roster_id].values() if intelligence.decisions[roster_id].profile.position_rooms.get(position) and card.player_id in {str(player.get("id") or player.get("player_id")) for player in intelligence.decisions[roster_id].profile.players if player.get("position") == position}] for position in POSITIONS}
        team_needs = tuple(sorted((_need(roster_id, position, rooms[position], cards_by_position[position], directions[roster_id]) for position in POSITIONS), key=lambda item: (-item.score, item.position)))
        needs[roster_id] = team_needs
        team_surpluses = tuple(item for position in POSITIONS if (item := _surplus(roster_id, position, rooms[position], cards_by_position[position], next(need for need in team_needs if need.position == position))) is not None)
        average_picks = mean(decision.profile.draft_pick_count for decision in intelligence.decisions.values())
        if intelligence.decisions[roster_id].profile.draft_pick_count >= average_picks + 2:
            team_surpluses += (TeamSurplus(roster_id, "Future Picks", 70, (), (f"Owns {intelligence.decisions[roster_id].profile.draft_pick_count} picks versus league average {average_picks:.1f}.",)),)
        surpluses[roster_id] = team_surpluses
        surplus_positions = {item.category for item in team_surpluses}
        position_by_player = {str(player.get("id") or player.get("player_id")): str(player.get("position") or "") for player in intelligence.decisions[roster_id].profile.players}
        for player_id, card in roster.league_players[roster_id].items():
            availability[player_id] = _availability(player_id, roster_id, card, directions[roster_id], surplus_positions, position_by_player.get(player_id, ""))

    compatibility_rows = []
    for (first_id, second_id), observed in intelligence.front_office_model.compatibilities.items():
        first_needs = {item.position for item in needs[first_id] if item.priority in {"Critical", "High"}}
        second_needs = {item.position for item in needs[second_id] if item.priority in {"Critical", "High"}}
        first_surplus = {item.category for item in surpluses[first_id]}
        second_surplus = {item.category for item in surpluses[second_id]}
        complementary = tuple(sorted((first_needs & second_surplus) | (second_needs & first_surplus)))
        first_rebuild = directions[first_id].label in {"Rebuilding", "Full Rebuild"}
        second_rebuild = directions[second_id].label in {"Rebuilding", "Full Rebuild"}
        timeline = "Complementary" if first_rebuild != second_rebuild else "Aligned"
        score = min(100, round(observed.score * .45 + len(complementary) * 16 + (12 if timeline == "Complementary" else 5) + min(observed.bilateral_trades, 3) * 4))
        compatibility_rows.append(TradeCompatibility(first_id, second_id, score, complementary, timeline, (f"Front Office Intelligence compatibility is {observed.score}/100.", f"Complementary needs/surpluses: {', '.join(complementary) or 'none'}.", f"Timeline fit is {timeline}.", f"Observed bilateral trades: {observed.bilateral_trades}.")))
    compatibilities = tuple(sorted(compatibility_rows, key=lambda item: (-item.score, item.first_roster_id, item.second_roster_id)))

    market_map = {}
    economy = {}
    for position in POSITIONS:
        buyers = tuple(sorted(roster_id for roster_id, rows in needs.items() if next(item for item in rows if item.position == position).priority in {"Critical", "High"}))
        sellers = tuple(sorted(roster_id for roster_id, rows in surpluses.items() if position in {item.category for item in rows}))
        market_map[position] = {"buyers": buyers, "sellers": sellers}
        supply = len(sellers)
        demand = len(buyers)
        premium = max(-50, min(50, (demand - supply) * 12))
        state = "Elite Scarcity" if demand >= supply + 3 else "Scarce" if demand > supply else "Oversupplied" if supply > demand + 1 else "Balanced"
        economy[position] = PositionEconomy(position, state, supply, demand, premium, f"{demand} quality-based buyers and {supply} evidence-supported sellers; premium {premium:+d}.")
    rebuild_ids = tuple(sorted(roster_id for roster_id, item in directions.items() if item.label in {"Rebuilding", "Full Rebuild"}))
    contender_ids = tuple(sorted(roster_id for roster_id, item in directions.items() if item.label in {"Elite Contender", "Contender"}))
    pick_sellers = tuple(sorted(roster_id for roster_id, rows in surpluses.items() if "Future Picks" in {item.category for item in rows} and roster_id in contender_ids))
    market_map["Draft Picks"] = {"buyers": rebuild_ids, "sellers": pick_sellers}
    market_map["Veterans"] = {"buyers": contender_ids, "sellers": rebuild_ids}
    market_map["Youth"] = {"buyers": rebuild_ids, "sellers": contender_ids}

    gm_profiles = {}
    for roster_id, report in intelligence.front_office_model.reports.items():
        preferences = {item.label for item in report.asset_preferences}
        preferred = tuple(sorted(position for position in POSITIONS if position in report.strengths))
        gm_profiles[roster_id] = GMProfile(roster_id, report.activity.level, report.negotiation_style, "High" if "Pick collector" in preferences else "Neutral / unavailable", "Observed" if "Values veterans" in preferences else "Unestablished", "Observed" if "Values youth" in preferences else "Unestablished", "Aggressive" if report.activity.trades >= 5 else "Selective", "Unestablished", "Unavailable without offer events", "Unavailable without counteroffer events", "Neutral — DTOS does not judge managers", "Unestablished", preferred, report.confidence, tuple(f"{item.factor}: {item.observed_value}" for item in report.evidence))

    team_reports = {}
    for roster_id, direction in directions.items():
        strengths = tuple(item.category for item in surpluses[roster_id]) or ("No evidence-supported surplus",)
        weaknesses = tuple(f"{item.priority} {item.position}" for item in needs[roster_id] if item.priority in {"Critical", "High"}) or ("No critical need",)
        likely = f"Acquire {needs[roster_id][0].position} help" if needs[roster_id][0].priority != "Low" else "Monitor market inefficiencies"
        flexibility = "High" if len(surpluses[roster_id]) >= 2 else "Medium" if surpluses[roster_id] else "Low"
        team_reports[roster_id] = TeamReport(roster_id, direction, strengths, weaknesses, likely, flexibility, directions[roster_id].label, (*direction.reasoning, f"Top need is {needs[roster_id][0].position} ({needs[roster_id][0].score}/100)."))

    active_id = intelligence.context.active_roster_id
    active_needs = {item.position: item for item in needs[active_id]}
    partner_scores = {item.second_roster_id if item.first_roster_id == active_id else item.first_roster_id: item.score for item in compatibilities if active_id in {item.first_roster_id, item.second_roster_id}}
    opportunities = []
    name_by_id = {str(player.get("id") or player.get("player_id")): str(player.get("name") or player.get("full_name") or player.get("id")) for decision in intelligence.decisions.values() for player in decision.profile.players}
    position_by_id = {str(player.get("id") or player.get("player_id")): str(player.get("position") or "") for decision in intelligence.decisions.values() for player in decision.profile.players}
    status_scores = {"Actively Shopping": 95, "Available": 82, "Available For Premium": 65, "Extremely Difficult": 30, "Untouchable": 5}
    for player_id, available in availability.items():
        if available.roster_id == active_id:
            continue
        card = roster.league_players[available.roster_id][player_id]
        need = active_needs.get(position_by_id.get(player_id, ""))
        fit = need.score if need else 20
        partner = partner_scores.get(available.roster_id, 40)
        market_gap = card.dynasty_value - (card.market_value if card.market_value is not None else card.dynasty_value)
        gap_signal = max(0, min(100, 50 + market_gap))
        score = round(fit * .27 + status_scores[available.status] * .22 + partner * .18 + card.dynasty_value * .13 + card.trade_liquidity * .10 + gap_signal * .10)
        opportunities.append(Opportunity(player_id, name_by_id.get(player_id, player_id), available.roster_id, active_id, min(100, score), available.status, partner, (f"Active Front Office need fit is {fit}/100.", f"Availability is {available.status}.", f"Partner compatibility is {partner}/100.", f"Dynasty value {card.dynasty_value}/100 and liquidity {card.trade_liquidity}/100.", f"Observable market gap is {market_gap:+d}; neutral when external consensus is unavailable.")))
    opportunities = sorted(opportunities, key=lambda item: (-item.score, item.player_name))

    trade_recommendations = []
    for dossier in intelligence.trades[:5]:
        sent = tuple(asset.label for asset in dossier.proposal.assets_sent)
        received = tuple(asset.label for asset in dossier.proposal.assets_received)
        market_delta = dossier.market.market_gain_loss if dossier.market else None
        trade_recommendations.append(LeagueTradeRecommendation(dossier.partner.roster_id, sent, received, dossier.impact.asset_value, market_delta, dossier.impact.current_outlook, "Improves current direction" if dossier.impact.current_outlook > 0 else "Improves future direction" if dossier.impact.future_outlook > 0 else "Direction-neutral", dossier.recommendation.confidence, (dossier.why_active_improves, dossier.why_partner_improves, dossier.why_realistic, dossier.why_now)))

    active_partners = sorted(((score, roster_id) for roster_id, score in partner_scores.items()), reverse=True)
    undervalued = max(intelligence.market.opportunities, key=lambda item: item.value_gap.difference or -999, default=None)
    overvalued = min(intelligence.market.assets.values(), key=lambda item: item.value_gap.difference if item.value_gap.difference is not None else 999, default=None)
    most_tradable = max((item for item in availability.values() if item.status != "Untouchable"), key=lambda item: status_scores[item.status], default=None)
    strongest = max(((score, roster_id, position) for roster_id, rooms in roster.league_rooms.items() for position, score in rooms.items()), default=(0, 0, "Unavailable"))
    weakest = min(((score, roster_id, position) for roster_id, rooms in roster.league_rooms.items() for position, score in rooms.items()), default=(0, 0, "Unavailable"))
    dashboard = {
        "Today's Best Trade Partner": str(active_partners[0][1]) if active_partners else "Unavailable",
        "Most Undervalued Player": undervalued.label if undervalued else "Unavailable",
        "Most Overvalued Player": overvalued.label if overvalued and overvalued.value_gap.difference is not None else "Unavailable",
        "Largest Team Need": f"Team {max((item for rows in needs.values() for item in rows), key=lambda item: item.score).roster_id} {max((item for rows in needs.values() for item in rows), key=lambda item: item.score).position}",
        "Most Tradable Asset": most_tradable.player_id if most_tradable else "Unavailable",
        "Most Valuable Pick": "Requires pick-market provider",
        "Strongest Position Group": f"Team {strongest[1]} {strongest[2]} ({strongest[0]})",
        "Weakest Position Group": f"Team {weakest[1]} {weakest[2]} ({weakest[0]})",
        "Highest Opportunity Score": f"{opportunities[0].player_name} ({opportunities[0].score})" if opportunities else "Unavailable",
        "League Market Summary": ", ".join(f"{position} {item.state}" for position, item in economy.items()),
    }
    return LeagueIntelligenceReport(active_id, needs, surpluses, directions, compatibilities, market_map, availability, economy, gm_profiles, team_reports, tuple(opportunities[:25]), tuple(trade_recommendations), dashboard, ("Availability and acceptance are evidence-based estimates, not guarantees.", "Championship direction impact is qualitative; no probability model is implemented.", "Response-rate and counteroffer frequency remain unavailable without offer-event history."))
