"""No-hindsight trade evaluation over canonical Steps 1-3."""
from __future__ import annotations

import asyncio
from collections import Counter
from threading import RLock

from src.core.historical_franchise_state import (
    HistoricalBoundary, HistoricalFranchiseState, HistoricalFranchiseStateService,
    ReconstructionAvailability, historical_franchise_state,
)
from src.core.historical_intelligence import (
    HistoricalEventType, HistoricalIntelligenceService,
    historical_intelligence, semantic_identity,
)
from src.core.trade_intelligence.bilateral import evaluate_package_quality
from src.core.trade_intelligence.models import TradeAsset

from .models import (
    ConfidenceLevel, HISTORICAL_TRANSACTION_METHOD_VERSION,
    HistoricalBacklogMetrics, HistoricalDecisionDimension,
    HistoricalOutcomeEvaluation, HistoricalProcessEvaluation,
    HistoricalTradeEvaluation, HistoricalTradeSideEvaluation,
    OutcomeClassification, ProcessClassification,
)


def _confidence(score: int) -> ConfidenceLevel:
    return ConfidenceLevel.HIGH if score >= 75 else ConfidenceLevel.MEDIUM if score >= 45 else ConfidenceLevel.LOW


def _asset_map(state: HistoricalFranchiseState) -> dict[str, object]:
    return {asset.asset_id: asset for asset in (*state.players, *state.draft_picks)}


def _trade_asset(asset: object, roster_id: int) -> TradeAsset:
    value = round(float(asset.market_value or 0))
    return TradeAsset(
        asset_id=asset.asset_id, kind=asset.asset_type, label=asset.asset_id,
        position=asset.position, dynasty_value=value, redraft_value=value,
        market_value=value, team_fit_value=value, risk=50,
        source_roster_id=roster_id, trade_value=value,
        confidence_score=asset.market_confidence or 0,
    )


