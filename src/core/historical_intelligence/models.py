"""Canonical historical-intelligence contracts above reconstructable raw history."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


HISTORICAL_INTELLIGENCE_SCHEMA_VERSION = "historical-intelligence-1"
HISTORICAL_INTELLIGENCE_METHOD_VERSION = "canonical-normalization-1"


class EvidenceScope(StrEnum):
    GLOBAL = "global"
    LEAGUE = "league"


class HistoricalEventType(StrEnum):
    TRADE = "trade"
    WAIVER_ACQUISITION = "waiver_acquisition"
    FREE_AGENT_ACQUISITION = "free_agent_acquisition"
    DROP = "drop"
    ROOKIE_DRAFT_SELECTION = "rookie_draft_selection"
    PICK_TRADE = "pick_trade"
    MATCHUP_RESULT = "matchup_result"
    SEASON_RESULT = "season_result"
    PLAYOFF_RESULT = "playoff_result"
    CHAMPIONSHIP = "championship"
    ROSTER_OWNERSHIP_CHANGE = "roster_ownership_change"
    PLAYER_EVENT = "player_event"
    MILESTONE = "milestone"


class EvidenceAvailability(StrEnum):
    OBSERVED = "observed"
    RECONSTRUCTED = "reconstructed"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class CheckpointDirection(StrEnum):
    EXACT = "exact"
    AT_OR_BEFORE = "at_or_before"
    AFTER = "after"


def semantic_identity(namespace: str, *parts: object) -> str:
    """Return a stable semantic identity without random or display-name input."""
    body = json.dumps(
        [namespace, *("" if value is None else str(value) for value in parts)],
        separators=(",", ":"), ensure_ascii=True,
    )
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]
    return f"{namespace}:{digest}"


@dataclass(frozen=True)
class HistoricalEvent:
    event_id: str
    event_type: HistoricalEventType
    scope: EvidenceScope
    provider: str
    source_record_id: str
    season: int
    league_id: str
    league_season_context_id: str
    occurred_at: str | None = None
    week: int | None = None
    timestamp_provenance: Mapping[str, Any] = field(default_factory=dict)
    franchise_ids: tuple[str, ...] = ()
    player_ids: tuple[str, ...] = ()
    pick_ids: tuple[str, ...] = ()
    availability: EvidenceAvailability = EvidenceAvailability.OBSERVED
    confidence: int = 100
    source_reference: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    market_checkpoint_ids: tuple[str, ...] = ()
    schema_version: str = HISTORICAL_INTELLIGENCE_SCHEMA_VERSION
    method_version: str = HISTORICAL_INTELLIGENCE_METHOD_VERSION

    def __post_init__(self) -> None:
        if self.scope is not EvidenceScope.LEAGUE or not self.league_id:
            raise ValueError("Canonical league events require an explicit league scope.")
        if not 0 <= int(self.confidence) <= 100:
            raise ValueError("Historical evidence confidence must be between 0 and 100.")


@dataclass(frozen=True)
class GlobalMarketCheckpoint:
    checkpoint_id: str
    asset_id: str
    occurred_at: str
    provider: str
    normalized_value: float
    confidence: int
    classification: str
    reason_codes: tuple[str, ...]
    source_reference: str | None = None
    related_player_ids: tuple[str, ...] = ()
    relationship_evidence: tuple[str, ...] = ()
    schema_version: str = HISTORICAL_INTELLIGENCE_SCHEMA_VERSION
    method_version: str = HISTORICAL_INTELLIGENCE_METHOD_VERSION

    def __post_init__(self) -> None:
        if not self.asset_id or not self.occurred_at or not self.provider:
            raise ValueError("A global checkpoint requires asset, time, and provider identity.")
        if not self.reason_codes:
            raise ValueError("Sparse global checkpoints require an explainable retention reason.")
        if not 0 <= int(self.confidence) <= 100:
            raise ValueError("Checkpoint confidence must be between 0 and 100.")

    @classmethod
    def create(
        cls, *, asset_id: str, occurred_at: str, provider: str,
        normalized_value: float, confidence: int, classification: str,
        reason_codes: tuple[str, ...], source_reference: str | None = None,
        related_player_ids: tuple[str, ...] = (),
        relationship_evidence: tuple[str, ...] = (),
    ) -> "GlobalMarketCheckpoint":
        return cls(
            checkpoint_id=semantic_identity(
                "market-checkpoint", asset_id, occurred_at, provider, classification,
            ),
            asset_id=str(asset_id), occurred_at=str(occurred_at),
            provider=str(provider), normalized_value=float(normalized_value),
            confidence=int(confidence), classification=str(classification),
            reason_codes=tuple(sorted(set(map(str, reason_codes)))),
            source_reference=source_reference,
            related_player_ids=tuple(sorted(set(map(str, related_player_ids)))),
            relationship_evidence=tuple(map(str, relationship_evidence)),
        )

    def public_contract(self) -> dict[str, Any]:
        """Return only globally reusable evidence; league-private fields do not exist."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "asset_id": self.asset_id,
            "occurred_at": self.occurred_at,
            "provider": self.provider,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "classification": self.classification,
            "reason_codes": list(self.reason_codes),
            "source_reference": self.source_reference,
            "related_player_ids": list(self.related_player_ids),
            "relationship_evidence": list(self.relationship_evidence),
            "schema_version": self.schema_version,
            "method_version": self.method_version,
        }
