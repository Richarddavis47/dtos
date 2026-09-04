"""Deterministic assembly and publication of shared Front Office evidence."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from statistics import mean
from typing import Any, Iterable

from src.core.fois.facts import TradeFact
from src.core.intelligence.league_scope import league_id_from_data

from .models import (
    FRONT_OFFICE_EVIDENCE_METHOD_VERSION,
    FRONT_OFFICE_EVIDENCE_SCHEMA_VERSION,
    FrontOfficeEvidenceSummary,
)


def _identity(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()


def assemble_front_office_evidence(
    *, league_id: str, franchise_id: str, gm_id: str | None,
    trades: Iterable[TradeFact],
) -> FrontOfficeEvidenceSummary:
    """Summarize Step 4 trade-side evidence without rescanning history."""
    rows = tuple(sorted(trades, key=lambda row: (row.occurred_at or "", row.transaction_id)))
    process = Counter(row.process_classification or "unavailable" for row in rows)
    outcomes = Counter(row.outcome_classification or "unavailable" for row in rows)
    confidence = Counter(row.process_confidence or "unavailable" for row in rows)
    maturity = Counter(row.outcome_maturity or "unavailable" for row in rows)
    partners = Counter(row.partner_id for row in rows if row.partner_id)
    process_scores = [row.process_score for row in rows if row.process_score is not None]
    outcome_scores = [row.outcome_score for row in rows if row.outcome_score is not None]
    evaluated = sum(
        row.process_classification not in {None, "insufficient_evidence", "evaluation_blocked_invalid_historical_state"}
        for row in rows
    )
    references = tuple(sorted({ref for row in rows for ref in row.evidence_references}))
    history_generations = tuple(sorted({row.history_generation for row in rows if row.history_generation}))
    market_generations = tuple(sorted({row.market_generation for row in rows if row.market_generation}))
    core = {
        "league_id": league_id, "franchise_id": franchise_id, "gm_id": gm_id,
        "transaction_ids": tuple(row.transaction_id for row in rows),
        "process": dict(sorted(process.items())), "outcomes": dict(sorted(outcomes.items())),
        "confidence": dict(sorted(confidence.items())), "maturity": dict(sorted(maturity.items())),
        "partners": dict(sorted(partners.items())), "history_generations": history_generations,
        "market_generations": market_generations,
        "behavioral_observations": tuple({
            "transaction_id": row.transaction_id,
            "occurred_at": row.occurred_at,
            "incoming_asset_ids": row.incoming_asset_ids,
            "outgoing_asset_ids": row.outgoing_asset_ids,
            "incoming_asset_types": row.incoming_asset_types,
            "outgoing_asset_types": row.outgoing_asset_types,
            "incoming_positions": row.incoming_positions,
            "outgoing_positions": row.outgoing_positions,
            "known_incoming_value": row.known_incoming_value,
            "known_outgoing_value": row.known_outgoing_value,
            "market_coverage_ratio": row.market_coverage_ratio,
            "competitive_window_at_trade": row.competitive_window_at_trade,
            "season_phase": row.season_phase,
        } for row in rows),
        "schema_version": FRONT_OFFICE_EVIDENCE_SCHEMA_VERSION,
        "method_version": FRONT_OFFICE_EVIDENCE_METHOD_VERSION,
    }
    return FrontOfficeEvidenceSummary(
        league_id, franchise_id, gm_id, len(rows), evaluated,
        dict(sorted(process.items())), dict(sorted(outcomes.items())),
        dict(sorted(confidence.items())), dict(sorted(maturity.items())),
        dict(sorted(partners.items())),
        round(mean(process_scores), 2) if process_scores else None,
        round(mean(outcome_scores), 2) if outcome_scores else None,
        round(evaluated / len(rows) * 100, 2) if rows else 0.0,
        references, history_generations, market_generations, _identity(core),
    )


def publish_front_office_evidence(
    data: dict[str, Any], scores: tuple[Any, ...],
) -> None:
    """Atomically expose already-computed summaries to request-time consumers."""
    league_id = league_id_from_data(data)
    summaries = {
        str(score.franchise_id.rsplit(":", 1)[-1]): dict(score.front_office_evidence)
        for score in scores
        if getattr(score, "front_office_evidence", None)
        and str(getattr(score, "league_id", "")) == league_id
        and str(score.front_office_evidence.get("league_id") or "") == league_id
    }
    data["front_office_evidence"] = summaries
