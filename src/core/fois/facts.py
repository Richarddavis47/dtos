"""Raw FOIS facts separated from scoring and presentation."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.fois.models import FrontOfficeEvidence
from src.core.history_context.timestamps import canonical_utc_timestamp


@dataclass(frozen=True)
class SeasonResult:
    season: int
    wins: int | None
    losses: int | None
    finish: int | None
    playoff_finish: str | None = None
    championship: bool = False
    rebuilding: bool = False
    league_size: int | None = None
    playoff: bool = False
    final_four: bool = False
    championship_game: bool = False
    matchup_wins: int | None = None
    matchup_losses: int | None = None
    complete: bool = True


@dataclass(frozen=True)
class TradeFact:
    transaction_id: str
    season: int
    strategically_productive: bool | None
    market_overpay_percent: float | None = None
    championship_outlook_delta: float | None = None
    process_score: float | None = None
    outcome_score: float | None = None
    context_score: float | None = None
    recovery_score: float | None = None
    impact_weight: float = 1.0
    partner_id: str | None = None
    occurred_at: str | None = None
    process_evidence: dict[str, object] | None = None
    owner_id: str | None = None
    process_classification: str | None = None
    process_confidence: str | None = None
    outcome_classification: str | None = None
    outcome_confidence: str | None = None
    outcome_maturity: str | None = None
    history_generation: str | None = None
    market_generation: str | None = None
    evidence_references: tuple[str, ...] = ()
    incoming_asset_ids: tuple[str, ...] = ()
    outgoing_asset_ids: tuple[str, ...] = ()
    incoming_asset_types: tuple[str, ...] = ()
    outgoing_asset_types: tuple[str, ...] = ()
    incoming_positions: tuple[str, ...] = ()
    outgoing_positions: tuple[str, ...] = ()
    known_incoming_value: float | None = None
    known_outgoing_value: float | None = None
    market_coverage_ratio: float | None = None
    competitive_window_at_trade: str | None = None
    season_phase: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "occurred_at", canonical_utc_timestamp(self.occurred_at),
        )


@dataclass(frozen=True)
class DraftFact:
    draft_id: str
    season: int
    pick_number: float | None
    value_over_expected: float | None
    process_score: float | None = None
    outcome_score: float | None = None
    opportunity_cost_score: float | None = None


@dataclass(frozen=True)
class WaiverFact:
    transaction_id: str
    season: int
    value_created: float | None
    faab_efficiency: float | None = None
    meaningful: bool = False


@dataclass(frozen=True)
class FOISFacts:
    league_id: str
    franchise_id: str
    owner_id: str | None
    seasons: tuple[SeasonResult, ...]
    trades: tuple[TradeFact, ...] = ()
    drafts: tuple[DraftFact, ...] = ()
    roster_metrics: dict[str, float | None] | None = None
    league_settings: dict[str, object] | None = None
    evidence: tuple[FrontOfficeEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    ownership_changes: int = 0
    expected_seasons: int | None = None
    gm_id: str | None = None
    gm_name: str | None = None
    tenure_id: str | None = None
    tenure_started_at: str | None = None
    brain_snapshot_id: str | None = None
    brain_version: str | None = None
    current_team_score: float | None = None
    competitive_window: str | None = None
    waivers: tuple[WaiverFact, ...] = ()
    franchise_name: str | None = None
    front_office_evidence: dict[str, object] | None = None
    gm_behavioral_profile: dict[str, object] | None = None

    @property
    def completed_seasons(self) -> tuple[SeasonResult, ...]:
        return tuple(
            row for row in self.seasons
            if row.complete and row.wins is not None and row.losses is not None
        )
