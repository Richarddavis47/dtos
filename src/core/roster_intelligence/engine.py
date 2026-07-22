"""Deterministic roster construction evaluation using shared intelligence outputs."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.asset_intelligence import AssetContext, evaluate_player
from src.core.roster_intelligence.models import GradeDimension, PlayerCard, PositionRoomReport, RosterReport

POSITIONS = ("QB", "RB", "WR", "TE")
POSITION_WEIGHTS = {
    "QB": (0.34, 0.14, 0.18, 0.14, 0.12, 0.08),
    "RB": (0.28, 0.19, 0.18, 0.12, 0.13, 0.10),
    "WR": (0.30, 0.18, 0.16, 0.16, 0.12, 0.08),
    "TE": (0.36, 0.12, 0.22, 0.12, 0.10, 0.08),
}


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def _grade(score: float) -> str:
    score = _clamp(score)
    for threshold, label in ((97, "A+"), (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"), (73, "C"), (70, "C-"), (67, "D+"), (63, "D"), (60, "D-")):
        if score >= threshold:
            return label
    return "F"


def _tier(score: int) -> str:
    for threshold, label in ((92, "Elite Franchise Player"), (84, "Cornerstone"), (76, "Core Starter"), (68, "Quality Starter"), (58, "Flex Asset"), (48, "Depth"), (38, "Developmental")):
        if score >= threshold:
            return label
    return "Replacement Level"


def _market(report: Any, market: Any) -> tuple[int | None, str, int]:
    item = market.assets.get(report.profile.player_id) if market else None
    if item and item.consensus.value is not None:
        return item.consensus.value, item.trend.direction, item.consensus.confidence
    return None, "Unavailable", report.core_values.market.confidence


def _player_card(report: Any, market: Any, window: str, scarcity: int, unified: Any = None) -> PlayerCard:
    if unified is not None:
        return PlayerCard(
            unified.player_id, unified.positional.tier, _grade(unified.dtos_dynasty.value or 0),
            _clamp(unified.dtos_dynasty.value or 0), "Unknown" if unified.age is None else "Ascending" if unified.age <= 24 else "Prime" if unified.age <= 27 else "Veteran",
            unified.market_trend, round(unified.market_consensus.value) if unified.market_consensus.value is not None else None,
            round(unified.dtos_dynasty.value or 0), round(unified.contender.value or 0), round(unified.rebuilder.value or 0),
            round(unified.trade_liquidity.value or 0), unified.positional.scarcity, report.risk.level,
            _clamp((unified.projection.ceiling or 0) * 4), _clamp((unified.projection.floor or 0) * 5),
            unified.projection.source, report.long_term_outlook, unified.recommendation,
        )
    market_value, trend, market_confidence = _market(report, market)
    dynasty = report.core_values.dynasty.score
    redraft = report.core_values.redraft.score
    fit = report.core_values.team_fit.score
    consensus = market_value if market_value is not None else dynasty
    overall = _clamp(dynasty * .34 + redraft * .22 + fit * .18 + consensus * .18 + (100 - report.risk.score) * .08)
    contender = _clamp(redraft * .50 + fit * .25 + consensus * .15 + (100 - report.risk.score) * .10)
    rebuilder = _clamp(dynasty * .55 + consensus * .25 + (100 - report.risk.score) * .10 + fit * .10)
    liquidity = _clamp(consensus * .60 + market_confidence * .25 + (100 - report.risk.score) * .15)
    age = report.profile.age
    age_curve = "Unknown" if age is None else "Ascending" if age <= 24 else "Prime" if age <= 27 else "Veteran" if age <= 30 else "Declining"
    action = report.recommendation.action.upper()
    if overall >= 88 and action == "HOLD":
        action = "BUILD AROUND"
    return PlayerCard(
        report.profile.player_id, _tier(overall), _grade(overall), overall, age_curve, trend,
        market_value, dynasty, contender, rebuilder, liquidity, scarcity, report.risk.level,
        _clamp(redraft * .65 + overall * .35), _clamp(redraft * .55 + (100 - report.risk.score) * .45),
        report.current_outlook, report.long_term_outlook, action,
    )


def _room_score(cards: list[PlayerCard], position: str) -> tuple[int, dict[str, int]]:
    ordered = sorted(cards, key=lambda item: item.overall_score, reverse=True)
    elite = ordered[0].overall_score if ordered else 0
    second = ordered[1].overall_score if len(ordered) > 1 else 25
    top_three = mean(item.overall_score for item in ordered[:3]) if ordered else 0
    depth = _clamp(mean(item.overall_score for item in ordered[2:5])) if len(ordered) > 2 else _clamp(len(ordered) * 12)
    weekly = _clamp(mean(item.weekly_ceiling for item in ordered[:3])) if ordered else 0
    longevity = _clamp(mean(item.rebuilder_value for item in ordered[:3])) if ordered else 0
    market = _clamp(mean(item.market_value if item.market_value is not None else item.dynasty_value for item in ordered[:3])) if ordered else 0
    championship = _clamp(mean(item.contender_value for item in ordered[:3])) if ordered else 0
    quality = _clamp(elite * .60 + second * .25 + top_three * .15)
    values = {"Elite Talent": quality, "Depth": depth, "Weekly Advantage": weekly, "Longevity": longevity, "Market Value": market, "Championship Impact": championship}
    score = _clamp(sum(values[name] * weight for name, weight in zip(values, POSITION_WEIGHTS[position])))
    return score, values


def _identity(current: int, future: int, age: float | None, elite: int) -> tuple[str, str]:
    if current >= 82 and future >= 78:
        label = "Championship Favorite" if current >= 90 else "Young Contender" if age is not None and age <= 25.5 else "Contender"
    elif future >= 82:
        label = "Future Powerhouse" if elite >= 2 else "Ascending"
    elif current >= 76 and future < 62:
        label = "Aging Contender"
    elif current < 55 and future >= 65:
        label = "Productive Struggle"
    elif current < 55:
        label = "Rebuilding"
    else:
        label = "Balanced" if abs(current - future) <= 12 else "Bridge Team"
    return label, f"Current outlook {current}/100, future outlook {future}/100, average starter age {age if age is not None else 'unavailable'}, and {elite} elite/cornerstone assets."


def evaluate_roster(intelligence: Any) -> RosterReport:
    decision = intelligence.decision
    context = intelligence.context
    scarcity_by_position = decision.profile.market_context.get("position_counts") or {}
    cards = {
        player_id: _player_card(report, intelligence.market, decision.window.value, _clamp(100 - int(scarcity_by_position.get(report.profile.position, 0))), intelligence.player_values.get(player_id))
        for player_id, report in intelligence.player_reports.items()
    }
    room_inputs: dict[str, tuple[int, dict[str, int]]] = {}
    for position in POSITIONS:
        room_inputs[position] = _room_score([card for player_id, card in cards.items() if intelligence.player_reports[player_id].profile.position == position], position)
    room_scores = {position: value[0] for position, value in room_inputs.items()}
    league_room_scores: dict[str, list[int]] = {position: [] for position in POSITIONS}
    league_dimensions: list[dict[str, float]] = []
    league_rooms_by_roster: dict[int, dict[str, int]] = {}
    league_players: dict[int, dict[str, PlayerCard]] = {}
    for roster_id, other in intelligence.decisions.items():
        if roster_id == context.active_roster_id:
            other_scores = room_scores
            other_cards = list(cards.values())
            starter_ids = {str(player.get("id") or player.get("player_id")) for player in other.profile.players if player.get("roster_slot") == "Starter"}
        else:
            depths = {position: room.total_players for position, room in other.profile.position_rooms.items()}
            asset_context = AssetContext(context.league_id, roster_id, context.settings, other.window.value, other.profile.strategy, (), depths, other.profile.market_context.get("position_counts") or {})
            other_reports = [evaluate_player(player, asset_context) for player in other.profile.players]
            other_cards = [_player_card(report, None, other.window.value, _clamp(100 - int(scarcity_by_position.get(report.profile.position, 0)))) for report in other_reports]
            starter_ids = {str(player.get("id") or player.get("player_id")) for player in other.profile.players if player.get("roster_slot") == "Starter"}
            other_scores = {position: _room_score([card for card, report in zip(other_cards, other_reports) if report.profile.position == position], position)[0] for position in POSITIONS}
        starter_cards = [card for card in other_cards if card.player_id in starter_ids]
        league_dimensions.append({
            "roster_id": roster_id,
            "Total Dynasty Value": sum(card.dynasty_value for card in other_cards),
            "Starting-Lineup Dynasty Value": sum(card.dynasty_value for card in starter_cards),
            "Projected Weekly Starter Points": sum(card.weekly_ceiling * .25 for card in starter_cards),
            "Projected Floor": sum(card.weekly_floor * .20 for card in starter_cards),
            "Projected Ceiling": sum(card.weekly_ceiling * .25 for card in starter_cards),
            "Market Liquidity": mean((card.trade_liquidity for card in other_cards)) if other_cards else 0,
            "Contender Value": sum(card.contender_value for card in other_cards),
            "Rebuild Value": sum(card.rebuilder_value for card in other_cards),
        })
        for position in POSITIONS:
            league_room_scores[position].append(other_scores[position])
        league_rooms_by_roster[roster_id] = other_scores
        league_players[roster_id] = {card.player_id: card for card in other_cards}
    sorted_rooms = sorted(room_scores, key=lambda item: (-room_scores[item], item))
    rooms = {}
    league_size = len(context.teams)
    for position in POSITIONS:
        score, dimensions = room_inputs[position]
        rank = 1 + sum(other_score > score for other_score in league_room_scores[position])
        advantage = f"Top {rank} {position} room in league" if rank <= max(2, round(league_size * .2)) and score >= 70 else None
        reasoning = (
            "Top-end player quality supplies most of the grade; additional bodies cannot outweigh elite assets.",
            f"The best {position} asset scores {max((card.overall_score for player_id, card in cards.items() if intelligence.player_reports[player_id].profile.position == position), default=0)}/100.",
            f"Depth contributes independently and is currently {dimensions['Depth']}/100.",
        )
        room_dimensions = tuple(GradeDimension(name, value, _grade(value), f"Derived from shared Asset, Market, risk, age-curve, and team-fit evidence: {value}/100.") for name, value in dimensions.items())
        rooms[position] = PositionRoomReport(position, GradeDimension("Overall", score, _grade(score), "Weighted quality-first room score."), room_dimensions, rank, league_size, advantage, reasoning)
    elite = sum(card.tier in {"Elite Franchise Player", "Cornerstone"} for card in cards.values())
    current, future = decision.current_outlook.score, decision.future_outlook.score
    starter_age = mean(decision.profile.starter_ages) if decision.profile.starter_ages else None
    identity, identity_reasoning = _identity(current, future, round(starter_age, 1) if starter_age is not None else None, elite)
    metrics: dict[str, object] = {
        "Championship Window": current, "Future Window": future,
        "Roster Health": _clamp(100 - mean(card.overall_score * 0 + (100 if card.risk == 'High' else 35 if card.risk == 'Medium' else 10) for card in cards.values())) if cards else 50,
        "Elite Assets": elite, "Cornerstones": sum(card.tier == "Cornerstone" for card in cards.values()),
        "Trade Chips": sum(card.trade_liquidity >= 65 for card in cards.values()),
        "Roster Flexibility": _clamp(mean(card.trade_liquidity for card in cards.values())) if cards else 0,
        "Average Starter Age": round(starter_age, 1) if starter_age is not None else None,
        "Weekly Ceiling": _clamp(mean(card.weekly_ceiling for card in cards.values())) if cards else 0,
        "Weekly Floor": _clamp(mean(card.weekly_floor for card in cards.values())) if cards else 0,
        "Elite Concentration": _clamp(elite / max(1, len(cards)) * 400),
        "Positional Balance": _clamp(100 - (max(room_scores.values()) - min(room_scores.values()))) if room_scores else 0,
    }
    active_dimensions = next(item for item in league_dimensions if item["roster_id"] == context.active_roster_id)
    metrics["League Rankings"] = {
        name: 1 + sum(item[name] > active_dimensions[name] for item in league_dimensions)
        for name in active_dimensions if name != "roster_id"
    }
    advantages = tuple(room.advantage for room in rooms.values() if room.advantage)
    league_metric_map = {int(item["roster_id"]): {key: value for key, value in item.items() if key != "roster_id"} for item in league_dimensions}
    return RosterReport(identity, identity_reasoning, rooms, cards, metrics, sorted_rooms[0], sorted_rooms[-1], advantages, ("Production and projection dimensions use available deterministic Asset Intelligence proxies when live feeds are unavailable.",), league_rooms_by_roster, league_players, league_metric_map)
