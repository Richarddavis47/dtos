"""League-wide opportunity synthesis over existing DTOS intelligence outputs."""
from __future__ import annotations

from typing import Any

from src.core.league_intelligence.models import (
    AssetAvailability, GMProfile, LeagueIntelligenceReport, LeagueTradeRecommendation, Opportunity,
    PositionEconomy, TeamDirection, TeamNeed, TeamReport, TeamSurplus, TradeCompatibility,
)

POSITIONS = ("QB", "RB", "WR", "TE")


def _direction(decision: Any, card: Any) -> TeamDirection:
    current = 'Unavailable' if card.current_strength is None else f'{card.current_strength}/100'
    future = 'Unavailable' if card.future_strength is None else f'{card.future_strength}/100'
    return TeamDirection(decision.profile.roster_id, card.current_window.value, card.confidence,
        (f"Optimal projected lineup relative strength: {current}.", f"Long-term utility: {future}.", *card.explanation))


def _need(roster_id, position, facts):
    priority = ('Unavailable' if not facts or facts['coverage'] != 'supported current week' else
                'Low' if facts['classification'] == 'Current production gap' else
                'High' if facts['starter_need'] else 'Medium' if facts['resilience_need'] or facts.get('quality_depth_need') else 'Low')
    return TeamNeed(roster_id, position, priority, None,
                    (facts['interpretation'],) if facts else ('Compatible legal-lineup evidence unavailable.',))


