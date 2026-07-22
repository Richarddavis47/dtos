"""Immutable League Intelligence synthesis contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TeamNeed:
    roster_id: int
    position: str
    priority: str
    score: int
    reasoning: tuple[str, ...]


@dataclass(frozen=True)
class TeamSurplus:
    roster_id: int
    category: str
    score: int
    tradable_assets: tuple[str, ...]
    reasoning: tuple[str, ...]


@dataclass(frozen=True)
class TeamDirection:
    roster_id: int
    label: str
    confidence: int
    reasoning: tuple[str, ...]


@dataclass(frozen=True)
class TradeCompatibility:
    first_roster_id: int
    second_roster_id: int
    score: int
    complementary_needs: tuple[str, ...]
    timeline_fit: str
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class AssetAvailability:
    player_id: str
    roster_id: int
    status: str
    confidence: int
    reasoning: tuple[str, ...]


@dataclass(frozen=True)
class PositionEconomy:
    position: str
    state: str
    supply: int
    demand: int
    premium: int
    explanation: str


@dataclass(frozen=True)
class GMProfile:
    roster_id: int
    activity: str
    negotiation_style: str
    pick_valuation: str
    veteran_preference: str
    youth_preference: str
    aggressiveness: str
    risk_tolerance: str
    response_rate: str
    counteroffer_frequency: str
    fairness: str
    patience: str
    preferred_positions: tuple[str, ...]
    confidence: int
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TeamReport:
    roster_id: int
    direction: TeamDirection
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    likely_move: str
    trade_flexibility: str
    championship_window: str
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class Opportunity:
    player_id: str
    player_name: str
    owner_roster_id: int
    target_roster_id: int
    score: int
    availability: str
    partner_score: int
    reasoning: tuple[str, ...]


@dataclass(frozen=True)
class LeagueTradeRecommendation:
    partner_roster_id: int
    offer: tuple[str, ...]
    receive: tuple[str, ...]
    dtos_value_delta: int
    market_value_delta: int | None
    lineup_impact: int
    direction_impact: str
    confidence: int
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class LeagueIntelligenceReport:
    active_roster_id: int
    needs: dict[int, tuple[TeamNeed, ...]]
    surpluses: dict[int, tuple[TeamSurplus, ...]]
    directions: dict[int, TeamDirection]
    compatibilities: tuple[TradeCompatibility, ...]
    market_map: dict[str, dict[str, tuple[int, ...]]]
    availability: dict[str, AssetAvailability]
    economy: dict[str, PositionEconomy]
    gm_profiles: dict[int, GMProfile]
    team_reports: dict[int, TeamReport]
    opportunities: tuple[Opportunity, ...]
    trade_recommendations: tuple[LeagueTradeRecommendation, ...]
    dashboard: dict[str, str]
    limitations: tuple[str, ...]
