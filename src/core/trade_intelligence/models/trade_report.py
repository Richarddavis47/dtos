"""Immutable trade opportunity and dossier contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.asset_intelligence import Evidence


class TradePriority(str, Enum):
    URGENT = "Urgent"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    FUTURE_WATCH = "Future Watch"


class TradeType(str, Enum):
    CHAMPIONSHIP_PUSH = "Championship Push"
    REBUILD = "Rebuild"
    VALUE_ARBITRAGE = "Value Arbitrage"
    AGE_SWAP = "Age Swap"
    PICK_ACQUISITION = "Pick Acquisition"
    DEPTH_UPGRADE = "Depth Upgrade"
    ELITE_CONSOLIDATION = "Elite Consolidation"
    ROSTER_BALANCE = "Roster Balance"
    MARKET_EXPLOIT = "Market Exploit"
    SELL_HIGH = "Sell High"
    BUY_LOW = "Buy Low"


@dataclass(frozen=True)
class TradeAsset:
    asset_id: str
    kind: str
    label: str
    position: str | None
    dynasty_value: int
    redraft_value: int
    market_value: int
    team_fit_value: int
    risk: int
    source_roster_id: int


@dataclass(frozen=True)
class TradeProposal:
    active_roster_id: int
    partner_roster_id: int
    assets_sent: tuple[TradeAsset, ...]
    assets_received: tuple[TradeAsset, ...]
    package_type: str


@dataclass(frozen=True)
class PartnerReport:
    roster_id: int
    team_name: str
    owner_name: str
    compatibility_score: int
    difficulty: str
    negotiation_complexity: str
    complementary_needs: tuple[str, ...]
    historical_trades: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class TradeImpact:
    current_outlook: int
    future_outlook: int
    roster_balance: int
    positional_depth: int
    asset_value: int
    risk: int
    opportunity_cost: int
    market_efficiency: int
    championship_outlook: int
    evidence: tuple[Evidence, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class NegotiationPlan:
    opening_offer: str
    minimum_offer: str
    maximum_offer: str
    likely_counter: str
    walk_away_point: str
    fallback_offer: str
    alternative_targets: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class TradeRecommendation:
    title: str
    summary: str
    trade_type: TradeType
    priority: TradePriority
    confidence: int
    expected_value: int
    acceptance_likelihood: int | None
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class TradeDossier:
    proposal: TradeProposal
    partner: PartnerReport
    recommendation: TradeRecommendation
    impact: TradeImpact
    negotiation: NegotiationPlan
    executive_summary: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    risks: tuple[str, ...]
    why_active_improves: str
    why_partner_improves: str
    why_realistic: str
    why_now: str