def _availability(player_id: str, roster_id: int, card: Any, direction: TeamDirection, surplus_positions: set[str], position: str) -> AssetAvailability:
    if card.trade_liquidity is None:
        return AssetAvailability(player_id, roster_id, 'Unavailable', 0, ('Market price alone does not establish trade availability or willingness.',))
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
    from src.core.gm_behavioral_intelligence.diagnostics import league_gm_observations, MINIMUM_TENDENCY
    observations = league_gm_observations.report(intelligence.context.cached_data)
    roster = intelligence.roster
    directions = {roster_id: _direction(decision, roster.team_intelligence[roster_id]) for roster_id, decision in intelligence.decisions.items()}
    needs: dict[int, tuple[TeamNeed, ...]] = {}
    surpluses: dict[int, tuple[TeamSurplus, ...]] = {}
    availability: dict[str, AssetAvailability] = {}
    for roster_id, rooms in roster.league_rooms.items():
        facts = (intelligence.decisions[roster_id].diagnostics or {}).get('positions') or {}
        team_needs = tuple(sorted((_need(roster_id, position, facts.get(position)) for position in POSITIONS), key=lambda item: ({'High': 0, 'Medium': 1, 'Low': 2, 'Unavailable': 3}[item.priority], item.position)))
        needs[roster_id] = team_needs
        team_surpluses = tuple(TeamSurplus(roster_id, pos, None,
            tuple(asset['player_id'] for asset in row['surplus_assets']),
            (row['interpretation'], 'Current-week conditional depth only; Market and long-term capital remain separate.'))
            for pos, row in facts.items() if row['surplus_assets'])
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
    lineup_known = sum(card.starting_lineup.rank is not None for card in roster.team_intelligence.values())
    league_size = len(roster.team_intelligence)
    for position in POSITIONS:
        buyers = tuple(sorted(roster_id for roster_id, rows in needs.items() if next(item for item in rows if item.position == position).priority in {"Critical", "High"}))
        sellers = tuple(sorted(roster_id for roster_id, rows in surpluses.items() if position in {item.category for item in rows}))
        market_map[position] = {"buyers": buyers, "sellers": sellers}
        supply = len(sellers)
        demand = len(buyers)
        known = sum(item.priority != 'Unavailable' for rows in needs.values() for item in rows if item.position == position)
        state = 'Unavailable' if not known else 'Observed demand exceeds expendable supply' if demand > supply else 'Observed expendable supply exceeds demand' if supply > demand else 'No observed imbalance'
        economy[position] = PositionEconomy(position, state, supply, demand, None,
            f'{demand} supported starter-need contexts and {supply} conditional depth suppliers across {known}/{league_size} complete-roster needs assessments. '
            f'{lineup_known}/{league_size} franchises have supported optimal lineups. Needs assessments additionally require complete eligible replacement evidence and supported availability; '
            'missing depth evidence is not proven weak depth or an absent starting lineup. Availability is not willingness and no Market premium is inferred.')
    rebuild_ids = tuple(sorted(roster_id for roster_id, item in directions.items() if item.label in {"Rebuilding", "Full Rebuild"}))
    contender_ids = tuple(sorted(roster_id for roster_id, item in directions.items() if item.label in {"Elite Contender", "Contender"}))
    pick_sellers = tuple(sorted(roster_id for roster_id, rows in surpluses.items() if "Future Picks" in {item.category for item in rows} and roster_id in contender_ids))
    market_map["Draft Picks"] = {"buyers": rebuild_ids, "sellers": pick_sellers}
    market_map["Veterans"] = {"buyers": contender_ids, "sellers": rebuild_ids}
    market_map["Youth"] = {"buyers": rebuild_ids, "sellers": contender_ids}

    gm_profiles = {}
    for roster_id, report in intelligence.front_office_model.reports.items():
        manager = (observations.get('teams', {}).get(str(roster_id), {}).get('manager') or {})
        preferred = tuple(sorted(position for position, count in (manager.get('acquired_positions') or {}).items() if count >= MINIMUM_TENDENCY))
        pick_preference = 'Observed acquisitions; season-attributed, not willingness' if (manager.get('acquired_kinds') or {}).get('pick', 0) >= MINIMUM_TENDENCY else 'Unestablished'

        gm_profiles[roster_id] = GMProfile(roster_id, report.activity.level, report.negotiation_style, pick_preference, "Unestablished", "Unestablished", "Unestablished", "Unestablished", "Unavailable without offer events", "Unavailable without counteroffer events", "Neutral — DTOS does not judge managers", "Unestablished", preferred, report.confidence, tuple(f"{item.factor}: {item.observed_value}" for item in report.evidence))

    team_reports = {}
    for roster_id, direction in directions.items():
        from src.core.intelligence.roster_diagnostics import diagnostic_qualification
        qualification = diagnostic_qualification(intelligence.decisions[roster_id].diagnostics)
        strengths = tuple(pos for pos, facts in ((intelligence.decisions[roster_id].diagnostics or {}).get('positions') or {}).items() if facts['strength']) or ("No evidence-supported positional strength",)
        weaknesses = tuple(f"{item.priority} {item.position}" for item in needs[roster_id] if item.priority in {"Critical", "High"}) or ("No critical need",)
        likely = f"Acquire {needs[roster_id][0].position} help" if needs[roster_id][0].priority != "Low" else "Monitor market inefficiencies"
        flexibility = "High" if len(surpluses[roster_id]) >= 2 else "Medium" if surpluses[roster_id] else "Low"
        team_reports[roster_id] = TeamReport(roster_id, direction, strengths, weaknesses, likely, flexibility, directions[roster_id].label, (*direction.reasoning, *([qualification] if qualification else []), f"First positional context: {needs[roster_id][0].position} ({needs[roster_id][0].priority}); no synthetic need score."))

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
        if card.dynasty_value is None or card.trade_liquidity is None:
            continue
        need = active_needs.get(position_by_id.get(player_id, ""))
        if need is None or need.score is None:
            continue  # No invented scalar for the legacy numerical opportunity formula.
        fit = need.score
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
        direction = (
            "Current improvement; future evidence unavailable"
            if dossier.impact.future_outlook is None and dossier.impact.current_outlook is not None and dossier.impact.current_outlook > 0
            else "Future direction unavailable" if dossier.impact.future_outlook is None
            else "Improves current direction" if dossier.impact.current_outlook is not None and dossier.impact.current_outlook > 0
            else "Improves future direction" if dossier.impact.future_outlook > 0
            else "Direction-neutral"
        )
        trade_recommendations.append(LeagueTradeRecommendation(dossier.partner.roster_id, sent, received, dossier.impact.asset_value, market_delta, dossier.impact.current_outlook, direction, dossier.recommendation.confidence, (dossier.why_active_improves, dossier.why_partner_improves, dossier.why_realistic, dossier.why_now)))

    active_partners = sorted(((score, roster_id) for roster_id, score in partner_scores.items()), reverse=True)
    undervalued = max(intelligence.market.opportunities, key=lambda item: item.value_gap.difference or -999, default=None)
    overvalued = min((item for item in intelligence.market.assets.values() if item.value_gap.difference is not None and item.value_gap.difference < 0), key=lambda item: item.value_gap.difference, default=None)
    most_tradable = max((item for item in availability.values() if item.status in status_scores and item.status != "Untouchable"), key=lambda item: status_scores[item.status], default=None)
    strongest = max(((score, roster_id, position) for roster_id, rooms in roster.league_rooms.items() for position, score in rooms.items() if score is not None), default=(0, 0, "Unavailable"))
    weakest = min(((score, roster_id, position) for roster_id, rooms in roster.league_rooms.items() for position, score in rooms.items() if score is not None), default=(0, 0, "Unavailable"))
    names = {roster_id: getattr(decision.profile, "team_name", "Unassigned Franchise") for roster_id, decision in intelligence.decisions.items()}
    largest_need = max((item for rows in needs.values() for item in rows if item.score is not None), key=lambda item: item.score, default=None)
    dashboard = {
        "Today's Best Trade Partner": names.get(active_partners[0][1], "Unassigned Franchise") if active_partners else "Unavailable",
        "Most Undervalued Player": undervalued.label if undervalued else "Unavailable",
        "Most Overvalued Player": overvalued.label if overvalued and overvalued.value_gap.difference is not None else "Unavailable",
        "Largest Team Need": f"{names.get(largest_need.roster_id, 'Unassigned Franchise')} {largest_need.position}" if largest_need else 'Unavailable',
        "Most Tradable Asset": most_tradable.player_id if most_tradable else "Unavailable",
        "Most Valuable Pick": "Requires pick-market provider",
        "Strongest Position Group": f"{names.get(strongest[1], 'Unassigned Franchise')} {strongest[2]} ({strongest[0]})",
        "Weakest Position Group": f"{names.get(weakest[1], 'Unassigned Franchise')} {weakest[2]} ({weakest[0]})",
        "Highest Opportunity Score": f"{opportunities[0].player_name} ({opportunities[0].score})" if opportunities else "Unavailable",
        "League Market Summary": ", ".join(f"{position} {item.state}" for position, item in economy.items()),
    }
    return LeagueIntelligenceReport(active_id, needs, surpluses, directions, compatibilities, market_map, availability, economy, gm_profiles, team_reports, tuple(opportunities[:25]), tuple(trade_recommendations), dashboard, ("Availability and acceptance are evidence-based estimates, not guarantees.", "Championship direction impact is qualitative; no probability model is implemented.", "Response-rate and counteroffer frequency remain unavailable without offer-event history."), observations)