class HistoricalTransactionIntelligenceService:
    """Evaluate canonical trades without independently reading or replaying history."""

    def __init__(
        self,
        history: HistoricalIntelligenceService = historical_intelligence,
        states: HistoricalFranchiseStateService = historical_franchise_state,
    ) -> None:
        self.history = history
        self.states = states
        self._lock = RLock()
        self._cache: dict[str, HistoricalTradeEvaluation] = {}
        self._metrics = Counter({
            "evaluations": 0, "cache_hits": 0, "provider_calls": 0,
            "raw_history_scans": 0, "backlog_runs": 0,
        })

    @staticmethod
    def _process(
        before: HistoricalFranchiseState,
        after: HistoricalFranchiseState,
    ) -> HistoricalProcessEvaluation:
        if before.availability is ReconstructionAvailability.INVALID or after.availability is ReconstructionAvailability.INVALID:
            return HistoricalProcessEvaluation(
                ProcessClassification.BLOCKED, ConfidenceLevel.LOW, (),
                ("Required Step 3 historical state is invalid; no process grade was produced.",),
                0, 0, 0, (),
            )
        old, new = _asset_map(before), _asset_map(after)
        outgoing = tuple(old[key] for key in sorted(old.keys() - new.keys()))
        incoming = tuple(new[key] for key in sorted(new.keys() - old.keys()))
        all_assets = (*outgoing, *incoming)
        known_out = sum(float(asset.market_value) for asset in outgoing if asset.market_value is not None)
        known_in = sum(float(asset.market_value) for asset in incoming if asset.market_value is not None)
        known_count = sum(asset.market_value is not None for asset in all_assets)
        coverage = known_count / len(all_assets) if all_assets else 0.0
        missing = tuple(asset.asset_id for asset in all_assets if asset.market_value is None)
        dimensions: list[HistoricalDecisionDimension] = []
        if known_count:
            ratio = known_in / max(known_out, 1.0)
            fairness = "balanced" if .8 <= ratio <= 1.25 else "favorable" if ratio > 1.25 else "premium_paid"
            dimensions.append(HistoricalDecisionDimension(
                "value_fairness", fairness,
                f"Known contemporaneous value received was {known_in:.1f} versus {known_out:.1f} sent; unknown assets were excluded, never valued at zero.",
            ))
        else:
            ratio = 1.0
            dimensions.append(HistoricalDecisionDimension(
                "value_fairness", "unknown", "No contemporaneous market value supports this dimension.", False,
            ))
        roster_id = int(before.franchise_id.rsplit(":", 1)[-1])
        shared_package = evaluate_package_quality(
            tuple(_trade_asset(asset, roster_id) for asset in incoming),
            tuple(_trade_asset(asset, roster_id) for asset in outgoing),
        )
        package = shared_package.assessment.casefold().replace(" ", "_")
        dimensions.append(HistoricalDecisionDimension(
            "package_quality", package,
            shared_package.explanation,
        ))
        before_lineup, after_lineup = before.lineup.optimal_points, after.lineup.optimal_points
        lineup_available = before_lineup is not None and after_lineup is not None
        lineup_delta = round(after_lineup - before_lineup, 2) if lineup_available else None
        dimensions.append(HistoricalDecisionDimension(
            "lineup_impact", "improved" if lineup_delta and lineup_delta > 0 else "declined" if lineup_delta and lineup_delta < 0 else "neutral_or_unknown",
            f"Historically supported optimal-lineup delta was {lineup_delta:.2f}." if lineup_available else "Historical projection coverage is insufficient; no numeric lineup delta was fabricated.",
            lineup_available,
        ))
        window = before.competitive_window.classification
        incoming_picks = sum(asset.asset_type == "pick" for asset in incoming)
        outgoing_picks = sum(asset.asset_type == "pick" for asset in outgoing)
        fit = "neutral"
        if window in {"Rebuilding", "REBUILDING", "rebuilding"} and incoming_picks > outgoing_picks:
            fit = "aligned"
        elif window in {"Contending", "CONTENDING", "contending"} and lineup_delta and lineup_delta > 0:
            fit = "aligned"
        dimensions.append(HistoricalDecisionDimension(
            "competitive_window_fit", fit,
            f"The contemporaneous Step 3 competitive window was {window or 'unavailable'}.",
            window is not None,
        ))
        dimensions.append(HistoricalDecisionDimension(
            "future_capital_liquidity", "improved" if incoming_picks > outgoing_picks else "reduced" if incoming_picks < outgoing_picks else "unchanged",
            "Draft-capital direction uses generic pick identities known at the transaction boundary.",
        ))
        superflex = any(slot.upper() in {"SUPER_FLEX", "SUPERFLEX", "Q_W_R_T"} for slot in before.roster_positions)
        incoming_qb = max((float(asset.market_value or 0) for asset in incoming if asset.position == "QB"), default=0)
        outgoing_qb = max((float(asset.market_value or 0) for asset in outgoing if asset.position == "QB"), default=0)
        dimensions.append(HistoricalDecisionDimension(
            "scarcity", "material_qb_cost" if superflex and outgoing_qb > incoming_qb else "no_supported_veto",
            "Scarcity uses the historical league format and contemporaneous positions/values.",
            bool(before.roster_positions),
        ))
        dimensions.append(HistoricalDecisionDimension(
            "risk", "partially_observed" if missing else "observed",
            "Risk confidence reflects historical market, lineup, age, and pick uncertainty coverage; no later injury is used.",
        ))
        confidence_score = min(before.confidence, after.confidence, round(coverage * 100))
        if coverage == 0:
            classification = ProcessClassification.INSUFFICIENT
        elif ratio >= .8 and (fit == "aligned" or (lineup_delta is not None and lineup_delta >= 0)):
            classification = ProcessClassification.SOUND if ratio <= 1.25 else ProcessClassification.STRONG
        elif ratio >= .65 or package in {"coherent", "useful_depth"}:
            classification = ProcessClassification.DEFENSIBLE
        elif ratio >= .5:
            classification = ProcessClassification.QUESTIONABLE
        else:
            classification = ProcessClassification.POOR
        explanations = [f"{row.name}: {row.assessment}." for row in dimensions]
        if missing:
            explanations.append("Partial evidence reduced confidence; unavailable values were not replaced with current values.")
        return HistoricalProcessEvaluation(
            classification, _confidence(confidence_score), tuple(dimensions),
            tuple(explanations), known_out, known_in, round(coverage, 4), missing,
        )

    @staticmethod
    def _outcome(
        post: HistoricalFranchiseState,
        later: HistoricalFranchiseState | None,
        as_of: str,
    ) -> HistoricalOutcomeEvaluation:
        if later is None or later.state_id == post.state_id:
            return HistoricalOutcomeEvaluation(
                OutcomeClassification.NOT_MATURE, ConfidenceLevel.LOW,
                "not_yet_mature", as_of, (),
                ("No later accepted Step 3 state is available at this as-of boundary.",),
            )
        dimensions: list[HistoricalDecisionDimension] = []
        value_available = post.roster_market_value is not None and later.roster_market_value is not None
        value_delta = later.roster_market_value - post.roster_market_value if value_available else None
        dimensions.append(HistoricalDecisionDimension(
            "later_market_value", "positive" if value_delta and value_delta > 0 else "negative" if value_delta and value_delta < 0 else "mixed_or_unknown",
            f"Later roster market value changed by {value_delta:.1f}." if value_available else "Complete comparable later market evidence is unavailable.",
            value_available,
        ))
        record_delta = later.record.wins - post.record.wins
        dimensions.append(HistoricalDecisionDimension(
            "later_competitive_results", "positive" if record_delta > 0 else "mixed_or_unknown",
            "Later results are contextual evidence and are not attributed solely to this trade.",
            later.record.games_observed > post.record.games_observed,
        ))
        lineup_available = post.lineup.optimal_points is not None and later.lineup.optimal_points is not None
        lineup_delta = later.lineup.optimal_points - post.lineup.optimal_points if lineup_available else None
        dimensions.append(HistoricalDecisionDimension(
            "later_lineup_state", "positive" if lineup_delta and lineup_delta > 0 else "negative" if lineup_delta and lineup_delta < 0 else "mixed_or_unknown",
            f"Later supported lineup delta was {lineup_delta:.2f}." if lineup_available else "Later lineup comparison is unavailable.",
            lineup_available,
        ))
        signals = [value_delta, lineup_delta]
        known = [value for value in signals if value is not None]
        if not known and later.record.games_observed <= post.record.games_observed:
            classification = OutcomeClassification.INSUFFICIENT
        elif sum(value > 0 for value in known) > sum(value < 0 for value in known):
            classification = OutcomeClassification.POSITIVE
        elif sum(value < 0 for value in known) > sum(value > 0 for value in known):
            classification = OutcomeClassification.NEGATIVE
        else:
            classification = OutcomeClassification.MIXED
        evidence_count = sum(row.evidence_available for row in dimensions)
        return HistoricalOutcomeEvaluation(
            classification, _confidence(round(evidence_count / len(dimensions) * 100)),
            "mature" if evidence_count >= 2 else "partial", as_of, tuple(dimensions),
            ("Outcome uses only evidence after the transaction and does not modify Process.",),
        )

    def evaluate_trade(self, league_id: str, event_id: str, *, as_of: str | None = None) -> HistoricalTradeEvaluation:
        event = self.history.event_by_identity(str(league_id), str(event_id))
        if event is None or event.event_type is not HistoricalEventType.TRADE:
            raise KeyError("Unknown canonical trade event for selected league.")
        if not event.occurred_at or len(event.franchise_ids) < 2:
            raise ValueError("Canonical trade requires a timestamp and at least two franchises.")
        # The default boundary is the latest accepted canonical event, not wall
        # clock time. Replays therefore remain deterministic until source truth
        # actually advances.
        boundary_as_of = as_of or max(
            (row.occurred_at for row in self.history.events_for_league(event.league_id) if row.occurred_at),
            default=event.occurred_at,
        )
        explicit_roster_ids = tuple(event.attributes.get("roster_ids") or ())
        participant_ids = (
            tuple(f"{event.league_id}:franchise:{value}" for value in explicit_roster_ids)
            if len(explicit_roster_ids) >= 2 else event.franchise_ids
        )
        prepared: list[tuple[HistoricalFranchiseState, HistoricalFranchiseState, HistoricalFranchiseState | None]] = []
        for franchise_id in participant_ids:
            before, after = self.states.around_event(event.league_id, franchise_id, event.event_id)
            later = None
            try:
                later = self.states.reconstruct(event.league_id, franchise_id, HistoricalBoundary(
                    season=event.season, occurred_at=boundary_as_of,
                ))
            except (KeyError, ValueError):
                later = None
            prepared.append((before, after, later))
        history_generation = prepared[0][0].history_generation
        market_generation = semantic_identity(
            "historical-transaction-market",
            *(state.market_generation for states in prepared for state in states[:2]),
        )
        evaluation_id = semantic_identity(
            "historical-trade-evaluation", event.league_id, event.event_id,
            history_generation, market_generation, boundary_as_of,
            HISTORICAL_TRANSACTION_METHOD_VERSION,
        )
        with self._lock:
            cached = self._cache.get(evaluation_id)
            if cached is not None:
                self._metrics["cache_hits"] += 1
                return cached
        sides = tuple(HistoricalTradeSideEvaluation(
            before.franchise_id, before.state_id, after.state_id,
            later.state_id if later else None,
            self._process(before, after), self._outcome(after, later, boundary_as_of),
        ) for before, after, later in prepared)
        references = tuple(sorted({
            event.source_reference or event.event_id,
            *(ref for states in prepared for state in states[:2] for ref in state.evidence_references),
            *(asset.market_checkpoint_id for states in prepared for state in states[:2] for asset in state.players if asset.market_checkpoint_id),
        }))
        result = HistoricalTradeEvaluation(
            evaluation_id, event.league_id, event.event_id, event.occurred_at,
            event.season, sides, references, history_generation, market_generation,
            boundary_as_of,
        )
        with self._lock:
            self._cache[evaluation_id] = result
            self._metrics["evaluations"] += 1
        return result

    def evaluate_backlog(
        self, league_id: str, *, limit: int = 250, cursor: int = 0,
        as_of: str | None = None,
    ) -> tuple[tuple[HistoricalTradeEvaluation, ...], HistoricalBacklogMetrics]:
        if limit < 1 or limit > 1000:
            raise ValueError("Historical trade backlog limit must be between 1 and 1000.")
        if cursor < 0:
            raise ValueError("Historical trade backlog cursor cannot be negative.")
        trades = self.history.events_for_league(str(league_id), event_type=HistoricalEventType.TRADE)
        selected = trades[cursor:cursor + limit]
        before_hits = self._metrics["cache_hits"]
        evaluations = tuple(self.evaluate_trade(str(league_id), event.event_id, as_of=as_of) for event in selected)
        confidence = Counter(side.process.confidence.value for row in evaluations for side in row.sides)
        maturity = Counter(side.outcome.maturity for row in evaluations for side in row.sides)
        metrics = HistoricalBacklogMetrics(
            str(league_id), len(trades), len(evaluations),
            self._metrics["cache_hits"] - before_hits,
            sum(any(side.process.classification is ProcessClassification.INSUFFICIENT for side in row.sides) for row in evaluations),
            sum(any(side.process.classification is ProcessClassification.BLOCKED for side in row.sides) for row in evaluations),
            dict(confidence), dict(maturity), 0, 0, cursor,
            cursor + len(selected) if cursor + len(selected) < len(trades) else None,
            cursor + len(selected) >= len(trades),
        )
        self._metrics["backlog_runs"] += 1
        return evaluations, metrics

    async def evaluate_backlog_async(
        self, league_id: str, *, limit: int = 250, cursor: int = 0,
        as_of: str | None = None,
    ) -> tuple[tuple[HistoricalTradeEvaluation, ...], HistoricalBacklogMetrics]:
        return await asyncio.to_thread(
            self.evaluate_backlog, league_id, limit=limit, cursor=cursor,
            as_of=as_of,
        )

    def health(self) -> dict[str, object]:
        return {
            **dict(self._metrics), "cached_evaluations": len(self._cache),
            "method_version": HISTORICAL_TRANSACTION_METHOD_VERSION,
            "provider_calls": 0, "raw_history_scans": 0,
        }


historical_transaction_intelligence = HistoricalTransactionIntelligenceService()
