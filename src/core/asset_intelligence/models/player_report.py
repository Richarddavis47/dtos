"""Player dossier contracts."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.asset_intelligence.models.asset_evaluation import AssetEvaluation, CoreValues
from src.core.asset_intelligence.models.evidence import Evidence


@dataclass(frozen=True)
class PlayerProfile:
    player_id: str
    name: str
    position: str
    nfl_team: str
    age: float | None
    experience: int | None
    contract_status: str
    injury_status: str
    bye_week: str


@dataclass(frozen=True)
class RiskReport:
    score: int
    level: str
    evidence: tuple[Evidence, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssetRecommendation:
    action: str
    summary: str
    priority: str
    confidence: int
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class PlayerReport:
    profile: PlayerProfile
    executive_summary: str
    current_outlook: str
    long_term_outlook: str
    core_values: CoreValues
    archetypes: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    risk: RiskReport
    opportunity: dict[str, AssetEvaluation]
    recommendation: AssetRecommendation
    limitations: tuple[str, ...]
