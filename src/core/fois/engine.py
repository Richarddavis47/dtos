"""Deterministic provisional FOIS scoring engine."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from statistics import mean

from app_metadata import VERSION
from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION, validate_configuration
from src.core.fois.facts import FOISFacts
from src.core.fois.models import (
    Directionality,
    FrontOfficeIntelligenceScore,
    FrontOfficeMetricScore,
    FrontOfficeScoringConfiguration,
    MetricStatus,
)
from src.core.fois.registry import registry_by_category
from src.core.fois.results import ResultsScorer
from src.core.fois.scoring import aggregate_categories, aggregate_metrics, clamp, letter_grade

CATEGORY_NAMES = {
    "results": "Results",
    "trading_asset_management": "Trading and Asset Management",
    "roster_construction": "Roster Construction",
    "drafting_talent_evaluation": "Drafting and Talent Evaluation",
    "waivers_transactions": "Waivers and Transactions",
}


def _metric(
    key: str,
    name: str,
    description: str,
    value: float | int | None,
    score: float | None,
    sample: int,
    confidence: float,
    completeness: float,
    explanation: str,
    evidence: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    status: MetricStatus = MetricStatus.PROVISIONAL,
    directionality: Directionality = Directionality.HIGHER_IS_BETTER,
) -> FrontOfficeMetricScore:
    return FrontOfficeMetricScore(
        key, name, description, value, score, 1.0, score, directionality, sample,
        confidence, completeness, explanation, evidence, warnings, status,
    )


def _unavailable(definition) -> FrontOfficeMetricScore:
    return _metric(
        definition.key, definition.name, definition.description, None, None, 0,
        0, 0, "The required historical source is not available in this release.",
        warnings=("Unavailable evidence is not treated as zero.",),
        status=definition.default_status if definition.default_status is not MetricStatus.PROVISIONAL else MetricStatus.INSUFFICIENT_DATA,
        directionality=definition.directionality,
    )


class FOISEngine:
    def __init__(
        self,
        configuration: FrontOfficeScoringConfiguration = DEFAULT_FOIS_CONFIGURATION,
    ) -> None:
        self.configuration = validate_configuration(configuration)
        self.registry = registry_by_category()
        self.results_scorer = ResultsScorer(configuration)

    def evaluate(self, facts: FOISFacts, *, generated_at: str | None = None) -> FrontOfficeIntelligenceScore:
        # Full tenure is canonical. Trailing windows are presentation views and
        # must never replace early seasons in the executive score.
        completed = tuple(sorted(facts.completed_seasons, key=lambda row: row.season))
        start = completed[0].season if completed else 0
        end = completed[-1].season if completed else 0
        season_confidence = clamp(len(completed) / 10 * 100)
        evidence_ids = tuple(item.source_identifier for item in facts.evidence)
        calculated: dict[str, FrontOfficeMetricScore] = {}
        games = sum((row.wins or 0) + (row.losses or 0) for row in completed)
        wins = sum(row.wins or 0 for row in completed)
        championships = sum(row.championship for row in completed)
        playoffs = sum(row.playoff_finish is not None for row in completed)
        rebuild_runs = self._rebuild_runs(completed)
        longest_rebuild = max(rebuild_runs, default=0)
        if games:
            calculated["regular_season_winning_percentage"] = _metric(
                "regular_season_winning_percentage", "Regular-season winning percentage",
                "Completed regular-season wins divided by completed games.",
                round(wins / games, 4), clamp(wins / games * 100), games,
                season_confidence, clamp(len(completed) / 10 * 100),
                f"{wins} wins in {games} completed regular-season games.",
                evidence_ids,
            )
        if completed:
            calculated["championships"] = _metric(
                "championships", "Championships", "League championships over the evaluation window.",
                championships, clamp(championships * 35), len(completed),
                season_confidence, clamp(len(completed) / 10 * 100),
                f"{championships} championships across {len(completed)} evaluated seasons; this is combined with sustained-results metrics rather than used alone.",
                evidence_ids,
            )
            calculated["playoff_appearances"] = _metric(
                "playoff_appearances", "Playoff appearances", "Share of evaluated seasons reaching the playoffs.",
                playoffs, clamp(playoffs / len(completed) * 100), len(completed),
                season_confidence, clamp(len(completed) / 10 * 100),
                f"Reached the playoffs in {playoffs} of {len(completed)} evaluated seasons.",
                evidence_ids,
            )
            rebuild_score = 90 if longest_rebuild <= 2 else max(20, 90 - (longest_rebuild - 2) * 20)
            calculated["rebuild_duration"] = _metric(
                "rebuild_duration", "Rebuild duration", "Longest consecutive rebuilding run.",
                longest_rebuild, rebuild_score, len(completed), season_confidence,
                clamp(len(completed) / 10 * 100),
                (
                    f"Longest rebuild lasted {longest_rebuild} seasons; one or two down seasons remain inside the productive-cycle threshold."
                    if longest_rebuild <= 2
                    else f"Longest rebuild lasted {longest_rebuild} seasons, beyond the configured two-season productive threshold."
                ),
                evidence_ids,
                directionality=Directionality.LOWER_IS_BETTER,
            )
        trade_count = len(facts.trades)
        productive = sum(trade.strategically_productive is True for trade in facts.trades)
        if trade_count:
            calculated["trade_activity"] = _metric(
                "trade_activity", "Trade activity", "Observed completed trade sample; activity alone has limited value.",
                trade_count, clamp(min(trade_count, 10) * 10), trade_count,
                clamp(trade_count / 10 * 100), clamp(trade_count / 10 * 100),
                f"{trade_count} completed trades create an opportunity sample but do not independently establish quality.",
                evidence_ids,
            )
            calculated["productive_trade_activity"] = _metric(
                "productive_trade_activity", "Productive trade activity",
                "Trades with evidence of improved outlook, flexibility, or asset position.",
                productive, clamp(productive / trade_count * 100), trade_count,
                clamp(trade_count / 10 * 100), clamp(trade_count / 10 * 100),
                f"{productive} of {trade_count} observed trades have supported strategic improvement evidence.",
                evidence_ids,
            )
            justified = [
                trade for trade in facts.trades
                if trade.market_overpay_percent is not None
                and 0 < trade.market_overpay_percent <= 20
                and (trade.championship_outlook_delta or 0) > 0
            ]
            if justified:
                calculated["overpay_efficiency"] = _metric(
                    "overpay_efficiency", "Overpay efficiency",
                    "Reasonable premiums that materially improve championship outlook.",
                    mean(trade.market_overpay_percent for trade in justified), 85,
                    len(justified), clamp(len(justified) * 25), clamp(len(justified) * 25),
                    f"{len(justified)} acquisition(s) paid no more than 20% above consensus while improving championship outlook; strategic fit can outweigh a modest paper loss.",
                    evidence_ids,
                    directionality=Directionality.CONTEXTUAL,
                )
            process = [row.process_score for row in facts.trades if row.process_score is not None]
            outcomes = [row.outcome_score for row in facts.trades if row.outcome_score is not None]
            recovery = [row.recovery_score for row in facts.trades if row.recovery_score is not None]
            impact_total = sum(max(0.01, row.impact_weight) for row in facts.trades)
            if process:
                weighted = sum(
                    (row.process_score or 0) * max(0.01, row.impact_weight)
                    for row in facts.trades if row.process_score is not None
                ) / sum(max(0.01, row.impact_weight) for row in facts.trades if row.process_score is not None)
                calculated["value_captured_at_transaction_time"] = _metric(
                    "value_captured_at_transaction_time", "Decision quality at transaction time",
                    "Impact-weighted process quality using contemporaneous evidence.",
                    round(weighted, 2), clamp(weighted), len(process),
                    clamp(len(process) / 10 * 100), clamp(len(process) / trade_count * 100),
                    f"{len(process)} of {trade_count} trades have transaction-time process evidence; impact weight {impact_total:.2f}.",
                    evidence_ids,
                )
            if outcomes:
                calculated["subsequent_asset_value_change"] = _metric(
                    "subsequent_asset_value_change", "Long-term trade outcome",
                    "Observed outcome kept separate from transaction-time decision quality.",
                    round(mean(outcomes), 2), clamp(mean(outcomes)), len(outcomes),
                    clamp(len(outcomes) / 10 * 100), clamp(len(outcomes) / trade_count * 100),
                    "Outcome evidence is credited without rewriting the original process assessment.", evidence_ids,
                )
            if recovery:
                calculated["recovery_from_unsuccessful_trades"] = _metric(
                    "recovery_from_unsuccessful_trades", "Recovery from unsuccessful trades",
                    "Quality and speed of evidence-backed recovery after value loss.",
                    round(mean(recovery), 2), clamp(mean(recovery)), len(recovery),
                    clamp(len(recovery) / 5 * 100), clamp(len(recovery) / trade_count * 100),
                    "Recovery is scored independently; repeated reckless attempts do not erase poor initial process.", evidence_ids,
                )
        roster = facts.roster_metrics or {}
        for key, label in (
            ("starting_lineup_strength", "Starting-lineup strength"),
            ("roster_flexibility", "Roster flexibility"),
            ("depth", "Depth"),
            ("positional_balance", "Positional balance"),
            ("injury_resilience", "Injury resilience"),
            ("asset_liquidity", "Asset liquidity"),
            ("competitive_window_coherence", "Competitive-window coherence"),
        ):
            if roster.get(key) is not None:
                calculated[key] = _metric(
                    key, label, f"League-relative {label.casefold()} from existing DTOS intelligence.",
                    roster[key], clamp(float(roster[key])), 1, 70, 100,
                    f"Reuses the existing DTOS league-relative value of {roster[key]}/100 without recalculating roster intelligence.",
                    evidence_ids,
                )
        if facts.drafts:
            values = [row.value_over_expected for row in facts.drafts if row.value_over_expected is not None]
            processes = [row.process_score for row in facts.drafts if row.process_score is not None]
            if values:
                score = clamp(50 + mean(values))
                calculated["value_over_expected_draft_slot"] = _metric(
                    "value_over_expected_draft_slot", "Value over expected draft slot",
                    "Value captured relative to transaction-time draft-slot expectation.",
                    round(mean(values), 2), score, len(values), clamp(len(values) * 20),
                    clamp(len(values) / len(facts.drafts) * 100),
                    "Draft outcomes use the evidence available for each historical selection.", evidence_ids,
                )
            if processes:
                calculated["pick_value_realization"] = _metric(
                    "pick_value_realization", "Draft process quality",
                    "Selection process separated from later player outcome.",
                    round(mean(processes), 2), clamp(mean(processes)), len(processes),
                    clamp(len(processes) * 20), clamp(len(processes) / len(facts.drafts) * 100),
                    "Process evidence is graded independently from injury and later outcome variance.", evidence_ids,
                )
        if facts.waivers:
            waiver_values = [row.value_created for row in facts.waivers if row.value_created is not None]
            faab_values = [row.faab_efficiency for row in facts.waivers if row.faab_efficiency is not None]
            calculated["waiver_activity"] = _metric(
                "waiver_activity", "Waiver activity",
                "Observed waiver, free-agent, add/drop, and FAAB activity; activity is not quality.",
                len(facts.waivers), None, len(facts.waivers),
                clamp(len(facts.waivers) / 20 * 100), 100,
                f"{len(facts.waivers)} historical transaction(s) establish activity only; no performance score is fabricated.",
                evidence_ids, status=MetricStatus.INSUFFICIENT_DATA,
                directionality=Directionality.CONTEXTUAL,
            )
            if waiver_values:
                calculated["waiver_value_created"] = _metric(
                    "waiver_value_created", "Waiver value created",
                    "Evidence-supported value created by waiver and free-agent decisions.",
                    round(mean(waiver_values), 2), clamp(mean(waiver_values)), len(waiver_values),
                    clamp(len(waiver_values) / 10 * 100), clamp(len(waiver_values) / len(facts.waivers) * 100),
                    "Only transactions with supported value evidence contribute.", evidence_ids,
                )
            if faab_values:
                calculated["faab_efficiency"] = _metric(
                    "faab_efficiency", "FAAB efficiency",
                    "Evidence-supported FAAB efficiency; spending volume alone is not quality.",
                    round(mean(faab_values), 2), clamp(mean(faab_values)), len(faab_values),
                    clamp(len(faab_values) / 10 * 100), clamp(len(faab_values) / len(facts.waivers) * 100),
                    "Only supported FAAB outcomes contribute.", evidence_ids,
                )
        categories = []
        for category, definitions in self.registry.items():
            if category == "results":
                categories.append(self.results_scorer.score(facts))
                continue
            metrics = tuple(calculated.get(definition.key, _unavailable(definition)) for definition in definitions)
            categories.append(aggregate_metrics(
                category, CATEGORY_NAMES[category],
                self.configuration.category_weights[category], metrics,
                self.configuration,
            ))
        category_scores = tuple(categories)
        overall = aggregate_categories(category_scores, self.configuration)
        available = tuple(row for row in category_scores if row.normalized_score is not None)
        strongest = max(available, key=lambda row: row.normalized_score).category_name if available else None
        weakest = min(available, key=lambda row: row.normalized_score).category_name if available else None
        completeness = round(sum(row.completeness * row.weight for row in category_scores) / 100, 2)
        supported_weight = round(sum(row.weight for row in available), 2)
        base_confidence = (
            sum(row.confidence * row.weight for row in available) / supported_weight
            if available and supported_weight else 0
        )
        history_coverage = min(1.0, len(completed) / max(1, min(5, facts.expected_seasons or 5)))
        confidence = round(
            base_confidence
            * (.55 + .45 * completeness / 100)
            * (.70 + .30 * history_coverage),
            2,
        )
        warnings = tuple(dict.fromkeys((*facts.warnings, *(
            warning for category in category_scores for warning in category.warnings
        ))))
        provisional = len(completed) < 10 or completeness < 80 or any(
            category.normalized_score is None for category in category_scores
        )
        summary = (
            f"Provisional FOIS score {overall}/100 ({letter_grade(overall, self.configuration)}) across {len(completed)} completed seasons. "
            f"Strongest supported category: {strongest or 'unavailable'}; weakest supported category: {weakest or 'unavailable'}. "
            "Missing categories are disclosed and excluded rather than scored as zero."
            if overall is not None
            else "FOIS is provisional because no supported category has sufficient historical evidence."
        )
        key_source = f"{facts.league_id}|{facts.franchise_id}|{facts.tenure_id or facts.owner_id}|{start}|{end}|{self.configuration.model_version}"
        score_key = hashlib.sha256(key_source.encode()).hexdigest()
        evidence_state = (
            "insufficient_evidence" if overall is None else
            "provisional" if provisional else "available"
        )
        strengths = tuple(row.category_name for row in sorted(
            available, key=lambda row: row.normalized_score or 0, reverse=True
        )[:2])
        weaknesses = tuple(row.category_name for row in sorted(
            available, key=lambda row: row.normalized_score or 0
        )[:1])
        partners = {row.partner_id for row in facts.trades if row.partner_id}
        tendencies = []
        if len(facts.trades) >= self.configuration.minimum_sample_sizes.get("tendencies", 5):
            tendencies.append(
                "Aggressive trader" if len(facts.trades) >= 15 else "Selective trader"
            )
        if len(facts.waivers) >= self.configuration.minimum_sample_sizes.get("tendencies", 5):
            tendencies.append("Waiver-active")
        unavailable_tendencies = () if tendencies else ("TENDENCY_UNAVAILABLE",)
        return FrontOfficeIntelligenceScore(
            VERSION, facts.league_id, facts.franchise_id, facts.owner_id, start, end,
            len(completed), overall, letter_grade(overall, self.configuration),
            category_scores, strongest, weakest, summary, confidence, completeness,
            self.configuration.model_version,
            generated_at or datetime.now(timezone.utc).isoformat(),
            evidence_ids, warnings, provisional, score_key,
            facts.gm_id or facts.owner_id,
            facts.gm_name,
            facts.tenure_id,
            facts.tenure_started_at,
            evidence_state,
            facts.brain_snapshot_id,
            facts.brain_version,
            current_team_score=facts.current_team_score,
            management_momentum="Stable" if completed else "Unavailable",
            strengths=strengths,
            weaknesses=weaknesses,
            franchise_name=facts.franchise_name,
            supported_weight=supported_weight,
            tendencies=tuple(tendencies),
            unavailable_tendencies=unavailable_tendencies,
            trade_partner_count=len(partners),
        )

    @staticmethod
    def _rebuild_runs(seasons) -> tuple[int, ...]:
        runs, current = [], 0
        for row in seasons:
            if row.rebuilding:
                current += 1
            elif current:
                runs.append(current)
                current = 0
        if current:
            runs.append(current)
        return tuple(runs)
