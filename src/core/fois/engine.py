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
        completed = tuple(sorted(facts.completed_seasons, key=lambda row: row.season))[-10:]
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
        roster = facts.roster_metrics or {}
        for key, label in (
            ("starting_lineup_strength", "Starting-lineup strength"),
            ("roster_flexibility", "Roster flexibility"),
        ):
            if roster.get(key) is not None:
                calculated[key] = _metric(
                    key, label, f"League-relative {label.casefold()} from existing DTOS intelligence.",
                    roster[key], clamp(float(roster[key])), 1, 70, 100,
                    f"Reuses the existing DTOS league-relative value of {roster[key]}/100 without recalculating roster intelligence.",
                    evidence_ids,
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
        confidence = round(sum(row.confidence * row.weight for row in available) / sum(row.weight for row in available), 2) if available else 0
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
        key_source = f"{facts.league_id}|{facts.franchise_id}|{start}|{end}|{self.configuration.model_version}"
        score_key = hashlib.sha256(key_source.encode()).hexdigest()
        return FrontOfficeIntelligenceScore(
            VERSION, facts.league_id, facts.franchise_id, facts.owner_id, start, end,
            len(completed), overall, letter_grade(overall, self.configuration),
            category_scores, strongest, weakest, summary, confidence, completeness,
            self.configuration.model_version,
            generated_at or datetime.now(timezone.utc).isoformat(),
            evidence_ids, warnings, provisional, score_key,
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
