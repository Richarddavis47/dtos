"""Explainable Front Office Intelligence contracts."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.asset_intelligence import Evidence
from src.core.decision_engine import TeamDecision


@dataclass(frozen=True)
class ActivityProfile:
    level: str
    trades: int
    waivers: int
    adds: int
    drops: int
    draft_assets: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class AssetPreference:
    label: str
    strength: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class FrontOfficeReport:
    roster_id: int
    owner_name: str
    team_name: str
    executive_summary: str
    competitive_window: str
    philosophies: tuple[str, ...]
    negotiation_style: str
    activity: ActivityProfile
    asset_preferences: tuple[AssetPreference, ...]
    strengths: tuple[str, ...]
    constraints: tuple[str, ...]
    confidence: int
    evidence: tuple[Evidence, ...]
    decision: TeamDecision


@dataclass(frozen=True)
class NegotiationForecast:
    opening_recommendation: str
    expected_counter: str
    acceptance_probability: int | None
    walk_away_point: str
    alternative_structures: tuple[str, ...]
    fallback_targets: tuple[str, ...]
    notes: tuple[str, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class CompatibilityReport:
    first_roster_id: int
    second_roster_id: int
    score: int
    difficulty: str
    shared_interests: tuple[str, ...]
    conflicting_priorities: tuple[str, ...]
    best_trade_themes: tuple[str, ...]
    bilateral_trades: int
    forecast: NegotiationForecast
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class RelationshipEdge:
    first_roster_id: int
    second_roster_id: int
    bilateral_trades: int
    compatibility_score: int


@dataclass(frozen=True)
class LeagueFrontOfficeModel:
    reports: dict[int, FrontOfficeReport]
    compatibilities: dict[tuple[int, int], CompatibilityReport]
    relationships: tuple[RelationshipEdge, ...]

    def compatibility(self, first: int, second: int) -> CompatibilityReport:
        key = tuple(sorted((first, second)))
        if first == second or key not in self.compatibilities:
            raise ValueError("Compatibility requires two available Front Offices.")
        return self.compatibilities[key]
